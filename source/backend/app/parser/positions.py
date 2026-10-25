"""Преобразование UTF-8 байтовых смещений Tree-sitter в координаты API.

Публичный контракт:
- строки с 1;
- столбцы с 1, в UTF-16 code units (совместимо с Monaco);
- конечная позиция полуоткрытого диапазона [start, end).
"""

from __future__ import annotations

from bisect import bisect_right


def clamp_utf8_byte_offset(source_bytes: bytes, byte_offset: int) -> int:
    """Сдвигает смещение назад, если оно попало внутрь многобайтового символа."""
    if byte_offset <= 0:
        return 0
    if byte_offset >= len(source_bytes):
        return len(source_bytes)
    while byte_offset > 0 and (source_bytes[byte_offset] & 0xC0) == 0x80:
        byte_offset -= 1
    return byte_offset


def utf16_code_unit_length(text: str) -> int:
    """Длина текста в UTF-16 code units (суррогатные пары дают 2)."""
    length = 0
    for char in text:
        length += 2 if ord(char) > 0xFFFF else 1
    return length


def byte_offset_to_line_utf16_column(
    source: str,
    source_bytes: bytes,
    byte_offset: int,
) -> tuple[int, int]:
    """Возвращает (line, column) для байтового смещения в UTF-8 представлении source."""
    safe_offset = clamp_utf8_byte_offset(source_bytes, byte_offset)
    prefix = source_bytes[:safe_offset].decode("utf-8")
    line = prefix.count("\n") + 1
    line_start = prefix.rfind("\n") + 1
    column = utf16_code_unit_length(prefix[line_start:]) + 1
    return line, column


def byte_range_to_positions(
    source: str,
    source_bytes: bytes,
    start_byte: int,
    end_byte: int,
) -> tuple[int, int, int, int]:
    """Преобразует [start_byte, end_byte) в (start_line, start_col, end_line, end_col)."""
    start_line, start_column = byte_offset_to_line_utf16_column(source, source_bytes, start_byte)
    end_line, end_column = byte_offset_to_line_utf16_column(source, source_bytes, end_byte)
    return start_line, start_column, end_line, end_column


class LineIndex:
    """Индекс начал строк для многократного перевода смещений одного исходника.

    Результат position() совпадает с byte_offset_to_line_utf16_column.
    """

    def __init__(self, source: str, source_bytes: bytes) -> None:
        self.source = source
        self.source_bytes = source_bytes
        line_starts = [0]
        for index, byte_value in enumerate(source_bytes):
            if byte_value == 0x0A:
                line_starts.append(index + 1)
        self._line_start_bytes = line_starts

    def position(self, byte_offset: int) -> tuple[int, int]:
        safe_offset = clamp_utf8_byte_offset(self.source_bytes, byte_offset)
        line_index = bisect_right(self._line_start_bytes, safe_offset) - 1
        if line_index < 0:
            line_index = 0
        line_start = self._line_start_bytes[line_index]
        column_text = self.source_bytes[line_start:safe_offset].decode("utf-8")
        return line_index + 1, utf16_code_unit_length(column_text) + 1

    def span(self, start_byte: int, end_byte: int) -> tuple[int, int, int, int]:
        start_line, start_column = self.position(start_byte)
        end_line, end_column = self.position(end_byte)
        return start_line, start_column, end_line, end_column

    def line_utf16_column_to_byte(self, line: int, column: int) -> int:
        """Переводит (line, UTF-16 column) 1-based в байтовое смещение UTF-8."""
        if line < 1:
            return 0
        line_index = line - 1
        if line_index >= len(self._line_start_bytes):
            return len(self.source_bytes)
        line_start = self._line_start_bytes[line_index]
        next_line_start = (
            self._line_start_bytes[line_index + 1]
            if line_index + 1 < len(self._line_start_bytes)
            else len(self.source_bytes)
        )
        line_bytes = self.source_bytes[line_start:next_line_start]
        # Без завершающего \\n для измерения столбцов.
        if line_bytes.endswith(b"\n"):
            content_bytes = line_bytes[:-1]
        else:
            content_bytes = line_bytes
        content = content_bytes.decode("utf-8")
        target_col = max(1, column)
        units = 0
        char_index = 0
        while char_index < len(content) and units + 1 < target_col:
            units += 2 if ord(content[char_index]) > 0xFFFF else 1
            char_index += 1
        prefix = content[:char_index]
        return line_start + len(prefix.encode("utf-8"))

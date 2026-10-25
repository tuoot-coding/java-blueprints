from __future__ import annotations

from app.parser.positions import byte_offset_to_line_utf16_column, byte_range_to_positions


def test_ascii_positions_are_one_based() -> None:
    source = "ab\ncd"
    data = source.encode("utf-8")
    assert byte_offset_to_line_utf16_column(source, data, 0) == (1, 1)
    assert byte_offset_to_line_utf16_column(source, data, 2) == (1, 3)
    assert byte_offset_to_line_utf16_column(source, data, 3) == (2, 1)


def test_cyrillic_columns_use_utf16_units_not_bytes() -> None:
    # Кириллица: 2 байта UTF-8, 1 UTF-16 code unit.
    source = "класс A"
    data = source.encode("utf-8")
    # Смещение после первой буквы "к" (2 байта) -> столбец 2.
    assert byte_offset_to_line_utf16_column(source, data, 2) == (1, 2)
    start_line, start_col, end_line, end_col = byte_range_to_positions(source, data, 0, len(data))
    assert (start_line, start_col) == (1, 1)
    assert end_line == 1
    assert end_col == len(source) + 1


def test_emoji_uses_two_utf16_units() -> None:
    source = "a😀b"
    data = source.encode("utf-8")
    # После "a" столбец 2; после emoji столбец 4 (суррогатная пара).
    assert byte_offset_to_line_utf16_column(source, data, 1) == (1, 2)
    emoji_end = 1 + len("😀".encode())
    assert byte_offset_to_line_utf16_column(source, data, emoji_end) == (1, 4)

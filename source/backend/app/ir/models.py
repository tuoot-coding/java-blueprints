"""Структурное IR Java: снимок синтаксического дерева для анализа и CFG.

IR не является CFG. Узлы хранят исходный срез и дочерние элементы с ролями.
Неподдержанная конструкция остается узлом kind=unsupported с исходным текстом.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IrNodeKind(StrEnum):
    """Виды узлов структурного IR. Значение совпадает с именем в API."""

    COMPILATION_UNIT = "compilation_unit"
    PACKAGE = "package_declaration"
    IMPORT = "import_declaration"
    CLASS = "class_declaration"
    INTERFACE = "interface_declaration"
    ENUM = "enum_declaration"
    ENUM_CONSTANT = "enum_constant"
    RECORD = "record_declaration"
    FIELD = "field_declaration"
    METHOD = "method_declaration"
    CONSTRUCTOR = "constructor_declaration"
    COMPACT_CONSTRUCTOR = "compact_constructor_declaration"
    PARAMETER = "parameter"
    FORMAL_PARAMETERS = "formal_parameters"
    LAMBDA = "lambda_expression"
    METHOD_REFERENCE = "method_reference"
    CLASS_LITERAL = "class_literal"
    LOCAL_VARIABLE = "local_variable_declaration"
    BLOCK = "block"
    EXPRESSION_STATEMENT = "expression_statement"
    ASSIGNMENT = "assignment_expression"
    RETURN = "return_statement"
    BREAK = "break_statement"
    CONTINUE = "continue_statement"
    THROW = "throw_statement"
    IF = "if_statement"
    WHILE = "while_statement"
    DO = "do_statement"
    FOR = "for_statement"
    ENHANCED_FOR = "enhanced_for_statement"
    TRY = "try_statement"
    CATCH = "catch_clause"
    FINALLY = "finally_clause"
    SWITCH = "switch_expression"
    SWITCH_GROUP = "switch_block_statement_group"
    SYNCHRONIZED = "synchronized_statement"
    LABELED = "labeled_statement"
    ASSERT = "assert_statement"
    YIELD = "yield_statement"
    METHOD_INVOCATION = "method_invocation"
    EXPLICIT_CONSTRUCTOR_INVOCATION = "explicit_constructor_invocation"
    OBJECT_CREATION = "object_creation_expression"
    FIELD_ACCESS = "field_access"
    ARRAY_ACCESS = "array_access"
    ARRAY_CREATION = "array_creation_expression"
    ARRAY_INITIALIZER = "array_initializer"
    CAST = "cast_expression"
    TERNARY = "ternary_expression"
    INSTANCEOF = "instanceof_expression"
    TRY_WITH_RESOURCES = "try_with_resources_statement"
    BINARY = "binary_expression"
    UNARY = "unary_expression"
    UPDATE = "update_expression"
    PARENTHESIZED = "parenthesized_expression"
    LITERAL = "literal"
    IDENTIFIER = "identifier"
    COMMENT = "comment"
    UNSUPPORTED = "unsupported"


ROLE_BODY = "body"
ROLE_ELSE = "else"
ROLE_CONDITION = "condition"
ROLE_PARAMETERS = "parameters"
ROLE_ARGUMENTS = "arguments"
ROLE_VALUE = "value"
ROLE_LEFT = "left"
ROLE_RIGHT = "right"
ROLE_OBJECT = "object"
ROLE_INIT = "init"
ROLE_UPDATE = "update"
ROLE_CHILDREN = "children"
ROLE_INDEX = "index"
ROLE_ALTERNATIVE = "alternative"
ROLE_RESOURCES = "resources"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Диапазон исходника: байты UTF-8 и позиции line/UTF-16 column, конец полуоткрытый."""

    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True, slots=True, kw_only=True)
class IrNode:
    """Узел IR одной ревизии исходника.

    id стабилен для одного и того же текста и того же обхода: порядок seq
    определяется деревом Tree-sitter, а не случайным числом.
    editable остается False, пока преобразование не доказано отдельным патчем.
    """

    id: str
    kind: IrNodeKind
    span: SourceSpan
    source_text: str
    syntax_type: str
    children: tuple[IrNode, ...] = ()
    child_roles: tuple[str, ...] = ()
    name: str | None = None
    operator: str | None = None
    type_text: str | None = None
    modifiers_text: str | None = None
    superclass_text: str | None = None
    interfaces_text: str | None = None
    type_parameters_text: str | None = None
    throws_text: str | None = None
    literal_kind: str | None = None
    label: str | None = None
    reason: str | None = None
    editable: bool = False

    def __post_init__(self) -> None:
        if len(self.children) != len(self.child_roles):
            raise ValueError("child_roles должны совпадать по длине с children")

    def role_child(self, role: str) -> IrNode | None:
        """Первый дочерний узел с указанной ролью."""
        for child, child_role in zip(self.children, self.child_roles, strict=True):
            if child_role == role:
                return child
        return None

    def role_children(self, role: str) -> tuple[IrNode, ...]:
        """Все дочерние узлы с указанной ролью, в порядке исходника."""
        return tuple(
            child
            for child, child_role in zip(self.children, self.child_roles, strict=True)
            if child_role == role
        )

"""Построение структурного IR из дерева tree-sitter-java.

Обход идет по именованным узлам грамматики. Знаки препинания остаются внутри
source_text родителя и не становятся отдельными узлами.

Распознанные оболочки (модификаторы, тип, throws, extends, implements,
параметры типа) сохраняются текстовыми полями. Это не kind=unsupported:
конструкция узнана, но ее внутренняя модель сознательно не раскрывается.

Любой другой именованный узел попадает в дерево как kind=unsupported и лист:
его source_text - точный срез исходника, дочерние узлы не подменяются выдуманной
структурой. Узлы ERROR и missing тоже становятся unsupported.
"""

from __future__ import annotations

from tree_sitter import Node, Tree

from app.ir.models import (
    ROLE_ALTERNATIVE,
    ROLE_ARGUMENTS,
    ROLE_BODY,
    ROLE_CHILDREN,
    ROLE_CONDITION,
    ROLE_ELSE,
    ROLE_INDEX,
    ROLE_INIT,
    ROLE_LEFT,
    ROLE_OBJECT,
    ROLE_PARAMETERS,
    ROLE_RESOURCES,
    ROLE_RIGHT,
    ROLE_UPDATE,
    ROLE_VALUE,
    IrNode,
    IrNodeKind,
    SourceSpan,
)
from app.parser.positions import LineIndex

_LITERAL_TYPES = frozenset(
    {
        "decimal_integer_literal",
        "hex_integer_literal",
        "octal_integer_literal",
        "binary_integer_literal",
        "decimal_floating_point_literal",
        "hex_floating_point_literal",
        "string_literal",
        "character_literal",
        "true",
        "false",
        "null_literal",
    }
)

_UPDATE_OPERATORS = frozenset({"++", "--"})


class _Cursor:
    """Отмечает уже разобранные дочерние узлы, чтобы остаток не потерять."""

    def __init__(self, node: Node) -> None:
        self._node = node
        self._used: set[int] = set()

    def take_field(self, field_name: str) -> Node | None:
        child = self._node.child_by_field_name(field_name)
        if child is None:
            return None
        self._used.add(child.id)
        return child

    def take_type(self, type_name: str) -> Node | None:
        for child in self._node.children:
            if child.type == type_name and child.id not in self._used:
                self._used.add(child.id)
                return child
        return None

    def mark(self, node: Node) -> None:
        self._used.add(node.id)

    def remaining_named(self) -> list[Node]:
        return [child for child in self._node.named_children if child.id not in self._used]


class _Context:
    def __init__(self, source: str) -> None:
        self.source_bytes = source.encode("utf-8")
        self.index = LineIndex(source, self.source_bytes)
        self._seq = 0

    def text_of(self, node: Node | None) -> str | None:
        if node is None:
            return None
        return self.source_bytes[node.start_byte : node.end_byte].decode("utf-8")

    def span(self, start_byte: int, end_byte: int) -> SourceSpan:
        start_line, start_column, end_line, end_column = self.index.span(start_byte, end_byte)
        return SourceSpan(
            start_byte=start_byte,
            end_byte=end_byte,
            start_line=start_line,
            start_column=start_column,
            end_line=end_line,
            end_column=end_column,
        )

    def make(
        self,
        node: Node,
        kind: IrNodeKind,
        *,
        children: list[tuple[str, IrNode]] | tuple[tuple[str, IrNode], ...] = (),
        name: str | None = None,
        operator: str | None = None,
        type_text: str | None = None,
        modifiers_text: str | None = None,
        superclass_text: str | None = None,
        interfaces_text: str | None = None,
        type_parameters_text: str | None = None,
        throws_text: str | None = None,
        literal_kind: str | None = None,
        label: str | None = None,
        reason: str | None = None,
    ) -> IrNode:
        return self.make_at(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            kind=kind,
            syntax_type=node.type,
            source_text=self.source_bytes[node.start_byte : node.end_byte].decode("utf-8"),
            children=children,
            name=name,
            operator=operator,
            type_text=type_text,
            modifiers_text=modifiers_text,
            superclass_text=superclass_text,
            interfaces_text=interfaces_text,
            type_parameters_text=type_parameters_text,
            throws_text=throws_text,
            literal_kind=literal_kind,
            label=label,
            reason=reason,
        )

    def make_at(
        self,
        *,
        start_byte: int,
        end_byte: int,
        kind: IrNodeKind,
        syntax_type: str,
        source_text: str,
        children: list[tuple[str, IrNode]] | tuple[tuple[str, IrNode], ...] = (),
        name: str | None = None,
        operator: str | None = None,
        type_text: str | None = None,
        modifiers_text: str | None = None,
        superclass_text: str | None = None,
        interfaces_text: str | None = None,
        type_parameters_text: str | None = None,
        throws_text: str | None = None,
        literal_kind: str | None = None,
        label: str | None = None,
        reason: str | None = None,
    ) -> IrNode:
        self._seq += 1
        pairs = tuple(children)
        return IrNode(
            id=f"n{start_byte}_{end_byte}_{kind.value}_{self._seq}",
            kind=kind,
            span=self.span(start_byte, end_byte),
            source_text=source_text,
            syntax_type=syntax_type,
            children=tuple(child for _, child in pairs),
            child_roles=tuple(role for role, _ in pairs),
            name=name,
            operator=operator,
            type_text=type_text,
            modifiers_text=modifiers_text,
            superclass_text=superclass_text,
            interfaces_text=interfaces_text,
            type_parameters_text=type_parameters_text,
            throws_text=throws_text,
            literal_kind=literal_kind,
            label=label,
            reason=reason,
            editable=False,
        )


def build_structural_ir(source: str, tree: Tree) -> IrNode:
    """Строит IR по уже разобранному дереву. source должен быть тем же текстом."""
    return _convert(_Context(source), tree.root_node)


def _convert(ctx: _Context, node: Node) -> IrNode:
    if node.is_missing or node.type == "ERROR":
        return _unsupported(ctx, node)
    converter = _CONVERTERS.get(node.type)
    if converter is not None:
        return converter(ctx, node)
    if node.type in _LITERAL_TYPES:
        return _literal(ctx, node)
    return _unsupported(ctx, node)


def _unsupported(ctx: _Context, node: Node) -> IrNode:
    reason = "missing" if node.is_missing else node.type
    return ctx.make(node, IrNodeKind.UNSUPPORTED, reason=reason)


def _literal(ctx: _Context, node: Node) -> IrNode:
    return ctx.make(node, IrNodeKind.LITERAL, literal_kind=node.type)


def _comment(ctx: _Context, node: Node) -> IrNode:
    return ctx.make(node, IrNodeKind.COMMENT)


def _identifier(ctx: _Context, node: Node) -> IrNode:
    return ctx.make(node, IrNodeKind.IDENTIFIER, name=ctx.text_of(node))


def _keyword_primary(ctx: _Context, node: Node) -> IrNode:
    """this и super - первичные выражения, для IR они совпадают с идентификатором."""
    return ctx.make(node, IrNodeKind.IDENTIFIER, name=node.type)


def _block(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.BLOCK, children=children)


def _program(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.COMPILATION_UNIT, children=children)


def _package(ctx: _Context, node: Node) -> IrNode:
    named = node.named_children
    name = ctx.text_of(named[0]) if named else None
    return ctx.make(node, IrNodeKind.PACKAGE, name=name)


def _import(ctx: _Context, node: Node) -> IrNode:
    parts = [ctx.text_of(child) or "" for child in node.named_children]
    name = ".".join(part for part in parts if part) or None
    return ctx.make(node, IrNodeKind.IMPORT, name=name)


def _class(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    name_node = cursor.take_field("name")
    type_parameters = cursor.take_field("type_parameters")
    superclass = cursor.take_field("superclass")
    interfaces = cursor.take_field("interfaces")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        for member in body.named_children:
            children.append((ROLE_CHILDREN, _convert(ctx, member)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        IrNodeKind.CLASS,
        children=children,
        name=ctx.text_of(name_node),
        modifiers_text=ctx.text_of(modifiers),
        type_parameters_text=ctx.text_of(type_parameters),
        superclass_text=ctx.text_of(superclass),
        interfaces_text=ctx.text_of(interfaces),
    )


def _declaration_with_declarators(
    ctx: _Context,
    node: Node,
    kind: IrNodeKind,
) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    type_node = cursor.take_field("type")
    declarators = [child for child in node.children if child.type == "variable_declarator"]
    for declarator in declarators:
        cursor.mark(declarator)
    names: list[str] = []
    children: list[tuple[str, IrNode]] = []
    for declarator in declarators:
        name_node = declarator.child_by_field_name("name")
        value_node = declarator.child_by_field_name("value")
        dimensions = declarator.child_by_field_name("dimensions")
        used = {item.id for item in (name_node, value_node, dimensions) if item is not None}
        if name_node is not None:
            name_text = ctx.text_of(name_node) or ""
            if dimensions is not None:
                name_text += ctx.text_of(dimensions) or ""
            names.append(name_text)
        if value_node is not None:
            children.append((ROLE_VALUE, _convert(ctx, value_node)))
        for extra in declarator.named_children:
            if extra.id not in used:
                children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        kind,
        children=children,
        name=", ".join(names) or None,
        type_text=ctx.text_of(type_node),
        modifiers_text=ctx.text_of(modifiers),
    )


def _field(ctx: _Context, node: Node) -> IrNode:
    return _declaration_with_declarators(ctx, node, IrNodeKind.FIELD)


def _local_variable(ctx: _Context, node: Node) -> IrNode:
    return _declaration_with_declarators(ctx, node, IrNodeKind.LOCAL_VARIABLE)


def _method(ctx: _Context, node: Node, *, kind: IrNodeKind) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    type_node = cursor.take_field("type")
    name_node = cursor.take_field("name")
    type_parameters = cursor.take_field("type_parameters")
    parameters = cursor.take_field("parameters")
    throws = cursor.take_type("throws")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if parameters is not None:
        children.extend(_parameters(ctx, parameters))
    if body is not None and body.type in {"block", "constructor_body"}:
        children.append((ROLE_BODY, _block(ctx, body)))
    elif body is not None:
        children.append((ROLE_BODY, _convert(ctx, body)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        kind,
        children=children,
        name=ctx.text_of(name_node),
        type_text=ctx.text_of(type_node),
        modifiers_text=ctx.text_of(modifiers),
        type_parameters_text=ctx.text_of(type_parameters),
        throws_text=ctx.text_of(throws),
    )


def _method_declaration(ctx: _Context, node: Node) -> IrNode:
    return _method(ctx, node, kind=IrNodeKind.METHOD)


def _constructor(ctx: _Context, node: Node) -> IrNode:
    return _method(ctx, node, kind=IrNodeKind.CONSTRUCTOR)


def _parameters(ctx: _Context, node: Node) -> list[tuple[str, IrNode]]:
    children: list[tuple[str, IrNode]] = []
    for child in node.named_children:
        if child.type == "formal_parameter":
            children.append((ROLE_PARAMETERS, _parameter(ctx, child)))
        elif child.type == "identifier":
            children.append(
                (
                    ROLE_PARAMETERS,
                    ctx.make(child, IrNodeKind.PARAMETER, name=ctx.text_of(child)),
                )
            )
        elif child.type == "spread_parameter":
            children.append((ROLE_PARAMETERS, _parameter(ctx, child)))
        else:
            children.append((ROLE_PARAMETERS, _convert(ctx, child)))
    return children


def _parameter(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    type_node = cursor.take_field("type")
    name_node = cursor.take_field("name")
    children = [(ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named()]
    return ctx.make(
        node,
        IrNodeKind.PARAMETER,
        children=children,
        name=ctx.text_of(name_node),
        type_text=ctx.text_of(type_node),
        modifiers_text=ctx.text_of(modifiers),
    )


def _expression_statement(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_VALUE, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.EXPRESSION_STATEMENT, children=children)


def _assignment(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    left = cursor.take_field("left")
    operator = cursor.take_field("operator")
    right = cursor.take_field("right")
    if left is None or right is None:
        return _unsupported(ctx, node)
    children = [
        (ROLE_LEFT, _convert(ctx, left)),
        (ROLE_RIGHT, _convert(ctx, right)),
    ]
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.ASSIGNMENT,
        children=children,
        operator=ctx.text_of(operator),
    )


def _return(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_VALUE, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.RETURN, children=children)


def _jump(ctx: _Context, node: Node, kind: IrNodeKind) -> IrNode:
    label = None
    for child in node.named_children:
        if child.type == "identifier":
            label = ctx.text_of(child)
            break
    return ctx.make(node, kind, label=label)


def _break(ctx: _Context, node: Node) -> IrNode:
    return _jump(ctx, node, IrNodeKind.BREAK)


def _continue(ctx: _Context, node: Node) -> IrNode:
    return _jump(ctx, node, IrNodeKind.CONTINUE)


def _throw(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_VALUE, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.THROW, children=children)


def _empty_statement(ctx: _Context, node: Node) -> IrNode:
    """Одиночная точка с запятой в позиции оператора - пустой блок того же диапазона."""
    return ctx.make_at(
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        kind=IrNodeKind.BLOCK,
        syntax_type=";",
        source_text=ctx.text_of(node) or ";",
    )


def _as_statement(ctx: _Context, node: Node) -> IrNode:
    if not node.is_named and node.type == ";":
        return _empty_statement(ctx, node)
    if node.type in {"block", "constructor_body"}:
        return _block(ctx, node)
    return _convert(ctx, node)


def _if(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    condition = cursor.take_field("condition")
    consequence = cursor.take_field("consequence")
    alternative = cursor.take_field("alternative")
    children: list[tuple[str, IrNode]] = []
    if condition is not None:
        children.append((ROLE_CONDITION, _convert(ctx, condition)))
    if consequence is not None:
        children.append((ROLE_BODY, _as_statement(ctx, consequence)))
    if alternative is not None:
        children.append((ROLE_ELSE, _as_statement(ctx, alternative)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.IF, children=children)


def _while(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    condition = cursor.take_field("condition")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if condition is not None:
        children.append((ROLE_CONDITION, _convert(ctx, condition)))
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.WHILE, children=children)


def _do(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    body = cursor.take_field("body")
    condition = cursor.take_field("condition")
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    if condition is not None:
        children.append((ROLE_CONDITION, _convert(ctx, condition)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.DO, children=children)


def _for(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    init = cursor.take_field("init")
    condition = cursor.take_field("condition")
    update = cursor.take_field("update")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if init is not None:
        children.append((ROLE_INIT, _as_statement(ctx, init)))
    if condition is not None:
        children.append((ROLE_CONDITION, _convert(ctx, condition)))
    if update is not None:
        children.append((ROLE_UPDATE, _convert(ctx, update)))
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.FOR, children=children)


def _enhanced_for(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    type_node = cursor.take_field("type")
    name_node = cursor.take_field("name")
    value = cursor.take_field("value")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if value is not None:
        children.append((ROLE_VALUE, _convert(ctx, value)))
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.ENHANCED_FOR,
        children=children,
        name=ctx.text_of(name_node),
        type_text=ctx.text_of(type_node),
    )


def _try(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(node, IrNodeKind.TRY, children=children)


def _try_with_resources(ctx: _Context, node: Node) -> IrNode:
    """try (Resource r = ...) { } catch/finally - ресурсы и тело сохраняются."""
    cursor = _Cursor(node)
    resources = cursor.take_field("resources")
    if resources is None:
        resources = next(
            (child for child in node.named_children if child.type == "resource_specification"),
            None,
        )
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if resources is not None:
        for resource in resources.named_children:
            if resource.type in {"resource", "local_variable_declaration"}:
                children.append((ROLE_RESOURCES, _convert(ctx, resource)))
            else:
                children.append((ROLE_CHILDREN, _convert(ctx, resource)))
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(node, IrNodeKind.TRY_WITH_RESOURCES, children=children)


def _catch(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    parameter = cursor.take_type("catch_formal_parameter")
    body = cursor.take_field("body")
    if body is None:
        body = cursor.take_type("block")
    children: list[tuple[str, IrNode]] = []
    if parameter is not None:
        children.append((ROLE_PARAMETERS, _catch_parameter(ctx, parameter)))
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.CATCH, children=children)


def _catch_parameter(ctx: _Context, node: Node) -> IrNode:
    name_node = node.child_by_field_name("name")
    type_node = next((child for child in node.named_children if child.type == "catch_type"), None)
    return ctx.make(
        node,
        IrNodeKind.PARAMETER,
        name=ctx.text_of(name_node),
        type_text=ctx.text_of(type_node),
    )


def _interface(ctx: _Context, node: Node) -> IrNode:
    return _type_declaration(ctx, node, IrNodeKind.INTERFACE)


def _enum(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    name_node = cursor.take_field("name")
    interfaces = cursor.take_field("interfaces")
    body = cursor.take_field("body")
    if body is None:
        body = next((child for child in node.named_children if child.type == "enum_body"), None)
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        cursor.mark(body)
        for member in body.named_children:
            if member.type == "enum_constant":
                children.append((ROLE_CHILDREN, _enum_constant(ctx, member)))
            elif member.type == "enum_body_declarations":
                for decl in member.named_children:
                    children.append((ROLE_CHILDREN, _convert(ctx, decl)))
            else:
                children.append((ROLE_CHILDREN, _convert(ctx, member)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        IrNodeKind.ENUM,
        children=children,
        name=ctx.text_of(name_node),
        modifiers_text=ctx.text_of(modifiers),
        interfaces_text=ctx.text_of(interfaces),
    )


def _enum_constant(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    name_node = cursor.take_field("name")
    if name_node is None:
        name_node = next((child for child in node.named_children if child.type == "identifier"), None)
    arguments = cursor.take_type("argument_list")
    body = cursor.take_type("class_body")
    children: list[tuple[str, IrNode]] = []
    if arguments is not None:
        for argument in arguments.named_children:
            children.append((ROLE_ARGUMENTS, _convert(ctx, argument)))
    if body is not None:
        for member in body.named_children:
            children.append((ROLE_CHILDREN, _convert(ctx, member)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.ENUM_CONSTANT,
        children=children,
        name=ctx.text_of(name_node),
    )


def _record(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    name_node = cursor.take_field("name")
    type_parameters = cursor.take_field("type_parameters")
    parameters = cursor.take_field("parameters")
    if parameters is None:
        parameters = next(
            (child for child in node.named_children if child.type == "formal_parameters"),
            None,
        )
    interfaces = cursor.take_field("interfaces")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if parameters is not None:
        children.extend(_parameters(ctx, parameters))
        cursor.mark(parameters)
    if body is not None:
        cursor.mark(body)
        for member in body.named_children:
            children.append((ROLE_CHILDREN, _convert(ctx, member)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        IrNodeKind.RECORD,
        children=children,
        name=ctx.text_of(name_node),
        modifiers_text=ctx.text_of(modifiers),
        type_parameters_text=ctx.text_of(type_parameters),
        interfaces_text=ctx.text_of(interfaces),
    )


def _compact_constructor(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    name_node = cursor.take_field("name")
    if name_node is None:
        name_node = next((child for child in node.named_children if child.type == "identifier"), None)
    body = cursor.take_field("body")
    if body is None:
        body = next((child for child in node.named_children if child.type == "block"), None)
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        children.append((ROLE_BODY, _block(ctx, body)))
        cursor.mark(body)
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.COMPACT_CONSTRUCTOR,
        children=children,
        name=ctx.text_of(name_node),
        modifiers_text=ctx.text_of(modifiers),
    )


def _formal_parameters(ctx: _Context, node: Node) -> IrNode:
    """Список формальных параметров (метод, лямбда, компоненты record)."""
    return ctx.make(node, IrNodeKind.FORMAL_PARAMETERS, children=_parameters(ctx, node))


def _type_declaration(ctx: _Context, node: Node, kind: IrNodeKind) -> IrNode:
    cursor = _Cursor(node)
    modifiers = cursor.take_type("modifiers")
    name_node = cursor.take_field("name")
    type_parameters = cursor.take_field("type_parameters")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        for member in body.named_children:
            children.append((ROLE_CHILDREN, _convert(ctx, member)))
    for extra in cursor.remaining_named():
        children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        kind,
        children=children,
        name=ctx.text_of(name_node),
        modifiers_text=ctx.text_of(modifiers),
        type_parameters_text=ctx.text_of(type_parameters),
    )


def _switch(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    condition = cursor.take_field("condition")
    if condition is None:
        condition = next(
            (child for child in node.named_children if child.type == "parenthesized_expression"),
            None,
        )
    body = cursor.take_field("body")
    if body is None:
        body = next((child for child in node.named_children if child.type == "switch_block"), None)
    children: list[tuple[str, IrNode]] = []
    if condition is not None:
        children.append((ROLE_CONDITION, _convert(ctx, condition)))
    if body is not None:
        for group in body.named_children:
            if group.type == "switch_block_statement_group":
                children.append((ROLE_CHILDREN, _switch_group(ctx, group)))
            else:
                children.append((ROLE_CHILDREN, _convert(ctx, group)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.SWITCH, children=children)


def _switch_group(ctx: _Context, node: Node) -> IrNode:
    children: list[tuple[str, IrNode]] = []
    labels: list[str] = []
    for child in node.named_children:
        if child.type == "switch_label":
            label_text = (ctx.text_of(child) or "case").strip()
            labels.append(label_text)
            children.append(("label", ctx.make(child, IrNodeKind.LITERAL, literal_kind="switch_label")))
        else:
            children.append((ROLE_CHILDREN, _as_statement(ctx, child)))
    label = " / ".join(labels) if labels else "case"
    return ctx.make(node, IrNodeKind.SWITCH_GROUP, children=children, label=label, name=label)


def _synchronized(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    lock_expr = next(
        (child for child in node.named_children if child.type == "parenthesized_expression"),
        None,
    )
    body = cursor.take_field("body")
    if body is None:
        body = next((child for child in node.named_children if child.type == "block"), None)
    children: list[tuple[str, IrNode]] = []
    if lock_expr is not None:
        children.append((ROLE_CONDITION, _convert(ctx, lock_expr)))
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.SYNCHRONIZED, children=children)


def _labeled(ctx: _Context, node: Node) -> IrNode:
    name_node = node.child_by_field_name("label")
    if name_node is None and node.named_children:
        name_node = node.named_children[0]
    body = None
    for child in node.named_children:
        if child is name_node:
            continue
        body = child
        break
    children: list[tuple[str, IrNode]] = []
    if body is not None:
        children.append((ROLE_BODY, _as_statement(ctx, body)))
    return ctx.make(
        node,
        IrNodeKind.LABELED,
        children=children,
        name=ctx.text_of(name_node),
        label=ctx.text_of(name_node),
    )


def _assert(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.ASSERT, children=children)


def _yield(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_VALUE, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.YIELD, children=children)


def _finally(ctx: _Context, node: Node) -> IrNode:
    block = next((child for child in node.named_children if child.type == "block"), None)
    children: list[tuple[str, IrNode]] = []
    if block is not None:
        children.append((ROLE_BODY, _block(ctx, block)))
    return ctx.make(node, IrNodeKind.FINALLY, children=children)


def _explicit_constructor_invocation(ctx: _Context, node: Node) -> IrNode:
    """this(...) / super(...) в начале конструктора."""
    cursor = _Cursor(node)
    arguments = cursor.take_field("arguments")
    children: list[tuple[str, IrNode]] = []
    if arguments is not None:
        for argument in arguments.named_children:
            children.append((ROLE_ARGUMENTS, _convert(ctx, argument)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    text = ctx.text_of(node).lstrip()
    name = "super" if text.startswith("super") else "this"
    return ctx.make(
        node,
        IrNodeKind.EXPLICIT_CONSTRUCTOR_INVOCATION,
        children=children,
        name=name,
    )


def _method_invocation(ctx: _Context, node: Node) -> IrNode:
    if any(child.type == "class_body" for child in node.children):
        return _unsupported(ctx, node)
    cursor = _Cursor(node)
    receiver = cursor.take_field("object")
    name_node = cursor.take_field("name")
    arguments = cursor.take_field("arguments")
    type_arguments = cursor.take_field("type_arguments")
    children: list[tuple[str, IrNode]] = []
    if receiver is not None:
        children.append((ROLE_OBJECT, _convert(ctx, receiver)))
    if arguments is not None:
        for argument in arguments.named_children:
            children.append((ROLE_ARGUMENTS, _convert(ctx, argument)))
    if type_arguments is not None:
        children.append((ROLE_CHILDREN, _unsupported(ctx, type_arguments)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.METHOD_INVOCATION,
        children=children,
        name=ctx.text_of(name_node),
    )


def _object_creation(ctx: _Context, node: Node) -> IrNode:
    if any(child.type == "class_body" for child in node.children):
        return _unsupported(ctx, node)
    cursor = _Cursor(node)
    type_node = cursor.take_field("type")
    arguments = cursor.take_field("arguments")
    type_arguments = cursor.take_field("type_arguments")
    children: list[tuple[str, IrNode]] = []
    if arguments is not None:
        for argument in arguments.named_children:
            children.append((ROLE_ARGUMENTS, _convert(ctx, argument)))
    if type_arguments is not None:
        children.append((ROLE_CHILDREN, _unsupported(ctx, type_arguments)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.OBJECT_CREATION,
        children=children,
        type_text=ctx.text_of(type_node),
    )


def _binary(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    left = cursor.take_field("left")
    operator = cursor.take_field("operator")
    right = cursor.take_field("right")
    if left is None or right is None:
        return _unsupported(ctx, node)
    children = [
        (ROLE_LEFT, _convert(ctx, left)),
        (ROLE_RIGHT, _convert(ctx, right)),
    ]
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.BINARY, children=children, operator=ctx.text_of(operator))


def _unary(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    operator = cursor.take_field("operator")
    operand = cursor.take_field("operand")
    if operand is None:
        return _unsupported(ctx, node)
    children = [(ROLE_VALUE, _convert(ctx, operand))]
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.UNARY, children=children, operator=ctx.text_of(operator))


def _update(ctx: _Context, node: Node) -> IrNode:
    operand: Node | None = None
    operator_node: Node | None = None
    for child in node.children:
        if child.type in _UPDATE_OPERATORS and operator_node is None:
            operator_node = child
        elif child.is_named and operand is None:
            operand = child
    if operand is None or operator_node is None:
        return _unsupported(ctx, node)
    operator = operator_node.type
    if operator_node.start_byte < operand.start_byte:
        operator = f"{operator}prefix"
    return ctx.make(
        node,
        IrNodeKind.UPDATE,
        children=[(ROLE_VALUE, _convert(ctx, operand))],
        operator=operator,
    )


def _parenthesized(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_VALUE, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.PARENTHESIZED, children=children)


def _lambda(ctx: _Context, node: Node) -> IrNode:
    """Лямбда: parameters + body (выражение или блок). java.util.function через типы вызова."""
    cursor = _Cursor(node)
    parameters = cursor.take_field("parameters")
    body = cursor.take_field("body")
    children: list[tuple[str, IrNode]] = []
    if parameters is not None:
        if parameters.type == "formal_parameters":
            children.extend(_parameters(ctx, parameters))
        elif parameters.type == "inferred_parameters":
            children.extend(_parameters(ctx, parameters))
        elif parameters.type == "identifier":
            children.append(
                (
                    ROLE_PARAMETERS,
                    ctx.make(parameters, IrNodeKind.PARAMETER, name=ctx.text_of(parameters)),
                )
            )
        else:
            children.append((ROLE_PARAMETERS, _convert(ctx, parameters)))
    if body is not None:
        if body.type == "block":
            children.append((ROLE_BODY, _block(ctx, body)))
        else:
            children.append((ROLE_BODY, _convert(ctx, body)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.LAMBDA, children=children)


def _method_reference(ctx: _Context, node: Node) -> IrNode:
    """Method reference: Type::method, obj::method, Type::new."""
    named = list(node.named_children)
    children: list[tuple[str, IrNode]] = []
    name: str | None = None
    if len(named) >= 2:
        children.append((ROLE_OBJECT, _convert(ctx, named[0])))
        name = ctx.text_of(named[-1])
        for extra in named[1:-1]:
            children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    elif named:
        name = ctx.text_of(named[0])
        children.append((ROLE_CHILDREN, _convert(ctx, named[0])))
    return ctx.make(
        node,
        IrNodeKind.METHOD_REFERENCE,
        children=children,
        name=name,
        operator="::",
    )


def _class_literal(ctx: _Context, node: Node) -> IrNode:
    """Class literal: String.class / int.class - база рефлексии."""
    type_node = next((child for child in node.named_children), None)
    children: list[tuple[str, IrNode]] = []
    if type_node is not None:
        children.append((ROLE_VALUE, _convert(ctx, type_node)))
    return ctx.make(
        node,
        IrNodeKind.CLASS_LITERAL,
        children=children,
        type_text=ctx.text_of(type_node),
        name=(ctx.text_of(type_node) or "") + ".class",
    )


def _inferred_parameters(ctx: _Context, node: Node) -> IrNode:
    return ctx.make(node, IrNodeKind.FORMAL_PARAMETERS, children=_parameters(ctx, node))


def _type_arguments(ctx: _Context, node: Node) -> IrNode:
    """Дженерик-аргументы <T, U>: текстовый узел + дочерние типы."""
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(
        node,
        IrNodeKind.LITERAL,
        children=children,
        literal_kind="type_arguments",
        type_text=ctx.text_of(node),
    )


def _type_parameters(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(
        node,
        IrNodeKind.LITERAL,
        children=children,
        literal_kind="type_parameters",
        type_text=ctx.text_of(node),
    )


def _field_access(ctx: _Context, node: Node) -> IrNode:
    """Доступ к полю: System.out, this.x, obj.field (база для Scanner/IO)."""
    cursor = _Cursor(node)
    obj = cursor.take_field("object")
    name_node = cursor.take_field("name")
    children: list[tuple[str, IrNode]] = []
    if obj is not None:
        children.append((ROLE_OBJECT, _convert(ctx, obj)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.FIELD_ACCESS,
        children=children,
        name=ctx.text_of(name_node),
    )


def _array_access(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    array = cursor.take_field("array")
    index = cursor.take_field("index")
    children: list[tuple[str, IrNode]] = []
    if array is not None:
        children.append((ROLE_OBJECT, _convert(ctx, array)))
    if index is not None:
        children.append((ROLE_INDEX, _convert(ctx, index)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.ARRAY_ACCESS, children=children)


def _array_creation(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    type_node = cursor.take_field("type")
    children: list[tuple[str, IrNode]] = []
    for extra in cursor.remaining_named():
        if extra.type == "dimensions" or extra.type.startswith("dimensions"):
            # Размерности: new int[n] / new int[][] - текст и выражения внутри.
            for dim_child in extra.named_children:
                children.append((ROLE_INDEX, _convert(ctx, dim_child)))
            children.append((ROLE_CHILDREN, _passthrough_text(ctx, extra)))
        elif extra.type == "array_initializer":
            children.append((ROLE_INIT, _array_initializer(ctx, extra)))
        else:
            children.append((ROLE_CHILDREN, _convert(ctx, extra)))
    return ctx.make(
        node,
        IrNodeKind.ARRAY_CREATION,
        children=children,
        type_text=ctx.text_of(type_node),
    )


def _array_initializer(ctx: _Context, node: Node) -> IrNode:
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.ARRAY_INITIALIZER, children=children)


def _passthrough_text(ctx: _Context, node: Node) -> IrNode:
    """Именованный узел без отдельной семантики: сохраняем срез, без unsupported."""
    return ctx.make(node, IrNodeKind.LITERAL, literal_kind=node.type)


def _passthrough_type(ctx: _Context, node: Node) -> IrNode:
    """Ссылка на тип (generic/array/примитив): имя в type_text, без unsupported."""
    return ctx.make(
        node,
        IrNodeKind.IDENTIFIER,
        name=ctx.text_of(node),
        type_text=ctx.text_of(node),
    )


def _resource(ctx: _Context, node: Node) -> IrNode:
    """Ресурс try-with-resources: объявление или выражение."""
    # Часто совпадает с local_variable_declaration по полям.
    if any(child.type == "variable_declarator" for child in node.named_children):
        return _declaration_with_declarators(ctx, node, IrNodeKind.LOCAL_VARIABLE)
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.LOCAL_VARIABLE, children=children)


def _passthrough_type(ctx: _Context, node: Node) -> IrNode:
    """Ссылка на тип (generic/array/примитив): имя в type_text, без unsupported."""
    return ctx.make(
        node,
        IrNodeKind.IDENTIFIER,
        name=ctx.text_of(node),
        type_text=ctx.text_of(node),
    )


def _resource(ctx: _Context, node: Node) -> IrNode:
    """Ресурс try-with-resources: объявление или выражение."""
    # Часто совпадает с local_variable_declaration по полям.
    if any(child.type == "variable_declarator" for child in node.named_children):
        return _declaration_with_declarators(ctx, node, IrNodeKind.LOCAL_VARIABLE)
    children = [(ROLE_CHILDREN, _convert(ctx, child)) for child in node.named_children]
    return ctx.make(node, IrNodeKind.LOCAL_VARIABLE, children=children)


def _cast(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    type_node = cursor.take_field("type")
    value = cursor.take_field("value")
    children: list[tuple[str, IrNode]] = []
    if value is not None:
        children.append((ROLE_VALUE, _convert(ctx, value)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.CAST,
        children=children,
        type_text=ctx.text_of(type_node),
    )


def _ternary(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    condition = cursor.take_field("condition")
    consequence = cursor.take_field("consequence")
    alternative = cursor.take_field("alternative")
    children: list[tuple[str, IrNode]] = []
    if condition is not None:
        children.append((ROLE_CONDITION, _convert(ctx, condition)))
    if consequence is not None:
        children.append((ROLE_VALUE, _convert(ctx, consequence)))
    if alternative is not None:
        children.append((ROLE_ALTERNATIVE, _convert(ctx, alternative)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(node, IrNodeKind.TERNARY, children=children)


def _instanceof(ctx: _Context, node: Node) -> IrNode:
    cursor = _Cursor(node)
    left = cursor.take_field("left")
    right = cursor.take_field("right")
    children: list[tuple[str, IrNode]] = []
    if left is not None:
        children.append((ROLE_LEFT, _convert(ctx, left)))
    if right is not None:
        # Тип или pattern: храним как value/type_text.
        if right.type in {
            "type_identifier",
            "scoped_type_identifier",
            "generic_type",
            "array_type",
            "integral_type",
            "floating_point_type",
            "boolean_type",
            "void_type",
        }:
            children.append(
                (
                    ROLE_VALUE,
                    ctx.make(right, IrNodeKind.IDENTIFIER, name=ctx.text_of(right), type_text=ctx.text_of(right)),
                )
            )
        else:
            children.append((ROLE_VALUE, _convert(ctx, right)))
    children.extend((ROLE_CHILDREN, _convert(ctx, extra)) for extra in cursor.remaining_named())
    return ctx.make(
        node,
        IrNodeKind.INSTANCEOF,
        children=children,
        type_text=ctx.text_of(right),
        operator="instanceof",
    )


_CONVERTERS = {
    "program": _program,
    "package_declaration": _package,
    "import_declaration": _import,
    "class_declaration": _class,
    "interface_declaration": _interface,
    "enum_declaration": _enum,
    "enum_constant": _enum_constant,
    "record_declaration": _record,
    "compact_constructor_declaration": _compact_constructor,
    "formal_parameters": _formal_parameters,
    "inferred_parameters": _inferred_parameters,
    "field_declaration": _field,
    "method_declaration": _method_declaration,
    "constructor_declaration": _constructor,
    "formal_parameter": _parameter,
    "local_variable_declaration": _local_variable,
    "block": _block,
    "constructor_body": _block,
    "expression_statement": _expression_statement,
    "assignment_expression": _assignment,
    "return_statement": _return,
    "break_statement": _break,
    "continue_statement": _continue,
    "throw_statement": _throw,
    "if_statement": _if,
    "while_statement": _while,
    "do_statement": _do,
    "for_statement": _for,
    "enhanced_for_statement": _enhanced_for,
    "try_statement": _try,
    "try_with_resources_statement": _try_with_resources,
    "resource": _resource,
    "catch_clause": _catch,
    "finally_clause": _finally,
    "switch_expression": _switch,
    "switch_statement": _switch,
    "synchronized_statement": _synchronized,
    "labeled_statement": _labeled,
    "assert_statement": _assert,
    "yield_statement": _yield,
    "method_invocation": _method_invocation,
    "explicit_constructor_invocation": _explicit_constructor_invocation,
    "object_creation_expression": _object_creation,
    "lambda_expression": _lambda,
    "method_reference": _method_reference,
    "class_literal": _class_literal,
    "type_arguments": _type_arguments,
    "type_parameters": _type_parameters,
    "field_access": _field_access,
    "array_access": _array_access,
    "array_creation_expression": _array_creation,
    "array_initializer": _array_initializer,
    "cast_expression": _cast,
    "ternary_expression": _ternary,
    "instanceof_expression": _instanceof,
    "binary_expression": _binary,
    "unary_expression": _unary,
    "update_expression": _update,
    "parenthesized_expression": _parenthesized,
    "identifier": _identifier,
    "this": _keyword_primary,
    "super": _keyword_primary,
    "line_comment": _comment,
    "block_comment": _comment,
    # Типы и имена в объявлениях/generics - текстовые листья, не unsupported.
    "type_identifier": _identifier,
    "scoped_type_identifier": _identifier,
    "generic_type": _passthrough_type,
    "array_type": _passthrough_type,
    "integral_type": _passthrough_type,
    "floating_point_type": _passthrough_type,
    "boolean_type": _passthrough_type,
    "void_type": _passthrough_type,
    "dimensions": _passthrough_text,
}

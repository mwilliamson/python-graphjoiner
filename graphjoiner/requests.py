from attr import attrs, attrib
from graphql.language import ast as ast_types


@attrs
class Request(object):
    key = attrib()
    field = attrib()
    args = attrib(default={})
    selections = attrib(default=[])
    join_selections = attrib(default=[])
    context = attrib(default=None)


def request_from_graphql_ast(ast, root, context, field=None):
    if isinstance(ast, ast_types.Field):
        key = field_key(ast)
    else:
        key = None
    
    args = dict(
        (argument.name.value, argument.value.value)
        for argument in getattr(ast, "arguments", {})
    )
    
    selections = _graphql_selections(ast, root, context=context)

    return Request(
        key=key,
        field=field,
        args=args,
        selections=selections,
        context=context,
    )


def _field_name(ast):
    return ast.name.value


def field_key(ast):
    if ast.alias is None:
        return _field_name(ast)
    else:
        return ast.alias.value


    
def _graphql_selections(ast, root, context):
    if ast.selection_set:
        fields = root.fields()
        return [
            _request_from_selection(selection, context=context, field=fields[_field_name(selection)])
            for selection in ast.selection_set.selections
        ]
    else:
        return []


def _request_from_selection(selection, field, context):
    return request_from_graphql_ast(
        selection,
        context=context,
        field=field,
        root=field._target,
    )
    

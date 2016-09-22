from attr import attrs, attrib
from graphql.language import ast as ast_types


@attrs
class Request(object):
    field_name = attrib()
    args = attrib(default={})
    selections = attrib(default=[])
    join_selections = attrib(default=[])
    context = attrib(default=None)


def request_from_graphql_ast(ast, context):
    if isinstance(ast, ast_types.Field):
        field_name = ast.name.value
    else:
        field_name = None
    
    args = dict(
        (argument.name.value, argument.value.value)
        for argument in getattr(ast, "arguments", {})
    )
    
    selections = _graphql_selections(ast, context=context)

    return Request(
        field_name=field_name,
        args=args,
        selections=selections,
        context=context,
    )
    
def _graphql_selections(ast, context):
    return [
        request_from_graphql_ast(selection, context=context)
        for selection in (ast.selection_set.selections if ast.selection_set else [])
    ]

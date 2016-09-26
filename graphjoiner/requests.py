from attr import attrs, attrib
from graphql.language import ast as ast_types
from graphql.execution.values import get_argument_values
from graphql.type.definition import GraphQLArgumentDefinition
import six


@attrs
class Request(object):
    key = attrib()
    field = attrib()
    args = attrib(default={})
    selections = attrib(default=[])
    join_selections = attrib(default=[])
    context = attrib(default=None)


def request_from_graphql_ast(ast, root, context, variables, field=None):
    if isinstance(ast, ast_types.Field):
        key = field_key(ast)
    else:
        key = None
    
    if field is None:
        args = {}
    else:
        arg_definitions = [
            GraphQLArgumentDefinition(
                type=arg.type,
                name=arg_name,
                default_value=arg.default_value,
                description=arg.description,
            )
            for arg_name, arg in six.iteritems(field.args)
        ]
        args = get_argument_values(arg_definitions, getattr(ast, "arguments", []), variables=variables)
    
    selections = _graphql_selections(ast, root, context=context, variables=variables)

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


    
def _graphql_selections(ast, root, context, variables):
    if ast.selection_set:
        fields = root.fields()
        return [
            _request_from_selection(selection, context=context, variables=variables, field=fields[_field_name(selection)])
            for selection in ast.selection_set.selections
        ]
    else:
        return []


def _request_from_selection(selection, field, context, variables):
    return request_from_graphql_ast(
        selection,
        context=context,
        variables=variables,
        field=field,
        root=field._target,
    )
    

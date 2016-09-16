from attr import attrs, attrib


@attrs
class Request(object):
    args = attrib()
    children = attrib()
    join_fields = attrib(default=[])
    context = attrib(default=None)

    @property
    def requested_fields(self):
        return self.children.keys()


def request_from_graphql_ast(ast, context):
    args = dict(
        (argument.name.value, argument.value.value)
        for argument in getattr(ast, "arguments", {})
    )
    
    children = _graphql_children(ast, context=context)
        
    return Request(
        args=args,
        children=children,
        context=context,
    )
    
def _graphql_children(ast, context):
    return dict(
        (selection.name.value, request_from_graphql_ast(selection, context=context))
        for selection in (ast.selection_set.selections if ast.selection_set else [])
    )

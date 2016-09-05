from attr import attrs, attrib


@attrs
class Request(object):
    args = attrib()
    children = attrib()
    join_fields = attrib(default=[])

    @property
    def requested_fields(self):
        return self.children.keys()


def request_from_graphql_ast(ast):
    args = dict(
        (argument.name.value, argument.value.value)
        for argument in getattr(ast, "arguments", {})
    )
    
    children = _graphql_children(ast)
        
    return Request(
        args,
        children,
    )
    
def _graphql_children(ast):
    return dict(
        (selection.name.value, request_from_graphql_ast(selection))
        for selection in (ast.selection_set.selections if ast.selection_set else [])
    )

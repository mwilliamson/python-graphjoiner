from graphql import build_ast_schema
from graphql.language.parser import parse


def parse_schema(document):
    return build_ast_schema(parse(document))

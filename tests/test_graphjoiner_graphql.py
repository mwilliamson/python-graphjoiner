from datetime import datetime

from attr import attrs, attrib
from graphql import graphql, GraphQLSchema, GraphQLInt, GraphQLString, GraphQLArgument

from graphjoiner import single, many, JoinType, RootJoinType, field
from .execution_test_cases import ExecutionTestCases


@attrs
class Book(object):
    id = attrib()
    title = attrib()
    author_id = attrib()


@attrs
class Author(object):
    id = attrib()
    name = attrib()


all_authors = [
    Author(1, "PG Wodehouse"),
    Author(2, "Joseph Heller"),
]

all_books = [
    Book(id=1, title="Leave It to Psmith", author_id=1),
    Book(id=2, title="Right Ho, Jeeves", author_id=1),
    Book(id=3, title="Catch-22", author_id=2),
]


def fetch_immediates_from_obj(request, objs):
    requested_fields = [
        (selection.key, selection.field.attr)
        for selection in request.selections
    ]
    
    def read_obj(obj):
        return dict((key, getattr(obj, attr)) for (key, attr) in requested_fields)
    
    return list(map(read_obj, objs))


def evaluate(func):
    return func()


@evaluate
def author_join_type():
    def fields():
        return {
            "id": field(attr="id", type=GraphQLInt),
            "name": field(attr="name", type=GraphQLString),
            "books": many(
                book_join_type,
                lambda *_: all_books,
                join={"id": "authorId"},
            ),
        }
    
    return JoinType(
        name="Author",
        fields=fields,
        fetch_immediates=fetch_immediates_from_obj,
    )


@evaluate
def book_join_type():
    def fields():
        return {
            "id": field(attr="id", type=GraphQLInt),
            "title": field(attr="title", type=GraphQLString),
            "authorId": field(attr="author_id", type=GraphQLInt),
            "author": single(
                author_join_type,
                lambda *_: all_authors,
                join={"authorId": "id"},
            ),
        }
    
    return JoinType(
        name="Book",
        fields=fields,
        fetch_immediates=fetch_immediates_from_obj,
    )


@evaluate
def root():
    def fields():
        return {
            "books": many(book_join_type, lambda *_: all_books),
            "author": single(author_join_type, author_query, args={"id": GraphQLArgument(type=GraphQLInt)}),
        }
    
    def author_query(request, _):
        authors = all_authors
        
        author_id = request.args.get("id")
        if author_id is not None:
            authors = list(filter(lambda author: author.id == int(author_id), authors))
        
        return authors
    
    return RootJoinType(
        name="Root",
        fields=fields,
    )


class TestGraphJoiner(ExecutionTestCases):
    def execute(self, query):
        schema = GraphQLSchema(
            query=root.to_graphql_type(),
        )
        
        result = graphql(schema, query)
        
        assert not result.errors
        return result.data

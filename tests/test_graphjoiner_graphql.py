from attr import attrs, attrib
from graphql import graphql, GraphQLSchema, GraphQLInt, GraphQLString, GraphQLArgument

from graphjoiner import single, many, extract, JoinType, RootJoinType, field
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


def fetch_immediates_from_obj(selections, objs, context):
    requested_attrs = [
        selection.field.attr
        for selection in selections
    ]

    def read_obj(obj):
        return [getattr(obj, attr) for attr in requested_attrs]

    return list(map(read_obj, objs))


def evaluate(func):
    return func()


@evaluate
def author_join_type():
    def fields():
        books = many(
            book_join_type,
            lambda *_: all_books,
            join={"id": "authorId"},
        )
        return {
            "id": field(attr="id", type=GraphQLInt),
            "name": field(attr="name", type=GraphQLString),
            "books": books,
            "bookTitles": extract(books, "title"),
        }

    return JoinType(
        name="Author",
        fields=fields,
        fetch_immediates=fetch_immediates_from_obj,
    )


@evaluate
def book_join_type():
    def fields():
        author = single(
            author_join_type,
            lambda *_: all_authors,
            join={"authorId": "id"},
        )

        return {
            "id": field(attr="id", type=GraphQLInt),
            "title": field(attr="title", type=GraphQLString),
            "authorId": field(attr="author_id", type=GraphQLInt),
            "author": author,
            "booksBySameAuthor": extract(author, "books"),
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
            "book": single(book_join_type, book_query, args={"id": GraphQLArgument(type=GraphQLInt)}),
            "author": single(author_join_type, author_query, args={"id": GraphQLArgument(type=GraphQLInt)}),
        }

    def book_query(args, _, context):
        books = all_books

        book_id = args.get("id")
        if book_id is not None:
            books = list(filter(lambda book: book.id == book_id, books))

        return books

    def author_query(args, _, context):
        authors = all_authors

        author_id = args.get("id")
        if author_id is not None:
            authors = list(filter(lambda author: author.id == author_id, authors))

        return authors

    return RootJoinType(
        name="Root",
        fields=fields,
    )


class TestGraphJoiner(ExecutionTestCases):
    def execute(self, query, variables=None):
        schema = GraphQLSchema(
            query=root.to_graphql_type(),
        )

        result = graphql(schema, query, variable_values=variables)

        return result

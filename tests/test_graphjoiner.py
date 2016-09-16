from datetime import datetime

from attr import attrs, attrib

from graphjoiner import execute, single, many, ObjectType, RootObjectType
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


class AuthorObjectType(ObjectType):
    @staticmethod
    def fields():
        return {
            "id": "id",
            "name": "name",
            "books": many(
                BookObjectType,
                lambda *_: all_books,
                join={"id": "authorId"},
            ),
        }
    
    def fetch_immediates(self, request, authors):
        requested_attrs = [self.fields()[field] for field in request.requested_fields]
        
        def read_author(author):
            return dict((attr, getattr(author, attr)) for attr in requested_attrs)
        
        return list(map(read_author, authors))


class BookObjectType(ObjectType):
    @staticmethod
    def fields():
        return {
            "id": "id",
            "title": "title",
            "authorId": "author_id",
            "author": single(
                AuthorObjectType,
                lambda *_: all_authors,
                join={"authorId": "id"},
            ),
        }
    
    def fetch_immediates(self, request, books):
        def read_book(book):
            return dict(
                (field, getattr(book, self.fields()[field]))
                for field in request.requested_fields
            )
        
        return list(map(read_book, books))


class Root(RootObjectType):
    @classmethod
    def fields(cls):
        return {
            "books": many(BookObjectType, lambda *_: all_books),
            "author": single(AuthorObjectType, cls._author_query),
        }
    
    @classmethod
    def _author_query(cls, request, _):
        authors = all_authors
        
        author_id = request.args.get("id")
        if author_id is not None:
            authors = list(filter(lambda author: author.id == int(author_id), authors))
        
        return authors


class Tests(ExecutionTestCases):
    def execute(self, query):
        return execute(Root(), query)

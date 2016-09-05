from datetime import datetime

from attr import attrs, attrib
from hamcrest import assert_that, equal_to

from graphjoiner import execute, single, many, Entity, RootEntity


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


class AuthorEntity(Entity):
    @staticmethod
    def fields():
        return {
            "id": "id",
            "name": "name",
            "books": many(
                BookEntity,
                lambda *_: all_books,
                join={"id": "authorId"},
            ),
        }
    
    def generate_context(self, request, authors):
        author_id = request.args.get("id")
        if author_id is not None:
            authors = list(filter(lambda author: author.id == int(author_id), authors))
        
        return authors
    
    def fetch_immediates(self, request, authors):
        requested_attrs = [self.fields()[field] for field in request.requested_fields]
        
        def read_author(author):
            return dict((attr, getattr(author, attr)) for attr in requested_attrs)
        
        return list(map(read_author, authors))


class BookEntity(Entity):
    @staticmethod
    def fields():
        return {
            "id": "id",
            "title": "title",
            "authorId": "author_id",
            "author": single(
                AuthorEntity,
                lambda *_: all_authors,
                join={"authorId": "id"},
            ),
        }
    
    def generate_context(self, request, books):
        return books
    
    def fetch_immediates(self, request, books):
        def read_book(book):
            return dict(
                (field, getattr(book, self.fields()[field]))
                for field in request.requested_fields
            )
        
        return list(map(read_book, books))


class Root(RootEntity):
    @staticmethod
    def fields():
        return {
            "books": many(BookEntity, lambda *_: all_books),
            "author": single(AuthorEntity, lambda *_: all_authors),
        }
    

def test_querying_list_of_entities():
    query = """
        {
            books {
                id
                title
            }
        }
    """
    
    result = execute(Root(), query)
    
    assert_that(result, equal_to({
        "books": [
            {
                "id": 1,
                "title": "Leave It to Psmith",
            },
            {
                "id": 2,
                "title": "Right Ho, Jeeves",
            },
            {
                "id": 3,
                "title": "Catch-22",
            },
        ]
    }))
    

def test_querying_list_of_entities_with_child_entity():
    query = """
        {
            books {
                id
                author {
                    name
                }
            }
        }
    """
    
    result = execute(Root(), query)
    
    assert_that(result, equal_to({
        "books": [
            {
                "id": 1,
                "author": {
                    "name": "PG Wodehouse",
                },
            },
            {
                "id": 2,
                "author": {
                    "name": "PG Wodehouse",
                },
            },
            {
                "id": 3,
                "author": {
                    "name": "Joseph Heller",
                },
            },
        ]
    }))

    
def test_querying_single_entity_with_arg():
    query = """
        {
            author(id: 1) {
                name
            }
        }
    """
    
    result = execute(Root(), query)
    
    assert_that(result, equal_to({
        "author": {
            "name": "PG Wodehouse",
        },
    }))

    
def test_single_entity_is_null_if_not_found():
    query = """
        {
            author(id: 100) {
                name
            }
        }
    """
    
    result = execute(Root(), query)
    
    assert_that(result, equal_to({
        "author": None,
    }))


    
def test_querying_single_entity_with_child_entities():
    query = """
        {
            author(id: 1) {
                books {
                    title
                }
            }
        }
    """
    
    result = execute(Root(), query)
    
    assert_that(result, equal_to({
        "author": {
            "books": [
                {"title": "Leave It to Psmith"},
                {"title": "Right Ho, Jeeves"},
            ],
        },
    }))

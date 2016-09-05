from datetime import datetime

import pytest
from hamcrest import assert_that, equal_to
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from graphjoiner import execute, single, many, Entity, RootEntity


Base = declarative_base()

class Author(Base):
    __tablename__ = "author"
    
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)

class Book(Base):
    __tablename__ = "book"
    
    id = Column(Integer, primary_key=True)
    title = Column(Unicode, nullable=False)
    author_id = Column(Integer, ForeignKey(Author.id))


class DatabaseEntity(Entity):
    def __init__(self, session):
        super(DatabaseEntity, self).__init__(session)
        self._session = session
        
    def fetch_immediates(self, request, query):
        query = query.with_entities(*(
            self.fields[field]
            for field in request.requested_fields
        ))
        
        return [
            dict(zip(request.requested_fields, row))
            for row in query.with_session(self._session).all()
        ]

def _author_to_book_context(request, author_query):
    authors = author_query.with_entities(Author.id).distinct().subquery()
    return Query([]) \
        .select_from(Book) \
        .join(authors, authors.c.id == Book.author_id)
        
class AuthorEntity(DatabaseEntity):
    fields = {
        "id": "id",
        "name": "name",
        "books": many(
            lambda: BookEntity,
            join={"id": "authorId"},
            generate_context=_author_to_book_context,
        ),
    }
    
    def generate_context(self, request, query):
        if query is None:
            query = Query([]).select_from(Author)
        
        author_id = request.args.get("id")
        if author_id is not None:
            query = query.filter(Author.id == author_id)
        
        return query


def _book_to_author_context(request, book_query):
    books = book_query.with_entities(Book.author_id).distinct().subquery()
    return Query([]) \
        .select_from(Author) \
        .join(books, books.c.author_id == Author.id)


class BookEntity(DatabaseEntity):
    fields = {
        "id": "id",
        "title": "title",
        "authorId": "author_id",
        "author": single(
            AuthorEntity,
            join={"authorId": "id"},
            generate_context=_book_to_author_context,
        ),
    }
    
    def generate_context(self, request, query):
        if query is None:
            query = self._session.query().select_from(Book)
            
        return query
    

class Root(RootEntity):
    fields = {
        "books": many(BookEntity),
        "author": single(AuthorEntity),
    }
    

def test_querying_list_of_entities(session):
    query = """
        {
            books {
                id
                title
            }
        }
    """
    
    result = execute(Root(session), query)
    
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
    

def test_querying_list_of_entities_with_child_entity(session):
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
    
    result = execute(Root(session), query)
    
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

    
def test_querying_single_entity_with_arg(session):
    query = """
        {
            author(id: 1) {
                name
            }
        }
    """
    
    result = execute(Root(session), query)
    
    assert_that(result, equal_to({
        "author": {
            "name": "PG Wodehouse",
        },
    }))

    
def test_single_entity_is_null_if_not_found(session):
    query = """
        {
            author(id: 100) {
                name
            }
        }
    """
    
    result = execute(Root(session), query)
    
    assert_that(result, equal_to({
        "author": None,
    }))


    
def test_querying_single_entity_with_child_entities(session):
    query = """
        {
            author(id: 1) {
                books {
                    title
                }
            }
        }
    """
    
    result = execute(Root(session), query)
    
    assert_that(result, equal_to({
        "author": {
            "books": [
                {"title": "Leave It to Psmith"},
                {"title": "Right Ho, Jeeves"},
            ],
        },
    }))


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    session = Session(engine)
    session.add(Author(name="PG Wodehouse"))
    session.add(Author(name="Joseph Heller"))
    session.add(Book(title="Leave It to Psmith", author_id=1))
    session.add(Book(title="Right Ho, Jeeves", author_id=1))
    session.add(Book(title="Catch-22", author_id=2))

    session.commit()
    
    return session

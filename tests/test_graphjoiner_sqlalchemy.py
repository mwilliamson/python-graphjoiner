from datetime import datetime

import pytest
from hamcrest import assert_that, equal_to
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

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
    def fetch_immediates(self, request):
        query = request.context.add_columns(*(
            self.fields[field]
            for field in request.requested_fields
        ))
        
        return [
            dict(zip(request.requested_fields, row))
            for row in query.all()
        ]

        
class AuthorEntity(DatabaseEntity):
    def __init__(self, session):
        super(AuthorEntity, self).__init__(session)
        self._session = session
        
    fields = {
        "id": "id",
        "name": "name",
        "books": many(lambda: BookEntity, join={"id": "authorId"}),
    }
    
    def generate_context(self, request):
        query = request.context
        if query is None:
            query = self._session.query().select_from(Author)
        
        author_id = request.args.get("id")
        if author_id is not None:
            query = query.filter(Author.id == author_id)
        
        return query


class BookEntity(DatabaseEntity):
    def __init__(self, session):
        super(BookEntity, self).__init__(session)
        self._session = session
    
    fields = {
        "id": "id",
        "title": "title",
        "authorId": "author_id",
        "author": single(AuthorEntity, join={"authorId": "id"}),
    }
    
    def generate_context(self, request):
        query = request.context
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

from datetime import datetime

from graphql import GraphQLInt, GraphQLString
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from graphjoiner import execute, single, many, JoinType, RootJoinType, field
from .execution_test_cases import ExecutionTestCases


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


class DatabaseJoinType(JoinType):
    def __init__(self, session):
        super(DatabaseJoinType, self).__init__(session)
        self._session = session
        
    def fetch_immediates(self, request, query):
        query = query.with_entities(*(
            self.fields()[field].column_name
            for field in request.requested_fields
        ))
        
        return [
            dict(zip(request.requested_fields, row))
            for row in query.with_session(self._session).all()
        ]
        
        
class AuthorJoinType(DatabaseJoinType):
    @classmethod
    def fields(cls):
        return {
            "id": field(column_name="id", type=GraphQLInt),
            "name": field(column_name="name", type=GraphQLString),
            "books": many(
                BookJoinType,
                cls._book_query,
                join={"id": "authorId"},
            ),
        }

    @classmethod
    def _book_query(cls, request, author_query):
        authors = author_query.with_entities(Author.id).distinct().subquery()
        return Query([]) \
            .select_from(Book) \
            .join(authors, authors.c.id == Book.author_id)


class BookJoinType(DatabaseJoinType):
    @classmethod
    def fields(cls):
        return {
            "id": field(column_name="id", type=GraphQLInt),
            "title": field(column_name="title", type=GraphQLString),
            "authorId": field(column_name="author_id", type=GraphQLInt),
            "author": single(
                AuthorJoinType,
                cls._author_query,
                join={"authorId": "id"},
            ),
        }
    
    @classmethod
    def _author_query(cls, request, book_query):
        books = book_query.with_entities(Book.author_id).distinct().subquery()
        return Query([]) \
            .select_from(Author) \
            .join(books, books.c.author_id == Author.id)
    

class Root(RootJoinType):
    @classmethod
    def fields(cls):
        return {
            "books": many(BookJoinType, lambda *_: Query([]).select_from(Book)),
            "author": single(AuthorJoinType, cls._author_query),
        }
    
    @classmethod
    def _author_query(cls, request, _):
        query = Query([]).select_from(Author)
        
        author_id = request.args.get("id")
        if author_id is not None:
            query = query.filter(Author.id == author_id)
        
        return query
    

class TestGraphJoinerSqlAlchemy(ExecutionTestCases):
    def execute(self, query):
        engine = create_engine("sqlite:///:memory:")

        Base.metadata.create_all(engine)

        session = Session(engine)
        session.add(Author(name="PG Wodehouse"))
        session.add(Author(name="Joseph Heller"))
        session.add(Book(title="Leave It to Psmith", author_id=1))
        session.add(Book(title="Right Ho, Jeeves", author_id=1))
        session.add(Book(title="Catch-22", author_id=2))

        session.commit()
        
        return execute(Root(session), query)

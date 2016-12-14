from datetime import datetime

from graphql import GraphQLInt, GraphQLString, GraphQLArgument
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from graphjoiner.declarative import executor, extract, field, single, many, root_join_type
from graphjoiner.declarative.sqlalchemy import sqlalchemy_join_type
from .execution_test_cases import ExecutionTestCases


Base = declarative_base()

class AuthorRecord(Base):
    __tablename__ = "author"

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)

class BookRecord(Base):
    __tablename__ = "book"

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, nullable=False)
    author_id = Column(Integer, ForeignKey(AuthorRecord.id))


class QueryContext(object):
    def __init__(self, session):
        self.session = session


def evaluate(func):
    return func()


@sqlalchemy_join_type(AuthorRecord)
class Author(object):
    id = field(column=AuthorRecord.id)
    name = field(column=AuthorRecord.name)
    books = lambda: many(Book)
    book_titles = lambda: extract(books, "title")


@sqlalchemy_join_type(BookRecord)
class Book(object):
    id = field(column=BookRecord.id)
    title = field(column=BookRecord.title)
    author_id = field(column=BookRecord.author_id)
    author = single(Author)
    books_by_same_author = extract(author, "books")


@root_join_type
class Root(object):
    books = many(Book)
    book = single(Book)
    
    @book.arg("id", GraphQLInt)
    def book_id(query, book_id):
        return query.filter(BookRecord.id == book_id)
    
    author = single(Author)
    
    @author.arg("id", GraphQLInt)
    def author_id(query, author_id):
        return query.filter(AuthorRecord.id == author_id)


class TestGraphJoinerSqlAlchemy(ExecutionTestCases):
    def execute(self, query, **kwargs):
        engine = create_engine("sqlite:///:memory:")

        Base.metadata.create_all(engine)

        session = Session(engine)
        session.add(AuthorRecord(name="PG Wodehouse"))
        session.add(AuthorRecord(name="Joseph Heller"))
        session.add(BookRecord(title="Leave It to Psmith", author_id=1))
        session.add(BookRecord(title="Right Ho, Jeeves", author_id=1))
        session.add(BookRecord(title="Catch-22", author_id=2))

        session.commit()
        
        execute = executor(Root)

        return execute(query, context=QueryContext(session), **kwargs)

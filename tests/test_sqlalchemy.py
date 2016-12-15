from datetime import datetime

from graphql import GraphQLInt, GraphQLString, GraphQLArgument
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from graphjoiner.declarative import executor, extract, field, single, many, root_join_type, lazy_field
from graphjoiner.declarative.sqlalchemy import sqlalchemy_join_type
from .execution_test_cases import ExecutionTestCases


Base = declarative_base()

class AuthorRecord(Base):
    __tablename__ = "author"

    c_id = Column(Integer, primary_key=True)
    c_name = Column(Unicode, nullable=False)

class BookRecord(Base):
    __tablename__ = "book"

    c_id = Column(Integer, primary_key=True)
    c_title = Column(Unicode, nullable=False)
    c_author_id = Column(Integer, ForeignKey(AuthorRecord.c_id))


class QueryContext(object):
    def __init__(self, session):
        self.session = session


def evaluate(func):
    return func()


@sqlalchemy_join_type(AuthorRecord)
class Author(object):
    id = field(column=AuthorRecord.c_id)
    name = field(column=AuthorRecord.c_name)
    books = lazy_field(lambda: many(Book))
    book_titles = extract(books, "title")


@sqlalchemy_join_type(BookRecord)
class Book(object):
    id = field(column=BookRecord.c_id)
    title = field(column=BookRecord.c_title)
    author_id = field(column=BookRecord.c_author_id)
    author = single(Author)
    books_by_same_author = extract(author, "books")


@root_join_type
class Root(object):
    books = many(Book)
    book = single(Book)
    
    @book.arg("id", GraphQLInt)
    def book_id(query, book_id):
        return query.filter(BookRecord.c_id == book_id)
    
    author = single(Author)
    
    @author.arg("id", GraphQLInt)
    def author_id(query, author_id):
        return query.filter(AuthorRecord.c_id == author_id)


class TestGraphJoinerSqlAlchemy(ExecutionTestCases):
    def execute(self, query, **kwargs):
        engine = create_engine("sqlite:///:memory:")

        Base.metadata.create_all(engine)

        session = Session(engine)
        session.add(AuthorRecord(c_name="PG Wodehouse"))
        session.add(AuthorRecord(c_name="Joseph Heller"))
        session.add(BookRecord(c_title="Leave It to Psmith", c_author_id=1))
        session.add(BookRecord(c_title="Right Ho, Jeeves", c_author_id=1))
        session.add(BookRecord(c_title="Catch-22", c_author_id=2))

        session.commit()
        
        execute = executor(Root)

        return execute(query, context=QueryContext(session), **kwargs)

from datetime import datetime

from graphql import GraphQLInt, GraphQLString, GraphQLArgument
from hamcrest import assert_that, equal_to
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from graphjoiner.declarative import executor, extract, field, single, many, root_type, lazy_field, object_type
from graphjoiner.declarative.sqlalchemy import sqlalchemy_object_type
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
    def __init__(self, session, api):
        self.session = session
        self.api = api


def evaluate(func):
    return func()


@sqlalchemy_object_type(AuthorRecord)
class Author(object):
    id = field(column=AuthorRecord.c_id)
    name = field(column=AuthorRecord.c_name)
    books = lazy_field(lambda: many(Book))
    book_titles = extract(books, "title")


@sqlalchemy_object_type(BookRecord)
class Book(object):
    id = field(column=BookRecord.c_id)
    title = field(column=BookRecord.c_title)
    author_id = field(column=BookRecord.c_author_id)
    author = single(Author)
    books_by_same_author = extract(author, "books")

    sales = lazy_field(lambda: single(Sales, {Book.title: Sales.book_title}))


@object_type
class Sales(object):
    book_title = field(property_name="title", type=GraphQLString)
    quantity = field(property_name="quantity", type=GraphQLInt)
    
    @staticmethod
    def __fetch_immediates__(selections, values, context):
        sales = context.api.fetch_sales(titles=[value.book_title for value in values])
        return (
            tuple(sale[selection.field.property_name] for selection in selections)
            for sale in sales
        )


@root_type
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


def execute(query, **kwargs):
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

    class Api(object):
        _sales = {
            "Leave It to Psmith": 416,
            "Right Ho, Jeeves": 44,
            "Catch-22": 53,
        }
        
        def fetch_sales(self, titles):
            return [
                {"title": title, "quantity": self._sales.get(title)}
                for title in titles
            ]

    return execute(query, context=QueryContext(session=session, api=Api()), **kwargs)


class TestGraphJoinerSqlAlchemy(ExecutionTestCases):
    def execute(self, *args, **kwargs):
        return execute(*args, **kwargs)


def test_can_join_across_types():
    query = """
        {
            book(id: 1) {
                sales {
                    quantity
                }
            }
        }
    """

    result = execute(query)

    assert_that(result, equal_to({
        "book": {
            "sales": {
                "quantity": 416,
            },
        },
    }))

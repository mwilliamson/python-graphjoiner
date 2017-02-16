import graphql
from hamcrest import assert_that, contains_inanyorder, equal_to, has_entries
import pytest
import sqlalchemy
from sqlalchemy import create_engine, Column, ForeignKey, Integer, literal, Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session

from graphjoiner.declarative import executor, field, many, RootType
from graphjoiner.declarative.sqlalchemy import (
    SqlAlchemyObjectType,
    select,
    sql_join,
    _find_join_candidates,
    _sql_type_to_graphql_type,
)
from ..matchers import is_successful_result


def test_can_explicitly_set_join_condition_with_single_field_between_sqlalchemy_objects():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"

        c_id = Column(Integer, primary_key=True)
        c_name = Column(Unicode, nullable=False)

    class BookRecord(Base):
        __tablename__ = "book"

        c_id = Column(Integer, primary_key=True)
        c_title = Column(Unicode, nullable=False)
        c_author_id = Column(Integer)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        id = field(column=AuthorRecord.c_id)
        name = field(column=AuthorRecord.c_name)
        books = many(lambda: sql_join(Book, join={Author.id: Book.author_id}))

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = field(column=BookRecord.c_id)
        title = field(column=BookRecord.c_title)
        author_id = field(column=BookRecord.c_author_id)

    class Root(RootType):
        authors = many(lambda: select(Author))

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    session = Session(engine)
    session.add(AuthorRecord(c_name="PG Wodehouse"))
    session.add(AuthorRecord(c_name="Joseph Heller"))
    session.add(BookRecord(c_title="Leave It to Psmith", c_author_id=1))
    session.add(BookRecord(c_title="Catch-22", c_author_id=2))
    session.commit()

    result = executor(Root)("""{
        authors {
            name
            books { title }
        }
    }""", context=QueryContext(session=session))
    assert_that(result, is_successful_result(data={
        "authors": [
            {"name": "PG Wodehouse", "books": [{"title": "Leave It to Psmith"}]},
            {"name": "Joseph Heller", "books": [{"title": "Catch-22"}]},
        ],
    }))


def test_can_explicitly_set_join_condition_with_multiple_fields_between_sqlalchemy_objects():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"

        c_id_1 = Column(Integer, primary_key=True)
        c_id_2 = Column(Integer, primary_key=True)
        c_name = Column(Unicode, nullable=False)

    class BookRecord(Base):
        __tablename__ = "book"

        c_id = Column(Integer, primary_key=True)
        c_title = Column(Unicode, nullable=False)
        c_author_id_1 = Column(Integer)
        c_author_id_2 = Column(Integer)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        id_1 = field(column=AuthorRecord.c_id_1)
        id_2 = field(column=AuthorRecord.c_id_2)
        name = field(column=AuthorRecord.c_name)
        books = many(lambda: sql_join(Book, join={
            Author.id_1: Book.author_id_1,
            Author.id_2: Book.author_id_2,
        }))

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = field(column=BookRecord.c_id)
        title = field(column=BookRecord.c_title)
        author_id_1 = field(column=BookRecord.c_author_id_1)
        author_id_2 = field(column=BookRecord.c_author_id_2)

    class Root(RootType):
        authors = many(lambda: select(Author))

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    session = Session(engine)
    wodehouse = AuthorRecord(c_name="PG Wodehouse", c_id_1=1, c_id_2=11)
    heller = AuthorRecord(c_name="Joseph Heller", c_id_1=2, c_id_2=12)
    session.add(wodehouse)
    session.add(heller)
    session.flush()
    session.add(BookRecord(c_title="Leave It to Psmith", c_author_id_1=wodehouse.c_id_1, c_author_id_2=wodehouse.c_id_2))
    session.add(BookRecord(c_title="Catch-22", c_author_id_1=heller.c_id_1, c_author_id_2=heller.c_id_2))
    session.commit()

    result = executor(Root)("""{
        authors {
            name
            books { title }
        }
    }""", context=QueryContext(session=session))
    assert_that(result, is_successful_result(data={
        "authors": [
            {"name": "PG Wodehouse", "books": [{"title": "Leave It to Psmith"}]},
            {"name": "Joseph Heller", "books": [{"title": "Catch-22"}]},
        ],
    }))


def test_hybrid_properties_are_ignored_when_scanning_for_foreign_keys():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"

        c_id = Column(Integer, primary_key=True)

    class BookRecord(Base):
        __tablename__ = "book"

        c_id = Column(Integer, primary_key=True)

        @hybrid_property
        def c_title(self):
            return literal("<title>")

        c_author_id = Column(Integer, ForeignKey(AuthorRecord.c_id))

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        id = field(column=AuthorRecord.c_id)

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = field(column=BookRecord.c_id)
        title = field(column=BookRecord.c_title)
        author_id = field(column=BookRecord.c_author_id)

    assert_that(
        list(_find_join_candidates(Author, Book)),
        equal_to([(Author.__dict__["id"], Book.__dict__["author_id"])]),
    )


def test_can_explicitly_set_primary_key():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"

        c_id = Column(Integer, primary_key=True)
        c_name = Column(Unicode, nullable=False)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        @staticmethod
        def __primary_key__():
            return [AuthorRecord.c_name]

        name = field(column=AuthorRecord.c_name)

    class Root(RootType):
        authors = many(lambda: select(Author))

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    session = Session(engine)
    session.add(AuthorRecord(c_name="PG Wodehouse"))
    session.add(AuthorRecord(c_name="PG Wodehouse"))
    session.add(AuthorRecord(c_name="Joseph Heller"))
    session.commit()

    result = executor(Root)("""{
        authors {
            name
        }
    }""", context=QueryContext(session=session))
    assert_that(result, is_successful_result(data=has_entries({
        "authors": contains_inanyorder(
            {"name": "PG Wodehouse"},
            {"name": "Joseph Heller"},
        ),
    })))


def test_type_of_field_is_determined_from_type_of_column():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"
        c_id = Column(Integer, primary_key=True)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        id = field(column=AuthorRecord.c_id)

    assert_that(Author.id.type, equal_to(graphql.GraphQLInt))


def test_type_of_field_can_be_explicitly_set():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"
        c_id = Column(Integer, primary_key=True)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        id = field(column=AuthorRecord.c_id, type=graphql.GraphQLString)

    assert_that(Author.id.type, equal_to(graphql.GraphQLString))


@pytest.mark.parametrize("sql_type, graphql_type", [
    (sqlalchemy.Integer(), graphql.GraphQLInt),
    (sqlalchemy.Float(), graphql.GraphQLFloat),
    (sqlalchemy.String(), graphql.GraphQLString),
    (sqlalchemy.Unicode(), graphql.GraphQLString),
    (sqlalchemy.Boolean(), graphql.GraphQLBoolean),
])
def test_type_mappings(sql_type, graphql_type):
    assert_that(_sql_type_to_graphql_type(sql_type), equal_to(graphql_type))


class QueryContext(object):
    def __init__(self, session):
        self.session = session

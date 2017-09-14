import graphql
from hamcrest import all_of, assert_that, contains_inanyorder, equal_to, has_entries, has_properties, has_string, instance_of, starts_with
import pytest
import sqlalchemy
from sqlalchemy import create_engine, Column, ForeignKey, Integer, literal, String, Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session

from graphjoiner.declarative import executor, many, RootType, select
from graphjoiner.declarative.sqlalchemy import (
    SqlAlchemyObjectType,
    column_field,
    sql_join,
    _find_join_candidates,
    _sql_column_to_graphql_type,
)
from ..matchers import is_invalid_result, is_successful_result


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

        id = column_field(AuthorRecord.c_id)
        name = column_field(AuthorRecord.c_name)
        books = many(lambda: sql_join(Book, join={Author.id: Book.author_id}))

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = column_field(BookRecord.c_id)
        title = column_field(BookRecord.c_title)
        author_id = column_field(BookRecord.c_author_id)

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

        id_1 = column_field(AuthorRecord.c_id_1)
        id_2 = column_field(AuthorRecord.c_id_2)
        name = column_field(AuthorRecord.c_name)
        books = many(lambda: sql_join(Book, join={
            Author.id_1: Book.author_id_1,
            Author.id_2: Book.author_id_2,
        }))

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = column_field(BookRecord.c_id)
        title = column_field(BookRecord.c_title)
        author_id_1 = column_field(BookRecord.c_author_id_1)
        author_id_2 = column_field(BookRecord.c_author_id_2)

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


def test_can_explicitly_set_join_query_between_sqlalchemy_objects():
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

        id = column_field(AuthorRecord.c_id)
        name = column_field(AuthorRecord.c_name)

        @staticmethod
        def _author_to_books(author_query, book_query):
            authors = author_query.add_columns(AuthorRecord.c_id).subquery()
            return book_query \
                .join(authors, authors.c.c_id == BookRecord.c_author_id)

        books = many(lambda: select(
            Book,
            join_query=Author._author_to_books,
            join_fields={Author.id: Book.author_id},
        ))

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = column_field(BookRecord.c_id)
        title = column_field(BookRecord.c_title)
        author_id = column_field(BookRecord.c_author_id)

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

        name = column_field(AuthorRecord.c_name)

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


def test_polymorphic_type_is_filtered_by_discriminator_when_there_are_no_polymorphic_fields_selected():
    Base = declarative_base()

    class PersonRecord(Base):
        __tablename__ = "person"

        c_id = Column(Integer, primary_key=True)
        c_discriminator = Column("type", String(50), nullable=False)

        __mapper_args__ = {"polymorphic_on": c_discriminator}

    class AuthorRecord(PersonRecord):
        __mapper_args__ = {"polymorphic_identity": "author"}

    class ReaderRecord(PersonRecord):
        __mapper_args__ = {"polymorphic_identity": "reader"}

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        id = column_field(PersonRecord.c_id)

    class Reader(SqlAlchemyObjectType):
        __model__ = ReaderRecord

        id = column_field(PersonRecord.c_id)

    class Root(RootType):
        authors = many(lambda: select(Author))

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    session = Session(engine)
    author = AuthorRecord()
    session.add(author)
    session.add(ReaderRecord())
    session.add(ReaderRecord())
    session.commit()

    result = executor(Root)("""{
        authors {
            id
        }
    }""", context=QueryContext(session=session))
    assert_that(result, is_successful_result(data={
        "authors": [
            {"id": author.c_id},
        ],
    }))


def test_column_field_can_be_marked_as_internal():
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

        id = column_field(AuthorRecord.c_id, internal=True)
        name = column_field(AuthorRecord.c_name)

    class Root(RootType):
        authors = many(lambda: select(Author))

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    result = executor(Root)("""{
        authors {
            id
        }
    }""", context=QueryContext(session=Session(engine)))
    assert_that(
        result,
        is_invalid_result(errors=contains_inanyorder(
            has_string(starts_with('Cannot query field "id"')),
        )),
    )


def test_distinct_on_is_preserved_when_fetching_immediates():
    # TODO: set up PostgreSQL tests to get this working
    return
    Base = declarative_base()

    class LabelRecord(Base):
        __tablename__ = "author"

        c_id = Column(Integer, primary_key=True)
        c_label = Column(Unicode, nullable=False)

    class Label(SqlAlchemyObjectType):
        __model__ = LabelRecord

        @classmethod
        def __select_all__(cls):
            return super(Label, cls).__select_all__() \
                .distinct(LabelRecord.c_label) \
                .order_by(LabelRecord.c_label, LabelRecord.c_id.desc())

        id = column_field(LabelRecord.c_id)
        label = column_field(LabelRecord.c_label)

    class Root(RootType):
        labels = many(lambda: select(Label))

    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    session = Session(engine)
    session.add(LabelRecord(c_id=1, c_label="First"))
    session.add(LabelRecord(c_id=2, c_label="Second"))
    session.commit()

    result = executor(Root)("""{
        labels {
            id
            label
        }
    }""", context=QueryContext(session=session))
    assert_that(result, is_successful_result(data={
        "labels": [
            {"id": 2, "label": "Second"},
        ],
    }))


def test_type_of_field_is_determined_from_type_of_column():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"
        c_id = Column(Integer, primary_key=True)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        id = column_field(AuthorRecord.c_id)

    assert_that(Author.id.type, all_of(
        instance_of(graphql.GraphQLNonNull),
        has_properties(of_type=equal_to(graphql.GraphQLInt))
    ))


def test_type_of_field_can_be_explicitly_set():
    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"
        c_id = Column(Integer, primary_key=True)

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        id = column_field(AuthorRecord.c_id, type=graphql.GraphQLString)

    assert_that(Author.id.type, equal_to(graphql.GraphQLString))


@pytest.mark.parametrize("column, graphql_type", [
    (sqlalchemy.Column(sqlalchemy.Integer()), equal_to(graphql.GraphQLInt)),
    (sqlalchemy.Column(sqlalchemy.Float()), equal_to(graphql.GraphQLFloat)),
    (sqlalchemy.Column(sqlalchemy.String()), equal_to(graphql.GraphQLString)),
    (sqlalchemy.Column(sqlalchemy.Unicode()), equal_to(graphql.GraphQLString)),
    (sqlalchemy.Column(sqlalchemy.Boolean()), equal_to(graphql.GraphQLBoolean)),
    (
        sqlalchemy.Column(sqlalchemy.Integer(), nullable=False),
        all_of(instance_of(graphql.GraphQLNonNull), has_properties(of_type=equal_to(graphql.GraphQLInt))),
    ),
])
def test_type_mappings(column, graphql_type):
    assert_that(_sql_column_to_graphql_type(column), graphql_type)


class QueryContext(object):
    def __init__(self, session):
        self.session = session


class TestFindJoinCandidates(object):
    def test_can_find_foreign_key_from_local_to_target_primary_key(self):
        Base = declarative_base()

        class AuthorRecord(Base):
            __tablename__ = "author"

            c_id = Column(Integer, primary_key=True)

        class BookRecord(Base):
            __tablename__ = "book"

            c_id = Column(Integer, primary_key=True)
            c_author_id = Column(Integer, ForeignKey(AuthorRecord.c_id))

        class Author(SqlAlchemyObjectType):
            __model__ = AuthorRecord

            id = column_field(AuthorRecord.c_id)

        class Book(SqlAlchemyObjectType):
            __model__ = BookRecord

            id = column_field(BookRecord.c_id)
            author_id = column_field(BookRecord.c_author_id)

        candidates = list(_find_join_candidates(Book, Author))

        assert_that(candidates, equal_to([
            (Book.__dict__["author_id"], Author.__dict__["id"]),
        ]))


    def test_can_find_foreign_key_from_local_to_target_column_that_isnt_primary_key(self):
        Base = declarative_base()

        class AuthorRecord(Base):
            __tablename__ = "author"

            c_id = Column(Integer, primary_key=True)
            c_code = Column(Integer)

        class BookRecord(Base):
            __tablename__ = "book"

            c_id = Column(Integer, primary_key=True)
            c_author_code = Column(Integer, ForeignKey(AuthorRecord.c_code))

        class Author(SqlAlchemyObjectType):
            __model__ = AuthorRecord

            id = column_field(AuthorRecord.c_id)
            code = column_field(AuthorRecord.c_code)

        class Book(SqlAlchemyObjectType):
            __model__ = BookRecord

            id = column_field(BookRecord.c_id)
            author_code = column_field(BookRecord.c_author_code)

        candidates = list(_find_join_candidates(Book, Author))

        assert_that(candidates, equal_to([
            (Book.__dict__["author_code"], Author.__dict__["code"]),
        ]))


    def test_hybrid_properties_are_ignored_when_scanning_for_foreign_keys(self):
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

            id = column_field(AuthorRecord.c_id)

        class Book(SqlAlchemyObjectType):
            __model__ = BookRecord

            id = column_field(BookRecord.c_id)
            title = column_field(BookRecord.c_title)
            author_id = column_field(BookRecord.c_author_id)

        assert_that(
            list(_find_join_candidates(Author, Book)),
            equal_to([(Author.__dict__["id"], Book.__dict__["author_id"])]),
        )

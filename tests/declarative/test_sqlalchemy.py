from hamcrest import assert_that, equal_to
from sqlalchemy import create_engine, Column, Integer, Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from graphjoiner.declarative import executor, field, many, RootType, lazy_field
from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType


def test_can_explicitly_set_join_condition_between_sqlalchemy_objects():
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
        books = lazy_field(lambda: many(Book, join={Author.id: Book.author_id}))

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = field(column=BookRecord.c_id)
        title = field(column=BookRecord.c_title)
        author_id = field(column=BookRecord.c_author_id)

    class Root(RootType):
        authors = many(Author)

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
    assert_that(result, equal_to({
        "authors": [
            {"name": "PG Wodehouse", "books": [{"title": "Leave It to Psmith"}]},
            {"name": "Joseph Heller", "books": [{"title": "Catch-22"}]},
        ],
    }))


class QueryContext(object):
    def __init__(self, session):
        self.session = session

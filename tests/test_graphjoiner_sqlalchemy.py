from datetime import datetime

from graphql import GraphQLInt, GraphQLString, GraphQLArgument
from sqlalchemy import create_engine, Column, Integer, Unicode, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query

from graphjoiner import execute, single, many, extract, JoinType, RootJoinType, field
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


class QueryContext(object):
    def __init__(self, session):
        self.session = session


def fetch_immediates_from_query(model):
    def fetch_immediates_from_query(selections, query, context):
        query = query.with_entities(*(
            getattr(model, selection.field.column_name)
            for selection in selections
        ))
        keys = tuple(selection.key for selection in selections)

        return [
            dict(zip(keys, row))
            for row in query.with_session(context.session).all()
        ]

    return fetch_immediates_from_query


def evaluate(func):
    return func()


@evaluate
def author_join_type():
    def fields():
        books = many(
            book_join_type,
            book_query,
            join={"id": "authorId"},
        )

        return {
            "id": field(column_name="id", type=GraphQLInt),
            "name": field(column_name="name", type=GraphQLString),
            "books": books,
            "bookTitles": extract(books, "title"),
        }

    def book_query(args, author_query):
        authors = author_query.with_entities(Author.id).distinct().subquery()
        return Query([]) \
            .select_from(Book) \
            .join(authors, authors.c.id == Book.author_id)

    return JoinType(
        name="Author",
        fields=fields,
        fetch_immediates=fetch_immediates_from_query(Author),
    )


@evaluate
def book_join_type():
    def fields():
        author = single(
            author_join_type,
            author_query,
            join={"authorId": "id"},
        )

        return {
            "id": field(column_name="id", type=GraphQLInt),
            "title": field(column_name="title", type=GraphQLString),
            "authorId": field(column_name="author_id", type=GraphQLInt),
            "author": author,
            "booksBySameAuthor": extract(author, "books"),
        }

    def author_query(args, book_query):
        books = book_query.with_entities(Book.author_id).distinct().subquery()
        return Query([]) \
            .select_from(Author) \
            .join(books, books.c.author_id == Author.id)

    return JoinType(
        name="Book",
        fields=fields,
        fetch_immediates=fetch_immediates_from_query(Book),
    )


@evaluate
def root():
    def fields():
        return {
            "books": many(book_join_type, lambda *_: Query([]).select_from(Book)),
            "book": single(book_join_type, book_query, args={"id": GraphQLArgument(type=GraphQLInt)}),
            "author": single(author_join_type, author_query, args={"id": GraphQLArgument(type=GraphQLInt)}),
        }

    def book_query(args, _):
        query = Query([]).select_from(Book)

        book_id = args.get("id")
        if book_id is not None:
            query = query.filter(Book.id == book_id)

        return query

    def author_query(args, _):
        query = Query([]).select_from(Author)

        author_id = args.get("id")
        if author_id is not None:
            query = query.filter(Author.id == author_id)

        return query

    return RootJoinType(
        name="Root",
        fields=fields,
    )


class TestGraphJoinerSqlAlchemy(ExecutionTestCases):
    def execute(self, query, **kwargs):
        engine = create_engine("sqlite:///:memory:")

        Base.metadata.create_all(engine)

        session = Session(engine)
        session.add(Author(name="PG Wodehouse"))
        session.add(Author(name="Joseph Heller"))
        session.add(Book(title="Leave It to Psmith", author_id=1))
        session.add(Book(title="Right Ho, Jeeves", author_id=1))
        session.add(Book(title="Catch-22", author_id=2))

        session.commit()

        return execute(root, query, context=QueryContext(session), **kwargs)

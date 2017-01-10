from hamcrest import assert_that, equal_to

def test_example():
    from sqlalchemy import Column, Integer, Unicode, ForeignKey
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

    class AuthorRecord(Base):
        __tablename__ = "author"

        id = Column(Integer, primary_key=True)
        name = Column(Unicode, nullable=False)

    class BookRecord(Base):
        __tablename__ = "book"

        id = Column(Integer, primary_key=True)
        title = Column(Unicode, nullable=False)
        genre = Column(Unicode, nullable=False)
        author_id = Column(Integer, ForeignKey(AuthorRecord.id))




    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(AuthorRecord(name="PG Wodehouse"))
    session.add(AuthorRecord(name="Joseph Heller"))
    session.add(AuthorRecord(name="Jules Verne"))
    session.add(BookRecord(title="Leave It to Psmith", author_id=1, genre="comedy"))
    session.add(BookRecord(title="Right Ho, Jeeves", author_id=1, genre="comedy"))
    session.add(BookRecord(title="Catch-22", author_id=2, genre="comedy"))
    session.add(BookRecord(title="Around the World in Eighty Days", author_id=3, genre="adventure"))



    from graphql import GraphQLString
    from graphjoiner.declarative import RootType, single, many, field
    from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        
        id = field(column=AuthorRecord.id)
        name = field(column=AuthorRecord.name)

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord
        
        id = field(column=BookRecord.id)
        title = field(column=BookRecord.title)
        genre = field(column=BookRecord.genre)
        author_id = field(column=BookRecord.author_id)
        author = field(lambda: single(Author))

    class Root(RootType):
        books = many(Book)
        
        @books.arg("genre", GraphQLString)
        def books_arg_genre(query, genre):
            return query.filter(BookRecord.genre == genre)




    from graphjoiner.declarative import executor

    execute = executor(Root)
    
    

    query = """
        {
            books(genre: "comedy") {
                title
                author {
                    name
                }
            }
        }
    """

    class Context(object):
        def __init__(self, session):
            self.session = session

    results = execute(query, context=Context(session))

    assert_that(results, equal_to({
        "books": [
            {
                "title": "Leave It to Psmith",
                "author": {
                    "name": "PG Wodehouse"
                }
            },
            {
                "title": "Right Ho, Jeeves",
                "author": {
                    "name": "PG Wodehouse"
                }
            },
            {
                "title": "Catch-22",
                "author": {
                    "name": "Joseph Heller"
                }
            },
        ]
    }))


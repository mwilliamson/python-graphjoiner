GraphJoiner: Implementing GraphQL with joins
============================================

In some use cases, I've found it more natural to generate the requested GraphQL
data using SQL joins rather than resolving values individually. This is a proof
of concept that provides an alternative way of responding to GraphQL queries.

In the reference GraphQL implementation, resolve functions describe how to
fulfil some part of the requested data for each instance of an object.
If implemented naively with a SQL backend, this results in the N+1 problem.
For instance, given the query:

::

    {
        books(genre: "comedy") {
            title
            author {
                name
            }
        }
    }

A naive GraphQL implement would issue one SQL query to get the list of all
books in the comedy genre, and then N queries to get the author of each book
(where N is the number of books returned by the first query).

There are various solutions proposed to this problem: GraphJoiner suggests that
using joins is a natural fit for many use cases. For this specific case, we only
need to run two queries: one to find the list of all books in the comedy genre,
and one to get the authors of books in the comedy genre.

Example
-------

Let's say we have some models defined by SQLAlchemy. A book has an ID, a title
and an author ID. An author has an ID and a name.

.. code-block:: python

    from sqlalchemy import Column, Integer, Unicode, ForeignKey
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

    class Author(Base):
    __tablename__ = "author"
    
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)

    class Book(Base):
        __tablename__ = "book"
        
        id = Column(Integer, primary_key=True)
        title = Column(Unicode, nullable=False)
        genre = Column(Unicode, nullable=False)
        author_id = Column(Integer, ForeignKey(Author.id))

We then define object types for the root, books and authors:

.. code-block:: python

    from graphjoiner import RootObjectType, single, many

    class Root(RootObjectType):
        @classmethod
        def fields(cls):
            return {
                "books": many(BookObjectType, cls._books_query)
            }
        
        @classmethod
        def _books_query(cls, request, _):
            query = Query([]).select_from(Book)
            
            if "genre" in request.args:
                query = query.filter(Book.genre == request.args["genre"])
                
            return query
    

    class DatabaseObjectType(ObjectType):
        def fetch_immediates(self, request, query):
            fields = self.fields()
            query = query.with_entities(*(
                fields[field]
                for field in request.requested_fields
            ))
            
            return [
                dict(zip(request.requested_fields, row))
                for row in query.all()
            ]

    class BookObjectType(DatabaseObjectType):
        @classmethod
        def fields(cls):
            return {
                "id": "id",
                "title": "title",
                "genre": "genre",
                "authorId": "author_id",
                "author": single(AuthorObjectType, cls._author_query, join={"authorId": "id"}),
            }
        
        @classmethod
        def _author_query(cls, request, book_query):
            books = book_query.with_entities(Book.author_id).distinct().subquery()
            return Query([]) \
                .select_from(Author) \
                .join(books, books.c.author_id == Author.id)
    
    class AuthorObjectType(DatabaseObjectType):
        @classmethod
        def fields(cls):
            return {
                "id": "id",
                "name": "name",
            }

A few things could do with some explanation:

* ``fetch_immediates(self, request, query)``:

* ``single()``:

* ``many()``:

We can execute the query by calling ``execute``:

.. code-block:: python
    
    from graphjoiner import execute
    
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
    execute(Root(), query)


Which produces:

::

    {
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
    }

Installation
------------

    pip install graphjoiner


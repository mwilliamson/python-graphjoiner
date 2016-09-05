GraphJoiner: Implementing GraphQL with joins
============================================

In some use cases, I've found it more natural to generate the requested GraphQL
data using SQL joins rather than resolving values individually. This is a proof
of concept that provides an alternative way of responding to GraphQL queries.

In the reference GraphQL implementation, resolve functions describe how to
fulfil some part of the requested data for each instance of an object.
GraphJoiner instead maps nodes in the query to a single query that will fetch
the relevant values for all instances.

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

GraphJoiner expects the ``books`` node to be mapped to one query that fetches
all books in the comedy genre, and the author node to be mapped to one query
that fetches all authors of books in the comedy genre.

Example
-------

(Working code for this example can be found in ``tests/test_graphjoiner/sqlalchemy.py``.)

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
        author_id = Column(Integer, ForeignKey(Author.id))

We then need to tell GraphJoiner how to query each model. Let's say we want to
respond to the query:

.. code-block:: none

    {
        books {
            id
            title
            authorId
        }
    }

We first define a root object type:

.. code-block:: python

    from graphjoiner import RootObjectType, many

    class Root(RootObjectType):
        @classmethod
        def fields(cls):
            return {
                "books": many(BookObjectType, cls._books_query)
            }
        
        @classmethod
        def _books_query(cls, request, _):
            return Query([]).select_from(Book)

We use the ``many`` function to define a one-to-many relationship -- that is,
that are many books for each root instance (and in fact, there's only ever one
root instance). We then describe how to generate a query that represents all of
the books in the database.

We still need to define ``BookObjectType``.
In this case, ``fields`` maps each GraphQL field to the column name in the database.
We also define a method ``fetch_immediates`` that tells GraphJoiner
how to fetch the fields for books that can be fetched without a join.

.. code-block:: python

    from graphjoiner import ObjectType

    class BookObjectType(ObjectType):
        @classmethod
        def fields(cls):
            return {
                "id": "id",
                "title": "title",
                "authorId": "author_id",
            }
        
        def fetch_immediates(self, request, book_query):
            query = book_query.with_entities(*(
                self.fields[field]
                for field in request.requested_fields
            ))
            
            return [
                dict(zip(request.requested_fields, row))
                for row in query.all()
            ]

We can then execute the query by calling ``execute``:

.. code-block:: python
    
    query = """
        {
            books {
                id
                title
                authorId
            }
        }
    """
    execute(Root(), query)


Which produces:

.. code-block::

    {
        "books": [
            {
                "id": 1,
                "title": "Leave It to Psmith",
                "authorId": 1,
            },
            {
                "id": 2,
                "title": "Right Ho, Jeeves",
                "authorId": 1,
            },
            {
                "id": 3,
                "title": "Catch-22",
                "authorId": 2,
            },
        ]
    }


Arguments
~~~~~~~~~

What about if we want to respond to a query that includes arguments?
For instance:

::
    
    {
        author(id: 1) {
            name
        }
    }

We need to add an ``author`` field to the ``fields`` method on ``RootEntity``.
Since this represent one instance instead of many, we use ``single`` instead of
``many`` to define the relationship:

.. code-block:: python

    from graphjoiner import RootObjectType, single, many

    class Root(RootObjectType):
        @classmethod
        def fields(cls):
            return {
                "books": many(BookObjectType, cls._books_query),
                "author": single(AuthorObjectType, cls._author_query),
            }
        
        @classmethod
        def _books_query(cls, request, _):
            return Query([]).select_from(Book)
        
        @classmethod
        def _author_query(cls, request, _):
            return Query([]) \
                .select_from(Author) \
                .filter(Author.id == request.args["id"])

We then define ``AuthorObjectType`` in much the same way we defined
``BookObjectType``. In fact, our definition for ``fetch_immediates`` will be
exactly the same, so we can extract a common base class:

.. code-block:: python

    from graphjoiner import ObjectType

    class DatabaseObjectType(ObjectType):
        def fetch_immediates(self, request, query):
            query = query.with_entities(*(
                self.fields[field]
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
                "authorId": "author_id",
            }
    
    class AuthorObjectType(DatabaseObjectType):
        @classmethod
        def fields(cls):
            return {
                "id": "id",
                "name": "name",
            }

As before, we can execute the query by calling ``execute``:

.. code-block:: python
    
    query = """
        {
            author(id: 1) {
                name
            }
        }
    """
    execute(Root(), query)


Which produces:

.. code-block::

    {
        "author": {
            "name": "PG Wodehouse",
        }
    }


Installation
------------

    pip install graphjoiner


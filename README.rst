GraphJoiner: Implementing GraphQL with joins
============================================

In some use cases, I've found it more natural to generate the requested GraphQL
data using SQL joins rather than resolving values individually. This is a proof
of concept that provides an alternative way of responding to GraphQL queries.

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
        }
    }

We define a class ``BookEntity`` so that GraphJoiner knows how to query books.
This inherits from ``Entity``, and has a attribute ``fields`` that maps
from the GraphQL key to the key in the database. We also define a method
``fetch_immediates`` that tells GraphJoiner how to fetch the fields for books
that can be fetched without a join.

.. code-block:: python

    from graphjoiner import Entity

    class BookEntity(Entity):
        fields = {
            "id": "id",
            "title": "title",
            "authorId": "author_id",
        }
        
        def fetch_immediates(self, request, context):
            query = session.query().select_from(Book).with_entities(*(
                self.fields[field]
                for field in request.requested_fields
            ))
            
            return [
                dict(zip(request.requested_fields, row))
                for row in query.all()
            ]

We also need to define a root entity:

.. code-block:: python

    from graphjoiner import RootEntity, many

    class Root(RootEntity):
        fields = {
            "books": many(BookEntity)
        }

We can then execute the query by calling ``execute``:

.. code-block:: python
    
    query = """
        {
            books {
                id
                title
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
            },
            {
                "id": 2,
                "title": "Right Ho, Jeeves",
            },
            {
                "id": 3,
                "title": "Catch-22",
            },
        ]
    }


Installation
------------

    pip install graphjoiner


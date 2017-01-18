GraphJoiner: Implementing GraphQL with joins
============================================

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

A naive GraphQL implementation would issue one SQL query to get the list of all
books in the comedy genre, and then N queries to get the author of each book
(where N is the number of books returned by the first query).

There are various solutions proposed to this problem: GraphJoiner suggests that
using joins is a natural fit for many use cases. For this specific case, we only
need to run two queries: one to find the list of all books in the comedy genre,
and one to get the authors of books in the comedy genre.

Installation
------------

::

    pip install graphjoiner
    
Example
-------

Let's say we have some models defined by SQLAlchemy. A book has an ID, a title,
a genre and an author ID. An author has an ID and a name.

.. code-block:: python

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

We then define object types for the root, books and authors:

.. code-block:: python

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
        books = field(lambda: many(Book))
        
        @books.arg("genre", GraphQLString)
        def books_arg_genre(query, genre):
            return query.filter(BookRecord.genre == genre)

We create an ``execute()`` function by calling ``executor()`` with our ``Root``:

.. code-block:: python

    from graphjoiner.declarative import executor

    execute = executor(Root)

``execute`` can then be used to execute queries:

.. code-block:: python

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

    result = execute(root, query, context=Context(session))


Where ``result.data`` is:

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

Let's break things down a little, starting with the definition of ``Author``:

.. code-block:: python

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        
        id = field(column=AuthorRecord.id)
        name = field(column=AuthorRecord.name)

When defining object types that represent SQLAlchemy models,
we can inherit from ``SqlAlchemyObjectType``,
with the ``__model__`` attribute set to the appropriate model.

Fields that can be fetched without further joining can be defined using ``field()``.
The arguments that ``field()`` accepts will depend on the object type.
For SQLAlchemy object types, we pass in the column that the field should correspond to.

Next is the definition of ``Book``:

.. code-block:: python

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord
        
        id = field(column=BookRecord.id)
        title = field(column=BookRecord.title)
        genre = field(column=BookRecord.genre)
        author_id = field(column=BookRecord.author_id)
        author = field(lambda: single(Author))

As before, we inherit from ``SqlAlchemyObjectType``,
set ``__model__`` to the appropriate class,
and define a number of fields that correspond to columns.

We also define an ``author`` field that allows a book to be joined to an author.
GraphJoiner will automatically inspect ``BookRecord`` and ``AuthorRecord``
and use the foreign keys to determine how they should be joined together.
To override this behaviour, you can pass in an explicit ``join`` argument:

.. code-block:: python

    author = field(lambda: single(Author, join={Book.author_id: Author.id}))

This explicitly tells GraphJoiner that authors can be joined to books
by equality between the fields ``Book.author_id`` and ``Author.id``.
When defining relationships such as this,
we call ``field()`` with a lambda to defer evaluation until all of the types and fields have been defined.

Finally, we can create a root object:

.. code-block:: python

    class Root(RootType):
        books = many(Book)
        
        @books.arg("genre", GraphQLString)
        def books_arg_genre(query, genre):
            return query.filter(BookRecord.genre == genre)

The root has only one field, ``books``, a one-to-many relationship,
which we define using ``many()``.
As with ``single()``, we pass in the type we want to join to as the first argument, in this case ``Book``.
By default, a relationship from a root will select all possible instances.
In this case, this means that ``books`` represents all of the books in the database.

Using ``books.arg()`` adds an optional argument to the field.

For completeness, we can tweak the definition of ``Author`` so
we can request the books by an author:

.. code-block:: python

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord
        
        id = field(column=AuthorRecord.id)
        name = field(column=AuthorRecord.name)
        books = field(lambda: many(Book))

Core Example
------------

The declarative API of GraphJoiner is built on top of a core API.
The core API exposes the fundamentals of how GraphJoiner works,
giving greater flexibility at the cost of being rather verbose to use directly.
The below shows how the original example could be written using the core API.
In general,
using the declarative API should be preferred,
either by using the built-in tools or adding your own.

Let's say we have some models defined by SQLAlchemy. A book has an ID, a title,
a genre and an author ID. An author has an ID and a name.

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

    from graphql import GraphQLInt, GraphQLString, GraphQLArgument
    from graphjoiner import JoinType, RootJoinType, single, many, field
    from sqlalchemy.orm import Query

    def create_root():
        def fields():
            return {
                "books": many(
                    book_join_type,
                    books_query,
                    args={"genre": GraphQLArgument(type=GraphQLString)}
                )
            }

        def books_query(args, _):
            query = Query([]).select_from(Book)

            if "genre" in args:
                query = query.filter(Book.genre == args["genre"])

            return query

        return RootJoinType(name="Root", fields=fields)

    root = create_root()

    def fetch_immediates_from_database(selections, query, context):
        query = query.with_entities(*(
            selection.field.column_name
            for selection in selections
        ))

        return query.with_session(context.session).all()

    def create_book_join_type():
        def fields():
            return {
                "id": field(column_name="id", type=GraphQLInt),
                "title": field(column_name="title", type=GraphQLString),
                "genre": field(column_name="genre", type=GraphQLString),
                "authorId": field(column_name="author_id", type=GraphQLInt),
                "author": single(author_join_type, author_query, join={"authorId": "id"}),
            }

        def author_query(args, book_query):
            books = book_query.with_entities(Book.author_id).distinct().subquery()
            return Query([]) \
                .select_from(Author) \
                .join(books, books.c.author_id == Author.id)

        return JoinType(
            name="Book",
            fields=fields,
            fetch_immediates=fetch_immediates_from_database,
        )

    book_join_type = create_book_join_type()

    def create_author_join_type():
        def fields():
            return {
                "id": field(column_name="id", type=GraphQLInt),
                "name": field(column_name="name", type=GraphQLString),
            }

        return JoinType(
            name="Author",
            fields=fields,
            fetch_immediates=fetch_immediates_from_database,
        )
    author_join_type = create_author_join_type()

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

    class Context(object):
        def __init__(self, session):
            self.session = session

    execute(root, query, context=Context(session))


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

Let's break things down a little, starting with the definition of the root object:

.. code-block:: python

    def create_root():
        def fields():
            return {
                "books": many(
                    book_join_type,
                    books_query,
                    args={"genre": GraphQLArgument(type=GraphQLString)}
                )
            }

        def books_query(args, _):
            query = Query([]).select_from(Book)

            if "genre" in args:
                query = query.filter(Book.genre == args["genre"])

            return query

        return RootJoinType(name="Root", fields=fields)

    root = create_root()

For each object type, we need to define its fields.
The root has only one field, ``books``, a one-to-many relationship,
which we define using ``many()``.
The first argument, ``book_join_type``,
is the type we're defining a relationship to.
The second argument to describes how to create a query representing all of those
related books: in this case all books, potentially filtered by a genre argument.

This means we need to define ``book_join_type``:

.. code-block:: python

    def create_book_join_type():
        def fields():
            return {
                "id": field(column_name="id", type=GraphQLInt),
                "title": field(column_name="title", type=GraphQLString),
                "genre": field(column_name="genre", type=GraphQLString),
                "authorId": field(column_name="author_id", type=GraphQLInt),
                "author": single(author_join_type, author_query, join={"authorId": "id"}),
            }

        def author_query(args, book_query):
            books = book_query.with_entities(Book.author_id).distinct().subquery()
            return Query([]) \
                .select_from(Author) \
                .join(books, books.c.author_id == Author.id)

        return JoinType(
            name="Book",
            fields=fields,
            fetch_immediates=fetch_immediates_from_database,
        )

    book_join_type = create_book_join_type()

The ``author`` field is defined as a one-to-one mapping from book to author.
As before, we define a function that generates a query for the requested authors.
We also provide a ``join`` argument to ``single()`` so that GraphJoiner knows
how to join together the results of the author query and the book query:
in this case, the ``authorId`` field on books corresponds to the ``id`` field
on authors.
(If we leave out the ``join`` argument, then GraphJoiner will perform a cross
join i.e. a cartesian product. Since there's always exactly one root instance,
this is fine for relationships defined on the root.)

The remaining fields define a mapping from the GraphQL field to the database
column. This mapping is handled by ``fetch_immediates_from_database``.
The value of ``selections`` in
``fetch_immediates()`` is the selections of fields that aren't defined as relationships
(using ``single`` or ``many``) that were either explicitly requested in the
original GraphQL query, or are required as part of the join.

.. code-block:: python

    def fetch_immediates_from_database(selections, query, context):
        query = query.with_entities(*(
            fields[selection.field_name].column_name
            for selection in selections
        ))

        return query.with_session(context.session).all()

For completeness, we can tweak the definition of ``author_join_type`` so
we can request the books by an author:

.. code-block:: python

    def create_author_join_type():
        def fields():
            return {
                "id": field(column_name="id", type=GraphQLInt),
                "name": field(column_name="name", type=GraphQLString),
                "author": many(book_join_type, book_query, join={"id": "authorId"}),
            }

        def book_query(args, author_query):
            authors = author_query.with_entities(Author.id).distinct().subquery()
            return Query([]) \
                .select_from(Book) \
                .join(authors, authors.c.id == Book.author_id)

        return JoinType(
            name="Author",
            fields=fields,
            fetch_immediates=fetch_immediates_from_database,
        )

    author_join_type = create_author_join_type()


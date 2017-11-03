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

    from graphjoiner.declarative import RootType, single, many, select, String
    from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType, column_field, sql_join

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        id = column_field(AuthorRecord.id)
        name = column_field(AuthorRecord.name)

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = column_field(BookRecord.id)
        title = column_field(BookRecord.title)
        genre = column_field(BookRecord.genre)
        author_id = column_field(BookRecord.author_id)
        author = single(lambda: sql_join(Author))

    class Root(RootType):
        books = many(lambda: select(Book))

        @books.arg("genre", String)
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

        id = column_field(AuthorRecord.id)
        name = column_field(AuthorRecord.name)

When defining object types that represent SQLAlchemy models,
we can inherit from ``SqlAlchemyObjectType``,
with the ``__model__`` attribute set to the appropriate model.

Fields that can be fetched without further joining can be defined using ``column_field()``.
GraphJoiner will automatically infer the GraphQL type of the field based on the SQL type of the column.

Next is the definition of ``Book``:

.. code-block:: python

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        id = column_field(BookRecord.id)
        title = column_field(BookRecord.title)
        genre = column_field(BookRecord.genre)
        author_id = column_field(BookRecord.author_id)
        author = single(lambda: sql_join(Author))

As before, we inherit from ``SqlAlchemyObjectType``,
set ``__model__`` to the appropriate class,
and define a number of fields that correspond to columns.

We also define an ``author`` field that allows a book to be joined to an author.
GraphJoiner will automatically inspect ``BookRecord`` and ``AuthorRecord``
and use the foreign keys to determine how they should be joined together.
To override this behaviour, you can pass in an explicit ``join`` argument:

.. code-block:: python

    author = single(lambda: sql_join(Author, join={Book.author_id: Author.id}))

This explicitly tells GraphJoiner that authors can be joined to books
by equality between the fields ``Book.author_id`` and ``Author.id``.
When defining relationships such as this,
we call ``single()`` with a lambda to defer evaluation until all of the types and fields have been defined.

Finally, we can create a root object:

.. code-block:: python

    class Root(RootType):
        books = many(lambda: select(Book))

        @books.arg("genre", String)
        def books_arg_genre(query, genre):
            return query.filter(BookRecord.genre == genre)

The root has only one field, ``books``, which we define using ``many()``.
Using ``select`` tells GraphJoiner to select all of the books in the database,
rather than trying to perform a join.

Using ``books.arg()`` adds an optional argument to the field.

For completeness, we can tweak the definition of ``Author`` so
we can request the books by an author:

.. code-block:: python

    class Author(SqlAlchemyObjectType):
        __model__ = AuthorRecord

        id = column_field(AuthorRecord.id)
        name = column_field(AuthorRecord.name)
        books = many(lambda: sql_join(Book))


API
---

``graphjoiner.declarative``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

ObjectType
^^^^^^^^^^

Represents a GraphQL object type.
Fields can be declared as attributes.
For instance, to create an object type called ``User`` with a ``name`` and ``emailAddress`` field:

.. code-block:: python

    from graphqjoiner import NonNull, ObjectType, String

    class User(ObjectType):
        name = NonNull(String)
        email_address = NonNull(String)

Field names are inferred from attribute names,
converting from snake case to camel case.
In the example above, the attribute name ``email_address`` is converted to the field name ``emailAddress``.

To create a type that can be joined to,
implement ``__fetch_immediates__`` as a static or class method.

* ``__fetch_immediates__(selections, query, context)``:
  fetch the values for the selected fields that aren't defined as relationships.

  Receives the arguments:

  * ``selections``: an iterable of the selections,
    where each selection has the attributes:

    * ``field``: the field being selected
    * ``args``: the arguments for the selection
    * ``selections``: the sub-selections of that selection

  * ``query``: the query for the records to select.

  * ``context``: the context as passed into the executor

  Should return a list of tuples,
  where each tuple contains the value for each selection in the same order.

Implementing ``__select_all__`` allows the object to be used with ``select()``.
``__select_all__()`` takes no arguments,
and should return a query that represents all instances of the object.

For instance,
to implement a base type for static data:

.. code-block:: python

    import collections

    from graphjoiner.declarative import ObjectType, RootType, select, single, String

    class StaticDataObjectType(ObjectType):
        @classmethod
        def __select_all__(cls):
            return cls.__records__

        @classmethod
        def __fetch_immediates__(cls, selections, records, context):
            return [
                tuple(
                    getattr(record, selection.field.attr_name)
                    for selection in selections
                )
                for record in records
            ]

    AuthorRecord = collections.namedtuple("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=String)

    class Root(RootType):
        author = single(lambda: select(Author))


Relationships
^^^^^^^^^^^^^

Use ``single``, ``single_or_null``, ``first_or_null`` and ``many`` to create fields that are joined to other types.
For instance, to select all books from the root type:

.. code-block:: python

    from graphjoiner.declarative import many, RootType, select

    class Root(RootType):
        ...
        books = many(lambda: select(Book))

Each relationship function accepts a joiner:
a value that describes how to join the left type to the right type.
The joiner is always wrapped in a lambda to defer evaluation until all types are defined.
In this case, the left type is ``Root``, the right type is ``Book``,
and the joiner is ``select(Book)``.
Calling ``select()`` with just the right type tells GraphJoiner to select all values,
in this case all books.

All joiners accept a ``filter`` argument that allow the query to be tweaked.
For instance,
supposing books are selected using SQLAlchemy queries,
and we want the ``books`` field to be sorted by title:

.. code-block:: python

    from graphjoiner.declarative import many, RootType, select
    from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        ...

        @staticmethod
        def order_by_title(query):
            # query is an instance of sqlalchemy.orm.Query
            return query.order_by(BookRecord.title)

    class Root(RootType):
        ...

        books = many(lambda: select(
            Book,
            filter=Book.order_by_title,
        ))

Arguments can be added using the ``arg()`` decorator.
If the GraphQL selection for that field includes a value for the argument,
the query is updated using the decorated function.
For instance, to allow books to be filtered by title:

.. code-block:: python

    from graphjoiner.declarative import many, RootType, select, String
    from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        ...

        @staticmethod
        def filter_by_title(query, title):
            # query is an instance of sqlalchemy.orm.Query
            return query.filter(BookRecord.title == title)

    class Root(RootType):
        ...

        books = many(lambda: select(Book))
        @books.arg("title", String)
        def books_arg_title(query, title):
            return Book.filter_by_title(query, title)


``select(target, join_query=None, join_fields=None)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Creates a joiner to the target type.
When given no additional arguments,
it will select all values of the target type using ``target.__select_all__()``.
All left values are joined onto all right values
i.e. the join is the cartesian product.
Unless the left type is the root type,
this probably isn't what you want.

Set ``join_fields`` to describe which fields to use to join together the left and right types.
Each item in the dictionary should map a field from the left type to a field from the right type.
For instance, supposing each author has a unique ID,
and each book has an author ID:

.. code-block:: python

    from graphjoiner.declarative import field, Int, ObjectType, select, single

    class Book(ObjectType):
        ...
        author_id = field(type=Int)
        author = single(lambda: select(
            Author,
            join_fields={Book.author_id: Author.id},
        ))

Set ``join_query`` to describe how to join the left query and the right query.
This should be a function that accepts a left query and a right query,
and returns a right query filtered to the values relevant to the left query.
This avoids the cost of fetching all values of the right type only to discard those that don't join onto any left values.
For instance, when using the ``sqlalchemy`` module,
we'd like to fetch the authors for just the requested book,
rather than all available authors:

.. code-block:: python

    from graphjoiner.declarative import select, single
    from graphjoiner.declarative.sqlalchemy import column_field, SqlAlchemyObjectType

    class Book(SqlAlchemyObjectType):
        ...
        author_id = column_field(BookRecord.author_id)

        def join_authors(book_query, author_query):
            author_ids = book_query \
                .add_columns(BookRecord.author_id) \
                .subquery()

            return author_query.join(
                author_ids,
                author_ids.c.author_id == AuthorRecord.id,
            )

        author = single(lambda: select(
            Author,
            join_query=join_authors,
            join_fields={Book.author_id: Author.id},
        ))

In this particular case, using ``sql_join()`` would remove much of the boilerplate:

.. code-block:: python

    from graphjoiner.declarative import single
    from graphjoiner.declarative.sqlalchemy import column_field, sql_join, SqlAlchemyObjectType

    class Book(SqlAlchemyObjectType):
        ...
        author_id = column_field(BookRecord.author_id)
        author = single(lambda: sql_join(Author, {Book.author_id: Author.id}))

``extract(field, sub_field)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a new field by extracting ``sub_field`` from ``field``.
The arguments for the new field are the same as the arguments for ``field``.

For instance,
supposing we have a field ``books`` on the root type,
each book has a ``title`` field,
and we want to add a ``bookTitles`` field to the root type:

.. code-block:: python

    from graphjoiner.declarative import extract, many, RootType, select

    class Root(RootType):
        books = many(lambda: select(Book))
        book_titles = extract(books, lambda: Book.title)

If we want to just have the ``bookTitles`` field without a ``books`` field,
we can pass the relationship directly into ``extract()``:

.. code-block:: python

    from graphjoiner.declarative import extract, many, RootType, select

    class Root(RootType):
        book_titles = extract(
            many(lambda: select(Book)),
            lambda: Book.title,
        )

``extract()`` is often useful when modelling many-to-many relationships.
For instance,
suppose a book may have many publishers,
and each publisher may publish many books.
We define a type that associates books and publishers:

.. code-block:: python

    from graphjoiner.declarative import ObjectType, select, single

    class BookPublisherAssociation(ObjectType):
        book = single(lambda: select(Book, ...))
        publisher = single(lambda: select(Publisher, ...))

We can then use ``extract`` to define a field for all publishers of a book,
and a field for books from a publisher:

.. code-block:: python

    from graphjoiner.declarative import extract, many, ObjectType, select

    class Book(ObjectType):
        ...
        publishers = extract(
            many(lambda: select(BookPublisherAssociation, ...)),
            lambda: BookPublisherAssociation.publisher,
        )

    class Publisher(ObjectType):
        ...
        books = extract(
            many(lambda: select(BookPublisherAssociation, ...)),
            lambda: BookPublisherAssociation.book,
        )

Interfaces
^^^^^^^^^^

To define an interface,
subclass ``InterfaceType`` and specify fields using ``field()``:

.. code-block:: python

    from graphjoiner.declarative import InterfaceType, String

    class HasName(InterfaceType):
        name = field(type=String)

To set which interfaces an object implements,
set the ``__interfaces__`` attribute:

.. code-block:: python

    from graphjoiner.declarative import ObjectType

    class Author(ObjectType):
        __interfaces__ = lambda: [HasName]
        ...

Field sets
^^^^^^^^^^

Field sets can be used to define multiple fields using a single attribute.
For instance, this definition without field sets:

.. code-block:: python

    from graphjoiner.declarative import field, Int, ObjectType, String

    class Book(ObjectType):
        title = field(type=String)
        author_id = field(type=Int)

is roughly equivalent to this definition using field sets:

.. code-block:: python

    from graphjoiner.declarative import field, field_set, ObjectType, String

    class Book(ObjectType):
        fields = field_set(
            title=field(type=String),
            author_id=field(type=String),
        )

Field sets are useful when a set of fields needs to be generated dynamically.

Input object types
^^^^^^^^^^^^^^^^^^

Define input types by inheriting from ``InputObjectType``,
and defining fields using ``field()``.
For instance:

.. code-block:: python

    from graphjoiner.declarative import InputObjectType, String

    class BookSelectionInput(InputObjectType):
        title = field(type=String, default=None)

The fields on input object values are available as attributes.
For instance:

.. code-block:: python

    from graphjoiner.declarative import many, RootType, select, String
    from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        ...

        @staticmethod
        def filter_by_title(query, title):
            # query is an instance of sqlalchemy.orm.Query
            return query.filter(BookRecord.title == title)

    class Root(RootType):
        ...

        books = many(lambda: select(Book))
        @books.arg("selection", BookSelectionInput)
        def books_arg_title(query, title):
            if selection.title is not None:
                query = Book.filter_by_title(query, title)

            return query

The default value for each field can be set by passing the ``default`` argument to each field.
To allow the absence of a value to be distinguished from an explicit null value,
the default value for a field is ``undefined`` if the ``default`` argument is not set.
For instance,
to allow books to be filtered by title,
including null titles:

.. code-block:: python

    from graphjoiner.declarative import field, InputObjectType, many, RootType, select, String, undefined
    from graphjoiner.declarative.sqlalchemy import SqlAlchemyObjectType

    class BookSelectionInput(InputObjectType):
        title = field(type=String)

    class Book(SqlAlchemyObjectType):
        __model__ = BookRecord

        ...

        @staticmethod
        def filter_by_title(query, title):
            # query is an instance of sqlalchemy.orm.Query
            return query.filter(BookRecord.title == title)

    class Root(RootType):
        ...

        books = many(lambda: select(Book))
        @books.arg("selection", BookSelectionInput)
        def books_arg_title(query, title):
            if selection.title is not undefined:
                query = Book.filter_by_title(query, title)

            return query

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


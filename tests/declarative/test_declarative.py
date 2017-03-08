import attr
from graphql import GraphQLField, GraphQLInterfaceType, GraphQLString
from hamcrest import assert_that, equal_to

from graphjoiner.declarative import executor, field, first_or_none, single, many, RootType, ObjectType, extract, join_builder, InterfaceType
from ..matchers import is_successful_result


class StaticDataObjectType(ObjectType):
    __abstract__ = True

    @staticmethod
    @join_builder
    def select(local, target):
        def generate_select(parent_select, context):
            return target.__records__

        return generate_select, {}

    @classmethod
    def __fetch_immediates__(cls, selections, records, context):
        return [
            tuple(
                getattr(record, selection.field.attr_name)
                for selection in selections
            )
            for record in records
        ]

def test_single_relationship_is_resolved_to_null_if_there_are_no_matching_results():
    class Author(StaticDataObjectType):
        __records__ = []

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("{ author { name } }")
    assert_that(result, is_successful_result(data={
        "author": None,
    }))


def test_single_relationship_is_resolved_to_object_if_there_is_exactly_one_matching_result():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("{ author { name } }")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_first_or_none_relationship_is_resolved_to_null_if_there_are_no_matching_results():
    class Author(StaticDataObjectType):
        __records__ = []

        name = field(type=GraphQLString)

    class Root(RootType):
        author = first_or_none(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("{ author { name } }")
    assert_that(result, is_successful_result(data={
        "author": None,
    }))


def test_first_or_none_relationship_is_resolved_to_object_if_there_is_exactly_one_matching_result():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = first_or_none(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("{ author { name } }")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_first_or_none_relationship_is_resolved_to_first_object_if_there_is_more_than_one_matching_result():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = first_or_none(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("{ author { name } }")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_relationships_can_take_filter_argument_to_refine_select():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        authors = many(lambda: StaticDataObjectType.select(Author, filter=lambda values: values[:1]))

    result = executor(Root)("{ authors { name } }")
    assert_that(result, is_successful_result(data={
        "authors": [{"name": "PG Wodehouse"}],
    }))


def test_can_extract_fields_from_relationships():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        authors = many(lambda: StaticDataObjectType.select(Author))
        author_names = extract(authors, "name")

    result = executor(Root)("{ authorNames }")
    assert_that(result, is_successful_result(data={
        "authorNames": ["PG Wodehouse", "Joseph Heller"],
    }))


def test_can_extract_fields_from_anonymous_fields():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author_names = extract(many(lambda: StaticDataObjectType.select(Author)), "name")

    result = executor(Root)("{ authorNames }")
    assert_that(result, is_successful_result(data={
        "authorNames": ["PG Wodehouse", "Joseph Heller"],
    }))


def test_can_implement_graphql_core_interfaces():
    HasName = GraphQLInterfaceType("HasName", fields={
        "name": GraphQLField(GraphQLString),
    }, resolve_type=lambda: None)

    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __interfaces__ = [HasName]

        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("""{
        author {
            ...on HasName {
                name
            }
        }
    }""")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_can_implement_declarative_interfaces():
    class HasName(InterfaceType):
        name = field(type=GraphQLString)

    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __interfaces__ = [HasName]

        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("""{
        author {
            ...on HasName {
                name
            }
        }
    }""")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_interfaces_can_be_declared_using_function():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __interfaces__ = lambda: [HasName]

        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class HasName(InterfaceType):
        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("""{
        author {
            ...on HasName {
                name
            }
        }
    }""")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_field_type_can_be_declared_using_declarative_interface_type():
    class Author(InterfaceType):
        name = field(type=GraphQLString)

    class Book(InterfaceType):
        author = field(type=Author)

    assert_that(Book.__graphql__.fields["author"].type, equal_to(Author.__graphql__))


def test_field_type_can_be_declared_using_declarative_object_type():
    class Author(ObjectType):
        name = field(type=GraphQLString)

        def __fetch_immediates__(cls, selections, query, context):
            pass

    class Book(InterfaceType):
        author = field(type=Author)

    assert_that(Book.__graphql__.fields["author"].type, equal_to(Author.__graphql__))

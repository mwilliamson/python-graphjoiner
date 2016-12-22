import attr
from hamcrest import assert_that, equal_to

from graphjoiner.declarative import executor, field, first_or_none, single, many, RootType, ObjectType, extract
from graphql import GraphQLString


class StaticDataObjectType(ObjectType):
    @classmethod
    def __select_all__(cls):
        return None

    @classmethod
    def __fetch_immediates__(cls, selections, query, context):
        return [
            tuple(
                getattr(record, selection.field.attr_name)
                for selection in selections
            )
            for record in cls.__records__
        ]


def test_single_relationship_is_resolved_to_null_if_there_are_no_matching_results():
    class Author(StaticDataObjectType):
        __records__ = []

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(Author)

    result = executor(Root)("{ author { name } }")
    assert_that(result, equal_to({
        "author": None,
    }))


def test_single_relationship_is_resolved_to_object_if_there_is_exactly_one_matching_result():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(Author)

    result = executor(Root)("{ author { name } }")
    assert_that(result, equal_to({
        "author": {"name": "PG Wodehouse"},
    }))


def test_first_or_none_relationship_is_resolved_to_null_if_there_are_no_matching_results():
    class Author(StaticDataObjectType):
        __records__ = []

        name = field(type=GraphQLString)

    class Root(RootType):
        author = first_or_none(Author)

    result = executor(Root)("{ author { name } }")
    assert_that(result, equal_to({
        "author": None,
    }))


def test_first_or_none_relationship_is_resolved_to_object_if_there_is_exactly_one_matching_result():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = first_or_none(Author)

    result = executor(Root)("{ author { name } }")
    assert_that(result, equal_to({
        "author": {"name": "PG Wodehouse"},
    }))


def test_first_or_none_relationship_is_resolved_to_first_object_if_there_is_more_than_one_matching_result():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = first_or_none(Author)

    result = executor(Root)("{ author { name } }")
    assert_that(result, equal_to({
        "author": {"name": "PG Wodehouse"},
    }))


def test_can_extract_fields_from_relationships():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        authors = many(Author)
        author_names = extract(authors, "name")

    result = executor(Root)("{ authorNames }")
    assert_that(result, equal_to({
        "authorNames": ["PG Wodehouse", "Joseph Heller"],
    }))


def test_can_extract_fields_from_anonymous_fields():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        author_names = extract(many(Author), "name")

    result = executor(Root)("{ authorNames }")
    assert_that(result, equal_to({
        "authorNames": ["PG Wodehouse", "Joseph Heller"],
    }))

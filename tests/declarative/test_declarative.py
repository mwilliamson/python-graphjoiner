import attr
from graphql import GraphQLBoolean, GraphQLField, GraphQLInterfaceType, GraphQLString
from hamcrest import assert_that, contains_inanyorder, equal_to, has_properties, has_string, starts_with
import pytest

from graphjoiner.declarative import (
    executor,
    extract,
    field,
    field_set,
    first_or_none,
    InputObjectType,
    single,
    many,
    RootType,
    ObjectType,
    join_builder,
    InterfaceType,
    select,
    undefined,
    _snake_case_to_camel_case,
)
from ..matchers import is_invalid_result, is_successful_result


class StaticDataObjectType(ObjectType):
    __abstract__ = True

    @staticmethod
    @join_builder
    def select(local, target, join=None):
        if join is None:
            join_fields = {}
        else:
            join_fields = dict(
                (local_field.field_name, remote_field.field_name)
                for local_field, remote_field in join.items()
            )

        def generate_select(parent_select, context):
            return target.__records__

        return generate_select, join_fields

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


def test_can_extract_fields_from_relationships_using_field():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse"), AuthorRecord("Joseph Heller")]

        name = field(type=GraphQLString)

    class Root(RootType):
        authors = many(lambda: StaticDataObjectType.select(Author))
        author_names = extract(authors, lambda: Author.name)

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


def test_field_type_can_be_declared_using_declarative_type_in_lambda():
    class Book(InterfaceType):
        author = field(type=lambda: Author)

    class Author(ObjectType):
        name = field(type=GraphQLString)

        def __fetch_immediates__(cls, selections, query, context):
            pass

    assert_that(Book.__graphql__.fields["author"].type, equal_to(Author.__graphql__))


def test_internal_fields_cannot_be_queried_directly():
    AuthorRecord = attr.make_class("AuthorRecord", ["id", "name"])
    BookRecord = attr.make_class("BookRecord", ["author_id", "title"])

    class Author(StaticDataObjectType):
        __records__ = [
            AuthorRecord("PGW", "PG Wodehouse"),
            AuthorRecord("JH", "Joseph Heller"),
        ]

        id = field(type=GraphQLString)
        name = field(type=GraphQLString)

    class Book(StaticDataObjectType):
        __records__ = [
            BookRecord("PGW", "Leave it to Psmith"),
            BookRecord("PGW", "The Code of the Woosters"),
        ]

        author_id = field(type=GraphQLString, internal=True)
        author = single(lambda: StaticDataObjectType.select(
            Author,
            join={Book.author_id: Author.id},
        ))
        title = field(type=GraphQLString)

    class Root(RootType):
        books = many(lambda: StaticDataObjectType.select(Book))

    execute = executor(Root)
    assert_that(
        execute("{ books { title authorId } }"),
        is_invalid_result(errors=contains_inanyorder(
            has_string(starts_with('Cannot query field "authorId"')),
        )),
    )
    # Check that internal fields can still be used for joining
    assert_that(
        execute("{ books { title author { name } } }"),
        is_successful_result(data={
            "books": [
                {"title": "Leave it to Psmith", "author": {"name": "PG Wodehouse"}},
                {"title": "The Code of the Woosters", "author": {"name": "PG Wodehouse"}},
            ],
        }),
    )


def test_field_set_can_be_used_to_declare_multiple_fields_in_one_attribute():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])
    BookRecord = attr.make_class("BookRecord", ["title"])

    class Author(StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

        name = field(type=GraphQLString)

    class Book(StaticDataObjectType):
        __records__ = [BookRecord("Leave it to Psmith")]

        title = field(type=GraphQLString)

    class Root(RootType):
        fields = field_set(
            author=single(lambda: StaticDataObjectType.select(Author)),
            book=single(lambda: StaticDataObjectType.select(Book)),
        )

    result = executor(Root)("{ author { name } book { title } }")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
        "book": {"title": "Leave it to Psmith"},
    }))


def test_arg_method_can_be_used_as_decorator_to_refine_query():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [
            AuthorRecord("PG Wodehouse"),
            AuthorRecord("Joseph Heller"),
        ]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))
        @author.arg("nameStartsWith", GraphQLString)
        def author_arg_starts_with(records, prefix):
            return list(filter(
                lambda record: record.name.startswith(prefix),
                records,
            ))

    result = executor(Root)("""{ author(nameStartsWith: "P") { name } }""")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_arg_refiner_can_take_context():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Author(StaticDataObjectType):
        __records__ = [
            AuthorRecord("PG Wodehouse"),
            AuthorRecord("Joseph Heller"),
        ]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))
        @author.arg("nameStartsWith", GraphQLBoolean)
        def author_arg_starts_with(records, _, context):
            return list(filter(
                lambda record: record.name.startswith(context),
                records,
            ))

    result = executor(Root)(
        """{ author(nameStartsWith: true) { name } }""",
        context="P",
    )
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_can_define_args_directly_on_field():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class DictQuery(object):
        @staticmethod
        def __select_all__():
            return {}

        @staticmethod
        def __add_arg__(args, arg_name, arg_value):
            args[arg_name] = arg_value
            return args

    class Author(ObjectType, DictQuery):
        __records__ = [
            AuthorRecord("PG Wodehouse"),
            AuthorRecord("Joseph Heller"),
        ]

        name = field(type=GraphQLString)

        @classmethod
        def __fetch_immediates__(cls, selections, query, context):
            records = cls.__records__
            if "nameStartsWith" in query:
                prefix = query["nameStartsWith"]
                records = list(filter(
                    lambda record: record.name.startswith(prefix),
                    records,
                ))

            return [
                tuple(
                    getattr(record, selection.field.attr_name)
                    for selection in selections
                )
                for record in records
            ]

    class Root(RootType):
        author = single(
            lambda: select(Author),
            args={
                "nameStartsWith": GraphQLString,
            },
        )

    result = executor(Root)("""{ author(nameStartsWith: "P") { name } }""")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_fields_can_be_defined_on_superclass():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class Named(object):
        name = field(type=GraphQLString)

    class Author(Named, StaticDataObjectType):
        __records__ = [AuthorRecord("PG Wodehouse")]

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))

    result = executor(Root)("{ author { name } }")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


def test_can_define_input_object_types():
    AuthorRecord = attr.make_class("AuthorRecord", ["name"])

    class AuthorSelection(InputObjectType):
        name_starts_with = field(type=GraphQLString)

    class Author(StaticDataObjectType):
        __records__ = [
            AuthorRecord("PG Wodehouse"),
            AuthorRecord("Joseph Heller"),
        ]

        name = field(type=GraphQLString)

    class Root(RootType):
        author = single(lambda: StaticDataObjectType.select(Author))
        @author.arg("selection", AuthorSelection)
        def author_arg_selection(records, selection):
            return list(filter(
                lambda record: record.name.startswith(selection.name_starts_with),
                records,
            ))

    result = executor(Root)("""{ author(selection: {nameStartsWith: "P"}) { name } }""")
    assert_that(result, is_successful_result(data={
        "author": {"name": "PG Wodehouse"},
    }))


class TestInputObjectType(object):
    def test_field_is_read_from_dict(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        assert_that(
            AuthorSelection.__read__({"nameStartsWith": "Bob"}),
            has_properties(name_starts_with="Bob"),
        )

    def test_missing_fields_have_value_of_undefined(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        assert_that(
            AuthorSelection.__read__({}),
            has_properties(name_starts_with=undefined),
        )

    def test_fields_are_recursively_read(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        class BookSelection(InputObjectType):
            author_selection = field(type=AuthorSelection)

        assert_that(
            BookSelection.__read__({"authorSelection": {"nameStartsWith": "Bob"}}),
            has_properties(
                author_selection=has_properties(name_starts_with="Bob"),
            ),
        )

    def test_missing_object_type_fields_have_value_of_undefined(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        class BookSelection(InputObjectType):
            author_selection = field(type=AuthorSelection)

        assert_that(
            BookSelection.__read__({}),
            has_properties(author_selection=undefined),
        )

    def test_object_type_field_of_null_is_read_as_none(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        class BookSelection(InputObjectType):
            author_selection = field(type=AuthorSelection)

        assert_that(
            BookSelection.__read__({"authorSelection": None}),
            has_properties(author_selection=None),
        )

    def test_can_instantiate_object_type(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        selection = AuthorSelection(name_starts_with="Bob")

        assert_that(
            selection,
            has_properties(name_starts_with="Bob"),
        )

    def test_unspecified_fields_are_undefined_when_instantiating_input_object_type(self):
        class AuthorSelection(InputObjectType):
            name_starts_with = field(type=GraphQLString)

        selection = AuthorSelection()

        assert_that(
            selection,
            has_properties(name_starts_with=undefined),
        )


def test_undefined_is_falsey():
    assert_that(bool(undefined), equal_to(False))


class TestSnakeCaseToCamelCase(object):
    @pytest.mark.parametrize("snake_case, camel_case", [
        ("one", "one"),
        ("one_two", "oneTwo"),
        ("one_", "one"),
    ])
    def test_string_without_underscores_is_unchanged(self, snake_case, camel_case):
        assert_that(_snake_case_to_camel_case(snake_case), equal_to(camel_case))


def test_name_of_object_type_can_be_overridden():
    class GeneratedType(ObjectType):
        __name__ = "User"

        email_address = field(type=GraphQLString)
        __fetch_immediates__ = None

    assert_that(GeneratedType.__name__, equal_to("User"))
    assert_that(GeneratedType.__graphql__.name, equal_to("User"))

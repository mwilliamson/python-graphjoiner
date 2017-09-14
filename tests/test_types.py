from graphjoiner import field, first_or_none, JoinType, many, single
from graphql import GraphQLInt, GraphQLNonNull
from hamcrest import assert_that, has_entries
import pytest

from .matchers import is_list_type, is_non_null, is_object_type, is_field, is_int


def test_join_types_are_not_nullable():
    object_type = JoinType(
        name="Object",
        fields=lambda: {"id": field(type=GraphQLInt)},
        fetch_immediates=None,
    )

    graphql_type = object_type.to_graphql_type()
    assert_that(graphql_type, is_non_null(is_object_type(
        fields=has_entries({
            "id": is_field(type=is_int),
        }),
    )))


@pytest.mark.parametrize("target_type, type_matcher", [
    (GraphQLInt, is_int),
    (GraphQLNonNull(GraphQLInt), is_int),
])
def test_single_produces_nullable_types(target_type, type_matcher):
    root_type = JoinType(
        name="Root",
        fields=lambda: {"value": single(Target(target_type), None)},
        fetch_immediates=None,
    )

    graphql_type = root_type.to_graphql_type()
    graphql_type.of_type.fields
    assert_that(graphql_type, is_non_null(is_object_type(
        fields=has_entries({
            "value": is_field(type=type_matcher),
        }),
    )))


@pytest.mark.parametrize("target_type, type_matcher", [
    (GraphQLInt, is_int),
    (GraphQLNonNull(GraphQLInt), is_int),
])
def test_first_or_none_produces_nullable_types(target_type, type_matcher):
    root_type = JoinType(
        name="Root",
        fields=lambda: {"value": first_or_none(Target(target_type), None)},
        fetch_immediates=None,
    )

    graphql_type = root_type.to_graphql_type()
    graphql_type.of_type.fields
    assert_that(graphql_type, is_non_null(is_object_type(
        fields=has_entries({
            "value": is_field(type=type_matcher),
        }),
    )))


@pytest.mark.parametrize("target_type, type_matcher", [
    (GraphQLInt, is_int),
    (GraphQLNonNull(GraphQLInt), is_non_null(is_int)),
])
def test_many_uses_type_of_target(target_type, type_matcher):
    root_type = JoinType(
        name="Root",
        fields=lambda: {"value": many(Target(target_type), None)},
        fetch_immediates=None,
    )

    graphql_type = root_type.to_graphql_type()
    graphql_type.of_type.fields
    assert_that(graphql_type, is_non_null(is_object_type(
        fields=has_entries({
            "value": is_field(type=is_list_type(type_matcher)),
        }),
    )))

# TODO: extract should combine nullability of parent and child


class Target(object):
    def __init__(self, type):
        self._type = type

    def to_graphql_type(self):
        return self._type

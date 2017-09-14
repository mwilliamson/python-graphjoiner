from graphql import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLField,
    GraphQLFloat,
    GraphQLInputObjectField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from hamcrest import (
    assert_that,
    equal_to,
    has_entries,
    has_properties,
)
import pytest

from graphjoiner.schemas import is_subtype, greatest_common_subtype, _common_supertype
from .matchers import (
    is_arg,
    is_field,
    is_list_type,
    is_int,
    is_input_field,
    is_input_object_type,
    is_non_null,
    is_object_type,
    is_schema,
    is_string,
)

class TestIsSubtype(object):
    @pytest.mark.parametrize("graphql_type", [
        GraphQLBoolean,
        GraphQLFloat,
        GraphQLInt,
        GraphQLString,
    ])
    def test_scalar_types_are_subtypes_of_themselves(self, graphql_type):
        assert is_subtype(graphql_type, graphql_type)

    @pytest.mark.parametrize("subtype, supertype", [
        (GraphQLBoolean, GraphQLFloat),
        (GraphQLFloat, GraphQLBoolean),
        (GraphQLInt, GraphQLBoolean),
        (GraphQLString, GraphQLBoolean),
    ])
    def test_scalar_types_are_not_subtypes_of_other_types(self, subtype, supertype):
        assert not is_subtype(subtype, supertype)

    def test_non_null_type_is_subtype_of_same_non_null_type(self):
        assert is_subtype(GraphQLNonNull(GraphQLInt), GraphQLNonNull(GraphQLInt))

    def test_non_null_type_is_subtype_of_same_null_type(self):
        assert is_subtype(GraphQLNonNull(GraphQLInt), GraphQLInt)

    def test_non_null_type_is_not_subtype_of_different_non_null_type(self):
        assert not is_subtype(GraphQLNonNull(GraphQLInt), GraphQLNonNull(GraphQLString))

    def test_non_null_type_is_not_subtype_of_different_null_type(self):
        assert not is_subtype(GraphQLNonNull(GraphQLInt), GraphQLString)

    def test_list_of_type_is_subtype_of_list_of_same_type(self):
        assert is_subtype(GraphQLList(GraphQLInt), GraphQLList(GraphQLInt))

    def test_list_of_type_is_subtype_of_list_of_supertype(self):
        assert is_subtype(GraphQLList(GraphQLNonNull(GraphQLInt)), GraphQLList(GraphQLInt))

    def test_list_of_type_is_not_subtype_of_list_of_subtype(self):
        assert not is_subtype(GraphQLList(GraphQLInt), GraphQLList(GraphQLNonNull(GraphQLInt)))

    def test_when_object_types_have_different_names_then_they_are_not_subtypes(self, object_type):
        assert not is_subtype(
            object_type("First", {"id": GraphQLInt}),
            object_type("Second", {"id": GraphQLInt}),
        )

    def test_when_object_types_have_same_name_and_fields_then_they_are_subtypes(self, object_type):
        assert is_subtype(
            object_type("Object", {"id": GraphQLInt}),
            object_type("Object", {"id": GraphQLInt}),
        )

    def test_when_object_type_field_is_of_different_type_then_it_is_not_a_subtype(self, object_type):
        assert not is_subtype(
            object_type("Object", {"id": GraphQLString}),
            object_type("Object", {"id": GraphQLInt}),
        )

    def test_object_type_field_can_be_subtype(self, object_type):
        assert is_subtype(
            object_type("Object", {"id": GraphQLNonNull(GraphQLInt)}),
            object_type("Object", {"id": GraphQLInt}),
        )

    def test_object_type_field_cannot_be_supertype(self, object_type):
        assert not is_subtype(
            object_type("Object", {"id": GraphQLInt}),
            object_type("Object", {"id": GraphQLNonNull(GraphQLInt)}),
        )

    def test_when_object_type_has_same_name_and_superset_of_fields_then_it_is_a_subtype(self):
        assert is_subtype(
            GraphQLObjectType("Object", fields={"id": GraphQLField(type=GraphQLInt), "name": GraphQLField(type=GraphQLString)}),
            GraphQLObjectType("Object", fields={"id": GraphQLField(type=GraphQLInt)}),
        )

    def test_when_object_type_has_same_name_and_subset_of_fields_then_it_is_not_a_subtype(self):
        assert not is_subtype(
            GraphQLObjectType("Object", fields={"id": GraphQLField(type=GraphQLInt)}),
            GraphQLObjectType("Object", fields={"id": GraphQLField(type=GraphQLInt), "name": GraphQLField(type=GraphQLString)}),
        )

    def test_when_object_type_has_same_name_and_has_different_field_name_then_it_is_not_a_subtype(self):
        assert not is_subtype(
            GraphQLObjectType("Object", fields={"id": GraphQLField(type=GraphQLString)}),
            GraphQLObjectType("Object", fields={"name": GraphQLField(type=GraphQLString)}),
        )

    def test_when_input_object_type_has_same_name_and_superset_of_fields_then_it_is_a_subtype(self):
        assert is_subtype(
            GraphQLInputObjectType("Object", {"id": GraphQLInputObjectField(type=GraphQLInt), "name": GraphQLInputObjectField(type=GraphQLString)}),
            GraphQLInputObjectType("Object", {"id": GraphQLInputObjectField(type=GraphQLInt)}),
        )

    def test_when_input_object_is_missing_nullable_field_then_it_is_a_subtype(self):
        assert is_subtype(
            GraphQLInputObjectType("Object", {"id": GraphQLInputObjectField(type=GraphQLInt)}),
            GraphQLInputObjectType("Object", {"id": GraphQLInputObjectField(type=GraphQLInt), "name": GraphQLInputObjectField(type=GraphQLString)}),
        )

    def test_when_input_object_is_missing_non_null_field_then_it_is_not_a_subtype(self):
        assert not is_subtype(
            GraphQLInputObjectType("Object", {"id": GraphQLInputObjectField(type=GraphQLInt)}),
            GraphQLInputObjectType("Object", {"id": GraphQLInputObjectField(type=GraphQLInt), "name": GraphQLInputObjectField(type=GraphQLNonNull(GraphQLString))}),
        )

    def test_when_field_has_same_args_then_is_subtype(self):
        assert is_subtype(
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLInt)},
                )
            }),
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLInt)},
                )
            }),
        )

    def test_when_field_has_arg_of_supertype_then_is_subtype(self):
        assert is_subtype(
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLInt)},
                )
            }),
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLNonNull(GraphQLInt))},
                )
            }),
        )

    def test_when_field_has_arg_of_subtype_then_is_not_subtype(self):
        assert not is_subtype(
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLNonNull(GraphQLInt))},
                )
            }),
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLInt)},
                )
            }),
        )

    def test_when_field_has_extra_nullable_args_then_is_subtype(self):
        assert is_subtype(
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLInt)},
                )
            }),
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={},
                )
            }),
        )

    def test_when_field_has_extra_non_null_args_then_is_not_subtype(self):
        assert not is_subtype(
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLNonNull(GraphQLInt))},
                )
            }),
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={},
                )
            }),
        )

    def test_when_arg_is_missing_then_is_not_subtype(self):
        assert not is_subtype(
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={},
                )
            }),
            GraphQLObjectType("Object", {
                "value": GraphQLField(
                    type=GraphQLNonNull(GraphQLInt),
                    args={"id": GraphQLArgument(type=GraphQLInt)},
                )
            }),
        )

    def test_when_query_is_subtype_then_schema_is_subtype(self):
        assert is_subtype(
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                    "name": GraphQLField(type=GraphQLString),
                }),
            ),
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ),
        )

    def test_when_query_is_not_subtype_then_schema_is_not_subtype(self):
        assert not is_subtype(
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ),
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                    "name": GraphQLField(type=GraphQLString),
                }),
            ),
        )

    def test_when_mutation_is_subtype_then_schema_is_subtype(self):
        assert is_subtype(
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                mutation=GraphQLObjectType("Mutation", fields={
                    "id": GraphQLField(type=GraphQLInt),
                    "name": GraphQLField(type=GraphQLString),
                }),
            ),
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                mutation=GraphQLObjectType("Mutation", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ),
        )

    def test_when_mutation_is_supertype_then_schema_is_subtype(self):
        assert not is_subtype(
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                mutation=GraphQLObjectType("Mutation", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ),
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                mutation=GraphQLObjectType("Mutation", fields={
                    "id": GraphQLField(type=GraphQLInt),
                    "name": GraphQLField(type=GraphQLString),
                }),
            ),
        )

    def test_when_mutation_is_missing_then_is_not_subtype_of_schema_with_mutation(self):
        assert not is_subtype(
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ),
            GraphQLSchema(
                query=GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                mutation=GraphQLObjectType("Mutation", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ),
        )

    def test_can_handle_recursive_types(self):
        obj_1 = GraphQLObjectType("Object", fields=lambda: {"self": GraphQLField(type=obj_1)})
        obj_2 = GraphQLObjectType("Object", fields=lambda: {"self": GraphQLField(type=obj_2)})

        assert is_subtype(obj_1, obj_2)

        obj_1 = GraphQLObjectType("Object", fields=lambda: {"self": GraphQLField(type=obj_1)})
        obj_2 = GraphQLObjectType("Object", fields=lambda: {"self": GraphQLField(type=GraphQLNonNull(obj_2))})

        assert not is_subtype(obj_1, obj_2)


class TestCommonSupertype(object):
    @pytest.mark.parametrize("graphql_type", [
        GraphQLBoolean,
        GraphQLFloat,
        GraphQLInt,
        GraphQLString,
    ])
    def test_scalar_types_are_merged_with_themselves(self, graphql_type):
        self._assert_merge(
            [graphql_type, graphql_type],
            equal_to(graphql_type),
        )

    def test_non_null_type_is_merged_with_nullable_type_to_nullable_type(self):
        self._assert_merge(
            [GraphQLNonNull(GraphQLInt), GraphQLInt],
            is_int,
        )

    def test_non_null_type_is_merged_with_same_non_null_type_to_same_type(self):
        self._assert_merge(
            [GraphQLNonNull(GraphQLInt), GraphQLNonNull(GraphQLInt)],
            is_non_null(is_int),
        )

    def test_types_within_non_null_types_are_merged(self):
        self._assert_merge(
            [
                GraphQLNonNull(GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLInt),
                })),
                GraphQLNonNull(GraphQLInputObjectType("Object", fields={
                    "name": GraphQLInputObjectField(type=GraphQLString),
                })),
            ],
            is_non_null(is_input_object_type(fields=has_entries({
                "id": is_input_field(type=is_int),
                "name": is_input_field(type=is_string),
            }))),
        )

    def test_types_within_list_types_are_merged(self):
        self._assert_merge(
            [
                GraphQLList(GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLInt),
                })),
                GraphQLList(GraphQLInputObjectType("Object", fields={
                    "name": GraphQLInputObjectField(type=GraphQLString),
                })),
            ],
            is_list_type(is_input_object_type(fields=has_entries({
                "id": is_input_field(type=is_int),
                "name": is_input_field(type=is_string),
            }))),
        )

    def test_merged_input_object_type_has_name_of_original_type(self):
        self._assert_merge(
            [
                GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLInt),
                }),
                GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLInt),
                }),
            ],
            has_properties(name="Object"),
        )

    def test_input_object_types_are_merged_to_input_object_type_with_union_of_fields(self):
        self._assert_merge(
            [
                GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLInt),
                }),
                GraphQLInputObjectType("Object", fields={
                    "name": GraphQLInputObjectField(type=GraphQLString),
                }),
            ],
            is_input_object_type(fields=has_entries({
                "id": is_input_field(type=is_int),
                "name": is_input_field(type=is_string),
            })),
        )

    def test_field_type_is_common_supertype_of_field_types(self):
        self._assert_merge(
            [
                GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLNonNull(GraphQLInt)),
                }),
                GraphQLInputObjectType("Object", fields={
                    "id": GraphQLInputObjectField(type=GraphQLInt),
                }),
            ],
            is_input_object_type(fields=has_entries({
                "id": is_input_field(type=is_int),
            })),
        )

    def _assert_merge(self, types, expected_type):
        merged = _common_supertype(*types)
        assert_that(merged, expected_type)
        assert_that(_common_supertype(*list(reversed(types))), expected_type)

        for type_ in types:
            assert is_subtype(type_, merged)


class TestCommonSubtype(object):
    @pytest.mark.parametrize("graphql_type", [
        GraphQLBoolean,
        GraphQLFloat,
        GraphQLInt,
        GraphQLString,
    ])
    def test_scalar_types_are_merged_with_themselves(self, graphql_type):
        self._assert_merge(
            [graphql_type, graphql_type],
            equal_to(graphql_type),
        )

    def test_non_null_type_is_merged_with_nullable_type_to_non_null_type(self):
        self._assert_merge(
            [GraphQLNonNull(GraphQLInt), GraphQLInt],
            is_non_null(is_int),
        )

    def test_non_null_type_is_merged_with_same_non_null_type_to_same_type(self):
        self._assert_merge(
            [GraphQLNonNull(GraphQLInt), GraphQLNonNull(GraphQLInt)],
            is_non_null(is_int),
        )

    def test_types_within_non_null_types_are_merged(self):
        self._assert_merge(
            [
                GraphQLNonNull(GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                })),
                GraphQLNonNull(GraphQLObjectType("Object", fields={
                    "name": GraphQLField(type=GraphQLString),
                })),
            ],
            is_non_null(is_object_type(fields=has_entries({
                "id": is_field(type=is_int),
                "name": is_field(type=is_string),
            }))),
        )

    def test_types_within_list_types_are_merged(self):
        self._assert_merge(
            [
                GraphQLList(GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                })),
                GraphQLList(GraphQLObjectType("Object", fields={
                    "name": GraphQLField(type=GraphQLString),
                })),
            ],
            is_list_type(is_object_type(fields=has_entries({
                "id": is_field(type=is_int),
                "name": is_field(type=is_string),
            }))),
        )

    def test_merged_object_type_has_name_of_original_type(self):
        self._assert_merge(
            [
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ],
            has_properties(name="Object"),
        )

    def test_object_types_are_merged_to_object_type_with_union_of_fields(self):
        self._assert_merge(
            [
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
                GraphQLObjectType("Object", fields={
                    "name": GraphQLField(type=GraphQLString),
                }),
            ],
            is_object_type(fields=has_entries({
                "id": is_field(type=is_int),
                "name": is_field(type=is_string),
            })),
        )

    def test_field_type_is_common_subtype_of_field_types(self):
        self._assert_merge(
            [
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLNonNull(GraphQLInt)),
                }),
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(type=GraphQLInt),
                }),
            ],
            is_object_type(fields=has_entries({
                "id": is_field(type=is_non_null(is_int)),
            })),
        )

    def test_field_args_is_union_of_original_field_args(self):
        self._assert_merge(
            [
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(
                        type=GraphQLInt,
                        args={"id": GraphQLArgument(type=GraphQLInt)},
                    ),
                }),
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(
                        type=GraphQLInt,
                        args={
                            "id": GraphQLArgument(type=GraphQLInt),
                            "name": GraphQLArgument(type=GraphQLString),
                        },
                    ),
                }),
            ],
            is_object_type(fields=has_entries({
                "id": is_field(args=has_entries({
                    "id": is_arg(type=is_int),
                    "name": is_arg(type=is_string),
                })),
            })),
        )

    def test_field_arg_type_is_common_supertype_of_arg_types(self):
        self._assert_merge(
            [
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(
                        type=GraphQLInt,
                        args={"id": GraphQLArgument(type=GraphQLNonNull(GraphQLInt))},
                    ),
                }),
                GraphQLObjectType("Object", fields={
                    "id": GraphQLField(
                        type=GraphQLInt,
                        args={"id": GraphQLArgument(type=GraphQLInt)},
                    ),
                }),
            ],
            is_object_type(fields=has_entries({
                "id": is_field(args=has_entries({
                    "id": is_arg(type=is_int),
                })),
            })),
        )

    def test_schema_queries_are_merged(self):
        self._assert_merge(
            [
                GraphQLSchema(
                    query=GraphQLObjectType("Object", fields={
                        "id": GraphQLField(type=GraphQLInt),
                    }),
                ),
                GraphQLSchema(
                    query=GraphQLObjectType("Object", fields={
                        "name": GraphQLField(type=GraphQLString),
                    }),
                ),
            ],
            is_schema(
                query=is_object_type(fields=has_entries({
                    "id": is_field(type=is_int),
                    "name": is_field(type=is_string),
                })),
            ),
        )

    def _assert_merge(self, types, expected_type):
        merged = greatest_common_subtype(types)
        assert_that(merged, expected_type)
        assert_that(greatest_common_subtype(list(reversed(types))), expected_type)

        for type_ in types:
            assert is_subtype(merged, type_)


@pytest.fixture(params=[
    (GraphQLObjectType, GraphQLField),
    (GraphQLInputObjectType, GraphQLInputObjectField),
])
def object_type(request):
    object_type, field = request.param
    return lambda name, field_types: object_type(name, fields=dict(
        (field_name, field(type=field_type))
        for field_name, field_type in field_types.items()
    ))

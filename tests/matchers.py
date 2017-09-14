from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInputObjectType,
    GraphQLInputObjectField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from hamcrest import all_of, equal_to, has_properties, instance_of


def is_successful_result(data):
    return has_properties(
        data=data,
        errors=equal_to([]),
        invalid=equal_to(False),
    )


def is_invalid_result(errors):
    return has_properties(
        data=equal_to(None),
        errors=errors,
        invalid=equal_to(True),
    )



is_int = equal_to(GraphQLInt)
is_string = equal_to(GraphQLString)


def is_non_null(matcher):
    return _type_matcher(GraphQLNonNull, has_properties(of_type=matcher))


def is_list_type(matcher):
    return _type_matcher(GraphQLList, has_properties(of_type=matcher))


def is_object_type(fields=None):
    if fields is None:
        return _type_matcher(GraphQLObjectType)
    else:
        return _type_matcher(GraphQLObjectType, has_properties(
            fields=fields,
        ))


def is_field(type=None, args=None):
    properties = {}
    if type is not None:
        properties["type"] = type
    if args is not None:
        properties["args"] = args

    return _type_matcher(GraphQLField, has_properties(**properties))


def is_arg(type):
    return _type_matcher(GraphQLArgument, has_properties(
        type=type,
    ))


def is_input_object_type(fields):
    return _type_matcher(GraphQLInputObjectType, has_properties(
        fields=fields,
    ))


def is_input_field(type):
    return _type_matcher(GraphQLInputObjectField, has_properties(
        type=type,
    ))

def is_schema(query):
    return _type_matcher(GraphQLSchema, has_properties(_query=query))


def _type_matcher(type_, matcher=None):
    type_matcher = instance_of(type_)
    if matcher is None:
        return type_matcher
    else:
        return all_of(type_matcher, matcher)

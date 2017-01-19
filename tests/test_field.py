from graphql import GraphQLString
from hamcrest import assert_that, has_key

import graphjoiner


def test_args_are_set_on_graphql_field():
    field = graphjoiner.field(
        args={"format": GraphQLString},
        type=GraphQLString,
    )

    assert_that(field.to_graphql_field().args, has_key("format"))

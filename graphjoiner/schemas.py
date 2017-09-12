from graphql import (
    build_ast_schema,
    GraphQLArgument,
    GraphQLField,
    GraphQLInputObjectField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
)
from graphql.language.parser import parse


def parse_schema(document):
    return build_ast_schema(parse(document))


def is_subtype(subtype, supertype):
    seen = set()

    def is_subtype(subtype, supertype):
        if (subtype, supertype) in seen:
            return True
        else:
            seen.add((subtype, supertype))
            if subtype == supertype:
                return True

            elif isinstance(subtype, GraphQLNonNull):
                if isinstance(supertype, GraphQLNonNull):
                    return is_subtype(subtype.of_type, supertype.of_type)
                else:
                    return is_subtype(subtype.of_type, supertype)

            elif isinstance(subtype, GraphQLList) and isinstance(supertype, GraphQLList):
                return is_subtype(subtype.of_type, supertype.of_type)

            elif isinstance(subtype, GraphQLObjectType) and isinstance(supertype, GraphQLObjectType):
                return _is_object_type_subtype(subtype, supertype)

            elif isinstance(subtype, GraphQLInputObjectType) and isinstance(supertype, GraphQLInputObjectType):
                return _is_input_object_type_subtype(subtype, supertype)

            elif isinstance(subtype, GraphQLSchema) and isinstance(supertype, GraphQLSchema):
                return all([
                    is_subtype(subtype.get_query_type(), supertype.get_query_type()),
                    supertype.get_mutation_type() is None or is_subtype(subtype.get_mutation_type(), supertype.get_mutation_type()),
                ])

            else:
                return False


    def _is_object_type_subtype(subtype, supertype):
        if subtype.name != supertype.name:
            return False
        elif not (set(subtype.fields.keys()) >= set(supertype.fields.keys())):
            return False
        else:
            return all(
                _is_subfield(subtype.fields[field_name], field)
                for field_name, field in supertype.fields.items()
            )


    def _is_subfield(subfield, superfield):
        return is_subtype(subfield.type, superfield.type) and all(
            _is_subarg(subfield.args.get(arg_name), superfield.args.get(arg_name))
            for arg_name in set(subfield.args.keys()) | set(superfield.args.keys())
        )


    def _is_subarg(subarg, superarg):
        if superarg is None:
            return not isinstance(subarg.type, GraphQLNonNull)

        elif subarg is None:
            return False

        else:
            return is_subtype(superarg.type, subarg.type)


    def _is_input_object_type_subtype(subtype, supertype):
        if subtype.name != supertype.name:
            return False
        else:
            return all(
                _is_sub_input_field(subtype.fields.get(field_name), supertype.fields.get(field_name))
                for field_name in set(subtype.fields.keys()) | set(supertype.fields.keys())
            )

    def _is_sub_input_field(subfield, superfield):
        if superfield is None:
            return True

        elif subfield is None:
            return not isinstance(superfield.type, GraphQLNonNull)

        else:
            return is_subtype(subfield.type, superfield.type)

    return is_subtype(subtype, supertype)


def greatest_common_subtype(types):
    """Merge GraphQL types into a single type

    This finds the type that is a subtype of all given types. It is
    assumed that such a type exists. Therefore, behaviour is undefined
    in the presence of conflicts, such as fields with incompatible
    types."""
    result = types[0]
    for type_ in types[1:]:
        result = _common_subtype(result, type_)
    return result


def _common_subtype(left, right):
    if left == right:
        return left

    elif isinstance(left, GraphQLNonNull) and isinstance(right, GraphQLNonNull):
        return GraphQLNonNull(_common_subtype(left.of_type, right.of_type))

    elif isinstance(left, GraphQLNonNull):
        return GraphQLNonNull(_common_subtype(left.of_type, right))

    elif isinstance(right, GraphQLNonNull):
        return GraphQLNonNull(_common_subtype(left, right.of_type))

    elif isinstance(left, GraphQLList) and isinstance(right, GraphQLList):
        return GraphQLList(_common_subtype(left.of_type, right.of_type))

    elif isinstance(left, GraphQLObjectType) and isinstance(right, GraphQLObjectType):
        fields = dict(
            (field_name, _common_subfield(left.fields.get(field_name), right.fields.get(field_name)))
            for field_name in set(left.fields.keys()) | set(right.fields.keys())
        )
        return GraphQLObjectType(left.name, fields=fields)

    elif isinstance(left, GraphQLSchema) and isinstance(right, GraphQLSchema):
        return GraphQLSchema(query=_common_subtype(left.get_query_type(), right.get_query_type()))

    else:
        raise ValueError("Cannot find common subtype")


def _common_subfield(left, right):
    if left is None:
        return right
    elif right is None:
        return left
    else:
        args = dict(
            (arg_name, _common_subarg(left.args.get(arg_name), right.args.get(arg_name)))
            for arg_name in set(left.args.keys()) | set(right.args.keys())
        )

        return GraphQLField(
            args=args,
            type=_common_subtype(left.type, right.type),
        )


def _common_subarg(left, right):
    if left is None:
        return right
    elif right is None:
        return left
    else:
        type_ = _common_supertype(left.type, right.type)
        return GraphQLArgument(type=type_)



def _common_supertype(left, right):
    if left == right:
        return left

    elif isinstance(left, GraphQLNonNull) and isinstance(right, GraphQLNonNull):
        return GraphQLNonNull(_common_supertype(left.of_type, right.of_type))

    elif isinstance(left, GraphQLNonNull):
        return _common_supertype(left.of_type, right)

    elif isinstance(right, GraphQLNonNull):
        return _common_supertype(left, right.of_type)

    elif isinstance(left, GraphQLList) and isinstance(right, GraphQLList):
        return GraphQLList(_common_supertype(left.of_type, right.of_type))

    elif isinstance(left, GraphQLInputObjectType) and isinstance(right, GraphQLInputObjectType):
        fields = dict(
            (field_name, _common_superfield(left.fields.get(field_name), right.fields.get(field_name)))
            for field_name in set(left.fields.keys()) | set(right.fields.keys())
        )

        return GraphQLInputObjectType(
            name=left.name,
            fields=fields,
        )

    else:
        raise ValueError("Cannot find common supertype")


def _common_superfield(left, right):
    if left is None:
        return right
    elif right is None:
        return left
    else:
        type = _common_supertype(left.type, right.type)
        return GraphQLInputObjectField(type=type)

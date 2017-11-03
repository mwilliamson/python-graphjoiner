from __future__ import absolute_import

import graphql
import six
import sqlalchemy
from sqlalchemy.orm import Query

from graphjoiner import declarative
from . import field, get_field_definitions, ObjectType, join_builder


class SqlAlchemyObjectType(ObjectType):
    @staticmethod
    def __get_session__(context):
        return context.session

    @classmethod
    def __primary_key__(cls):
        return cls.__model__.__mapper__.primary_key

    @classmethod
    def __select_all__(cls):
        query = Query([]).select_from(cls.__model__)
        # This is a workaround for a bug in SQLAlchemy:
        #    https://bitbucket.org/zzzeek/sqlalchemy/issues/3891/single-inh-criteria-should-be-added-for
        # When using polymorphic models, the filter on the type may not be
        # generated, so we explicitly include it here.

        polymorphic_identity = cls.__model__.__mapper__.polymorphic_identity

        if polymorphic_identity is None:
            return query
        else:
            return query.filter(cls.__model__.__mapper__.polymorphic_on == polymorphic_identity)

    @classmethod
    def __fetch_immediates__(cls, selections, query, context):
        query = query.with_entities(*(
            selection.field.column
            for selection in selections
        ))

        if not query._distinct:
            for primary_key_column in cls.__primary_key__():
                query = query.add_columns(primary_key_column)

            query = query.distinct()

        return query.with_session(cls.__get_session__(context)).all()


def column_field(column, type=None, internal=False):
    if type is None:
        type = _sql_column_to_graphql_type(column)
    return field(
        column=column,
        type=type,
        internal=internal,
    )


@join_builder
def sql_value_join(local, target, join):
    def build_query(parent_query, context):
        return parent_query.with_entities(*(
                local_field.column.label(remote_field.attr_name)
                for local_field, remote_field in six.iteritems(join)
            )) \
            .with_session(local.__get_session__(context)) \
            .all()

    join_fields = dict(
        (local_field.field_name, remote_field.field_name)
        for local_field, remote_field in six.iteritems(join)
    )

    return target, build_query, join_fields


@join_builder
def sql_join(local, target, join=None):
    if join is None:
        local_field_definition, remote_field_definition = _find_foreign_key(local, target)
        local_field = local_field_definition.field()
        remote_field = remote_field_definition.field()
        join = {local_field: remote_field}
    else:
        join = join.copy()

    def build_query(parent_query, context):
        parents = parent_query \
            .with_entities(*(
                local_field.column
                for local_field in join.keys()
            )) \
            .subquery()

        return target.__select_all__() \
            .join(parents, sqlalchemy.and_(
                parent_column == remote_field.column
                for parent_column, remote_field in zip(parents.c.values(), join.values())
            ))

    return target, build_query, dict(
        (local_field.field_name, remote_field.field_name)
        for local_field, remote_field in join.items()
    )


def _find_foreign_key(local, target):
    foreign_keys = list(_find_join_candidates(local, target))
    if len(foreign_keys) == 1:
        foreign_key, = foreign_keys
        return foreign_key
    else:
        raise Exception("Could not find unique foreign key from {} to {}".format(local.__name__, target.__name__))

def _find_join_candidates(local, target):
    for local_field, target_field in _find_join_candidates_directional(local, target):
        yield local_field, target_field
    for target_field, local_field in _find_join_candidates_directional(target, local):
        yield local_field, target_field

def _find_join_candidates_directional(local, remote):
    remote_tables = sqlalchemy.inspect(remote.__model__).tables

    for field_definition in _get_simple_field_definitions(local):
        orm_column = field_definition._kwargs.get("column")
        if orm_column is not None and hasattr(orm_column, "property"):
            columns = orm_column.property.columns
            if len(columns) == 1:
                column, = columns
                for foreign_key in column.foreign_keys:
                    if foreign_key.column.table in remote_tables:
                        remote_field = _find_field_for_column(remote, foreign_key.column)
                        yield field_definition, remote_field


def _find_field_for_column(cls, column):
    fields = [
        field_definition
        for field_definition in _get_simple_field_definitions(cls)
        if "column" in field_definition._kwargs and field_definition._kwargs["column"] == column
    ]

    if len(fields) == 1:
        return fields[0]
    else:
        raise Exception("Could not find unique field in {} for {}".format(cls.__name__, column))

def _get_simple_field_definitions(cls):
    for field_key, field_definition in get_field_definitions(cls):
        if isinstance(field_definition, declarative.SimpleFieldDefinition):
            yield field_definition


_type_mappings = [
    (sqlalchemy.Integer, graphql.GraphQLInt),
    (sqlalchemy.Float, graphql.GraphQLFloat),
    (sqlalchemy.String, graphql.GraphQLString),
    (sqlalchemy.Boolean, graphql.GraphQLBoolean),
]

def _sql_column_to_graphql_type(column):
    nullable_type = _sql_type_to_graphql_type(column.type)
    if getattr(column, "nullable", True):
        return nullable_type
    else:
        return graphql.GraphQLNonNull(nullable_type)


def _sql_type_to_graphql_type(sql_type):
    for mapped_sql_type, graphql_type in _type_mappings:
        if isinstance(sql_type, mapped_sql_type):
            return graphql_type

    raise Exception("Unknown SQL type: {}".format(sql_type))

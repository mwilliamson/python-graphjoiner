from __future__ import absolute_import

import six
from sqlalchemy.orm import Query

import graphjoiner
from graphjoiner import declarative
from . import create_join_type


def sqlalchemy_join_type(model):
    def create(cls):
        return create_join_type(
            cls,
            joiner=SqlAlchemyJoiner(cls, model),
        )
    
    return create
    
    
class SqlAlchemyJoiner(object):
    def __init__(self, cls, model):
        self._cls = cls
        self._model = model
    
    def simple_field(self, column):
        # TODO: SQLAlchemy type to GraphQL type
        return graphjoiner.field(column=column, type=None)
    
    def select(self):
        return Query([]).select_from(self._model)
        
    def join_to(self, target):
        foreign_keys = list(self._find_join_candidates(target))
        if len(foreign_keys) == 1:
            return dict(foreign_keys)
        else:
            raise Exception("TODO")
    
    def _find_join_candidates(self, target):
        for local_field, target_field in self._find_join_candidates_directional(self._cls, target):
            yield local_field, target_field
        for target_field, local_field in self._find_join_candidates_directional(target, self._cls):
            yield local_field, target_field
    
    def _find_join_candidates_directional(self, local, remote):
        for field_definition in self._get_simple_field_definitions(local):
            column, = field_definition._kwargs["column"].property.columns
            for foreign_key in column.foreign_keys:
                if remote._joiner._model.__table__ == foreign_key.column.table:
                    remote_primary_key_column, = foreign_key.column.table.primary_key
                    remote_field = self._find_field_for_column(remote, remote_primary_key_column)
                    yield field_definition.field_name, remote_field.field_name
        
    
    def _find_field_for_column(self, cls, column):
        for field_definition in self._get_simple_field_definitions(cls):
            if field_definition._kwargs["column"] == column:
                return field_definition
        raise Exception("Could not find find field in {} for {}".format(cls.__name__, column))
    
    def _get_simple_field_definitions(self, cls):
        for field_definition in six.itervalues(cls.__dict__):
            if isinstance(field_definition, declarative.SimpleFieldDefinition):
                yield field_definition
        
    
    def fetch_immediates(self, selections, query, context):
        query = query.with_entities(*(
            selection.field.column
            for selection in selections
        ))
        for primary_key_column in self._model.__mapper__.primary_key:
            query = query.add_columns(primary_key_column)
        keys = tuple(selection.key for selection in selections)
        
        return [
            dict(zip(keys, row))
            for row in query.distinct().with_session(context.session).all()
        ]

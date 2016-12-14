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
        for key, field in self._get_simple_fields(self._cls):
            column, = field.column.property.columns
            for foreign_key in column.foreign_keys:
                if target._joiner._model.__table__ == foreign_key.column.table:
                    remote_primary_key_column, = foreign_key.column.table.primary_key
                    yield key, self._find_field_for_column(target, remote_primary_key_column)[0]
    
    def _find_field_for_column(self, cls, column):
        for key, field in self._get_simple_fields(cls):
            if field.column == column:
                return key, field
        raise Exception("Could not find find field in {} for {}".format(cls.__name__, column))
    
    def _get_simple_fields(self, cls):
        for key, field_definition in six.iteritems(cls.__dict__):
            if isinstance(field_definition, declarative.SimpleFieldDefinition):
                yield key, getattr(cls, key)
        
    
    def fetch_immediates(self, selections, query, context):
        # TODO: add primary keys
        query = query.with_entities(*(
            selection.field.column
            for selection in selections
        ))
        keys = tuple(selection.key for selection in selections)
        return [
            dict(zip(keys, row))
            for row in query.with_session(context.session).all()
        ]

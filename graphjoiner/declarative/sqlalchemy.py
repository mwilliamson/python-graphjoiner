from __future__ import absolute_import

from sqlalchemy.orm import Query

import graphjoiner
from . import create_join_type


def sqlalchemy_join_type(model):
    def create(cls):
        return create_join_type(
            cls,
            fetch_immediates=fetch_immediates_from_query(model),
            joiner=SqlAlchemyJoiner(model),
        )
    
    return create
    
    
class SqlAlchemyJoiner(object):
    def __init__(self, model):
        self._model = model
    
    def simple_field(self, column):
        # TODO: SQLAlchemy type to GraphQL type
        return graphjoiner.field(column=column, type=None)
    
    def select(self):
        return Query([]).select_from(self._model)
    
    
# TODO: add primary keys
# TODO: don't need model?
def fetch_immediates_from_query(model):
    def fetch_immediates_from_query(selections, query, context):
        query = query.with_entities(*(
            selection.field.column
            for selection in selections
        ))
        keys = tuple(selection.key for selection in selections)

        return [
            dict(zip(keys, row))
            for row in query.with_session(context.session).all()
        ]

    return fetch_immediates_from_query

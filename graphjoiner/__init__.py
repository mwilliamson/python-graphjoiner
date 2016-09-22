import abc
from itertools import groupby

from attr import assoc
from graphql import GraphQLField, GraphQLObjectType, GraphQLList
from graphql.language.parser import parse
import six

from .requests import request_from_graphql_ast, Request, field_key
from .util import partition


def execute(root_entity, query, context=None):
    request = request_from_graphql_ast(parse(query).definitions[0], context=context)
    return root_entity.fetch(request, None)[0].value


class Result(object):
    def __init__(self, value, join_values):
        self.value = value
        self.join_values = join_values


class Value(six.with_metaclass(abc.ABCMeta, object)):
    @abc.abstractmethod
    def fetch(self, request):
        pass


def field(**kwargs):
    return Field(**kwargs)


class Field(object):
    def __init__(self, type, **kwargs):
        self.type = type
        for key, value in six.iteritems(kwargs):
            setattr(self, key, value)
    
    def to_graphql_field(self):
        return GraphQLField(
            type=self.type,
            resolver=_resolve_fetched_field,
        )


def _resolve_fetched_field(source, args, context, info):
    return source[field_key(info.field_asts[0])]


class Relationship(object):
    def __init__(self, target, process_results, wrap_type, select, join=None, args=None):
        if join is None:
            join = {}
        if args is None:
            args = {}

        self._target = target
        self._select = select
        self._join = join
        self._args = args
        self._process_results = process_results
        self._wrap_type = wrap_type

    @property
    def parent_join_keys(self):
        return self._join.keys()

    def fetch(self, request, select_parent):
        select = self._select(request, select_parent)
        join_selections = [Request(key=child_key, field_name=child_key) for child_key in self._join.values()]
        child_request = assoc(request, join_selections=join_selections)
        results = self._target.fetch(child_request, select)
        key_func = lambda result: result.join_values
        return RelationshipResults(results, self._process_results, self.parent_join_keys)
    
    def to_graphql_field(self):
        # TODO: differentiate between root and non-root types properly
        if self._join:
            resolve = _resolve_fetched_field
        else:
            def resolve(source, args, context, info):
                request = request_from_graphql_ast(info.field_asts[0], context=context)
                return self.fetch(request, None).get(())
                
        return GraphQLField(
            type=self._wrap_type(self._target.to_graphql_type()),
            resolver=resolve,
            args=self._args,
        )


class RelationshipResults(object):
    def __init__(self, results, process_results, parent_join_keys):
        key_func = lambda result: result.join_values
        self._results = dict(
            (key, [result.value for result in results])
            for key, results in groupby(sorted(results, key=key_func), key=key_func)
        )
        self._process_results = process_results
        self._parent_join_keys = parent_join_keys
    
    def _parent_join_values(self, parent):
        return tuple(parent[join_field] for join_field in self._parent_join_keys)
    
    def get(self, key):
        return self._process_results(self._results.get(self._parent_join_values(key), []))


def single(target, select, **kwargs):
    return Relationship(
        target=target,
        select=select,
        process_results=_one_or_none,
        wrap_type=lambda graphql_type: graphql_type,
        **kwargs
    )


def _one_or_none(values):
    if len(values) == 0:
        return None
    elif len(values) > 1:
        raise Exception("TODO")
    else:
        return values[0]


def many(target, select, **kwargs):
    return Relationship(
        target=target,
        select=select,
        process_results=lambda x: x,
        wrap_type=lambda graphql_type: GraphQLList(graphql_type),
        **kwargs
    )


class JoinType(Value):
    def __init__(self, name, fetch_immediates, fields):
        self.name = name
        self.fetch_immediates = fetch_immediates
        self.fields = fields
        self._graphql_type = None

    def fetch(self, request, select):
        fields = self.fields()

        (relationship_selections, requested_immediate_selections) = partition(
            lambda selection: isinstance(fields[selection.field_name], Relationship),
            request.selections,
        )

        join_to_children_selections = [
            Request(key=key, field_name=key)
            for selection in relationship_selections
            for key in fields[selection.field_name].parent_join_keys
        ]

        immediate_selections = requested_immediate_selections + list(request.join_selections) + join_to_children_selections

        results = self.fetch_immediates(
            fields,
            assoc(request, selections=immediate_selections),
            select,
        )
        
        for selection in relationship_selections:
            children = fields[selection.field_name].fetch(selection, select)
            for result in results:
                result[selection.key] = children.get(result)

        return [
            Result(
                dict((selection.key, result[selection.key]) for selection in request.selections),
                tuple(result[selection.field_name] for selection in request.join_selections),
            )
            for result in results
        ]
    
    def to_graphql_type(self):
        if self._graphql_type is None:
            self._graphql_type = GraphQLObjectType(
                name=self.name,
                fields=lambda: dict(
                    (name, field.to_graphql_field())
                    for name, field in six.iteritems(self.fields())
                ),
            )
            
        return self._graphql_type


def RootJoinType(**kwargs):
    return JoinType(fetch_immediates=lambda *_: [{}], **kwargs)

import abc
from itertools import groupby

from attr import assoc
from graphql import GraphQLField, GraphQLObjectType, GraphQLList
from graphql.language.parser import parse
import six

from .requests import request_from_graphql_ast, Request, field_key
from .util import partition


def execute(root, query, context=None):
    request = request_from_graphql_ast(parse(query).definitions[0], root, context=context)
    return root.fetch(request, None)[0].value


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
    _target = None
    args = {}
    
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
    def __init__(self, target, process_results, wrap_type, select, join=None, args=None, scalar=None):
        if join is None:
            join = {}
        if args is None:
            args = {}

        self._target = target
        self._select = select
        self._join = join
        self.args = args
        self._scalar = scalar
        self._process_results = process_results
        self._wrap_type = wrap_type
        
        self._parent_join_keys = tuple("_graphjoiner_joinToChildrenKey_" + parent_key for parent_key in self._join.keys())

    def parent_join_selections(self, parent):
        fields = parent.fields()
        return [
            Request(field=fields[field_name], key=key)
            for field_name, key in zip(self._join.keys(), self._parent_join_keys)
        ]

    def fetch(self, request, select_parent):
        select = self._select(request, select_parent)
        fields = self._target.fields()
        join_selections = [
            Request(key="_graphjoiner_joinToParentKey_" + child_key, field=fields[child_key])
            for child_key in self._join.values()
        ]
        if self._scalar is None:
            selections = request.selections
        else:
            selections = [Request(key=self._scalar, field=fields[self._scalar])]
        
        child_request = assoc(request, join_selections=join_selections, selections=selections)
        results = self._target.fetch(child_request, select)
        key_func = lambda result: result.join_values
        return RelationshipResults(
            results=results,
            process_results=self._process_results,
            parent_join_keys=self._parent_join_keys,
            scalar=self._scalar,
        )
    
    def to_graphql_field(self):
        # TODO: differentiate between root and non-root types properly
        if self._join:
            resolve = _resolve_fetched_field
        else:
            def resolve(source, args, context, info):
                request = request_from_graphql_ast(info.field_asts[0], self._target, context=context, field=self)
                return self.fetch(request, None).get(())
        
        if self._scalar is None:
            target = self._target.to_graphql_type()
        else:
            target = self._target.fields()[self._scalar].to_graphql_field().type
        
        return GraphQLField(
            type=self._wrap_type(target),
            resolver=resolve,
            args=self.args,
        )


class RelationshipResults(object):
    def __init__(self, results, process_results, parent_join_keys, scalar):
        key_func = lambda result: result.join_values
        self._results = dict(
            (key, [self._result_value(result, scalar) for result in results])
            for key, results in groupby(sorted(results, key=key_func), key=key_func)
        )
        self._process_results = process_results
        self._parent_join_keys = parent_join_keys
    
    @staticmethod
    def _result_value(result, scalar):
        value = result.value
        if scalar is None:
            return value
        else:
            return value[scalar]
    
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
            lambda selection: isinstance(selection.field, Relationship),
            request.selections,
        )

        join_to_children_selections = [
            parent_join_selection
            for selection in relationship_selections
            for parent_join_selection in selection.field.parent_join_selections(self)
        ]

        immediate_selections = requested_immediate_selections + list(request.join_selections) + join_to_children_selections

        results = self.fetch_immediates(
            assoc(request, selections=immediate_selections),
            select,
        )
        
        for selection in relationship_selections:
            children = selection.field.fetch(selection, select)
            for result in results:
                result[selection.key] = children.get(result)

        return [
            Result(
                dict((selection.key, result[selection.key]) for selection in request.selections),
                tuple(result[selection.key] for selection in request.join_selections),
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

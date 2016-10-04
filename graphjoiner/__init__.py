import abc
from itertools import groupby

from attr import assoc
from graphql import GraphQLField, GraphQLObjectType, GraphQLList
from graphql.language.parser import parse
import six

from .requests import request_from_graphql_ast, request_from_graphql_document, Request, field_key
from .util import partition, unique


def execute(root, query, context=None, variables=None):
    request = request_from_graphql_document(parse(query), root, context=context, variables=variables)
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


def relationship(join=None, args=None, **kwargs):
    if join is None:
        join = {}
    if args is None:
        args = {}

    return Relationship(join=join, args=args, **kwargs)


class Relationship(object):
    def __init__(self, target, process_results, wrap_type, select, join, args):
        self._target = target
        self._select = select
        self._join = join
        self.args = args
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
        select = self._select(request.args, select_parent)
        fields = self._target.fields()
        join_fields = self._target.join_fields()
        join_selections = [
            Request(key="_graphjoiner_joinToParentKey_" + child_key, field=join_fields[child_key])
            for child_key in self._join.values()
        ]

        child_request = assoc(request, join_selections=join_selections)
        results = self._target.fetch(child_request, select)
        key_func = lambda result: result.join_values
        return RelationshipResults(
            results=results,
            process_results=self._process_results,
            parent_join_keys=self._parent_join_keys,
        )

    def to_graphql_field(self):
        # TODO: differentiate between root and non-root types properly
        if self._join:
            resolve = _resolve_fetched_field
        else:
            def resolve(source, args, context, info):
                request = request_from_graphql_ast(
                    info.field_asts[0],
                    self._target,
                    context=context,
                    variables=info.variable_values,
                    field=self,
                    fragments=info.fragments,
                )
                return self.fetch(request, None).get(())

        return GraphQLField(
            type=self._wrap_type(self._target.to_graphql_type()),
            resolver=resolve,
            args=self.args,
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
    return relationship(
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
    return relationship(
        target=target,
        select=select,
        process_results=lambda x: x,
        wrap_type=lambda graphql_type: GraphQLList(graphql_type),
        **kwargs
    )



def extract(relationship, field_name):
    return Relationship(
        target=ScalarJoinType(relationship._target, field_name),
        process_results=relationship._process_results,
        wrap_type=relationship._wrap_type,
        select=relationship._select,
        join=relationship._join,
        args=relationship.args,
    )



class ScalarJoinType(Value):
    def __init__(self, target, field_name):
        self._target = target
        self._field_name = field_name

    @property
    def _field(self):
        return self._target.fields()[self._field_name]

    def fields(self):
        if isinstance(self._field, Relationship):
            return self._field._target.fields()
        else:
            return {}

    def join_fields(self):
        return self._target.join_fields()

    def fetch(self, request, select):
        field_request = Request(key=self._field_name, field=self._field, selections=request.selections, context=request.context)
        results = self._target.fetch(assoc(request, selections=[field_request]), select)
        return [
            Result(value=result.value[self._field_name], join_values=result.join_values)
            for result in results
        ]

    def to_graphql_type(self):
        return self._field.to_graphql_field().type


class JoinType(Value):
    def __init__(self, name, fetch_immediates, fields):
        self.name = name
        self.fetch_immediates = fetch_immediates
        self._generate_fields = fields
        self._fields = None
        self._graphql_type = None

    def fields(self):
        if self._fields is None:
            self._fields = self._generate_fields()
        return self._fields

    def join_fields(self):
        return self.fields()

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

        immediate_selections = unique(
            requested_immediate_selections + list(request.join_selections) + join_to_children_selections,
            key=lambda selection: selection.key,
        )

        results = self.fetch_immediates(immediate_selections, select, request.context)

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

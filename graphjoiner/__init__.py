import abc
from itertools import groupby

from attr import assoc
from graphql.language.parser import parse
import six

from .requests import request_from_graphql_ast


def execute(root_entity, query):
    request = request_from_graphql_ast(parse(query).definitions[0])
    return root_entity.fetch(request, None)[0].value


class Result(object):
    def __init__(self, value, join_values):
        self.value = value
        self.join_values = join_values


class Value(six.with_metaclass(abc.ABCMeta, object)):
    @abc.abstractmethod
    def fetch(self, request):
        pass


class RelationshipDefinition(object):
    def __init__(self, entity_cls, **kwargs):
        self._entity_cls = entity_cls
        self._kwargs = kwargs

    def instantiate(self, *args, **kwargs):
        entity_cls = self._entity_cls
        if not isinstance(entity_cls, type):
            entity_cls = entity_cls()
        return Relationship(entity_cls(*args, **kwargs), **self._kwargs)


class Relationship(object):
    def __init__(self, entity, process_results, default_value, generate_context, join=None):
        if join is None:
            join = {}

        self._entity = entity
        self._generate_context = generate_context
        self._join = join
        self._process_results = process_results
        self.default_value = default_value

    @property
    def parent_join_keys(self):
        return self._join.keys()

    def parent_join_values(self, parent):
        return tuple(parent[join_field] for join_field in self._join.keys())

    def fetch(self, request, context):
        child_context = self._generate_context(request, context)
        child_request = assoc(request, join_fields=self._join.values())
        results = self._entity.fetch(child_request, child_context)
        key_func = lambda result: result.join_values
        return dict(
            (key, self._process_results([result.value for result in results]))
            for key, results in groupby(sorted(results, key=key_func), key=key_func)
        )


def single(entity_cls, generate_context, **kwargs):
    return RelationshipDefinition(
        entity_cls=entity_cls,
        generate_context=generate_context,
        process_results=_one_or_none,
        default_value=None,
        **kwargs
    )


def _one_or_none(values):
    if len(values) == 0:
        return None
    elif len(values) > 1:
        raise Exception("TODO")
    else:
        return values[0]


def many(entity_cls, generate_context, **kwargs):
    return RelationshipDefinition(
        entity_cls=entity_cls,
        generate_context=generate_context,
        process_results=lambda x: x,
        default_value=[],
        **kwargs
    )


class JoinType(Value):
    def __init__(self, *args, **kwargs):
        generate_fields = self.fields
        self.fields = lambda: dict(
            (field_name, self._instantiate_field(field, args, kwargs))
            for field_name, field in generate_fields().items()
        )

    def _instantiate_field(self, field, args, kwargs):
        if isinstance(field, RelationshipDefinition):
            return field.instantiate(*args, **kwargs)
        else:
            return field

    @abc.abstractmethod
    def fetch_immediates(self, request, context):
        pass

    def fetch(self, request, context):
        fields = self.fields()

        requested_fields = request.children.keys()
        requested_immediate_fields = [
            field_name
            for field_name in requested_fields
            if not isinstance(fields[field_name], Relationship)
        ]
        requested_relationship_fields = [
            field_name
            for field_name in requested_fields
            if isinstance(fields[field_name], Relationship)
        ]

        join_to_children_fields = [
            join_field
            for field_name in requested_relationship_fields
            for join_field in fields[field_name].parent_join_keys
        ]

        fetch_fields = list(set(requested_immediate_fields + list(request.join_fields) + join_to_children_fields))

        results = self.fetch_immediates(
            assoc(
                request,
                children=dict((field, None) for field in fetch_fields),
            ),
            context,
        )

        for field_name, field in fields.items():
            if isinstance(field, Relationship):
                field_request = request.children.get(field_name)
                if field_request is not None:
                    children = field.fetch(field_request, context)
                    for result in results:
                        result[field_name] = children.get(field.parent_join_values(result), field.default_value)

        return [
            Result(
                dict((field, result[field]) for field in requested_fields),
                tuple(result[field] for field in request.join_fields),
            )
            for result in results
        ]


class RootJoinType(JoinType):
    def generate_context(self, request, context):
        return None
    
    def fetch_immediates(self, request, context):
        return [{}]

import abc
from itertools import groupby

from attr import assoc
from graphql import GraphQLField, GraphQLObjectType, GraphQLList
from graphql.language.parser import parse
import six

from .requests import request_from_graphql_ast


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
            resolver=lambda source, args, context, info: source[info.field_name],
        )


class RelationshipDefinition(object):
    def __init__(self, entity_cls, **kwargs):
        self._entity_cls = entity_cls
        self._kwargs = kwargs

    def instantiate(self, *args, **kwargs):
        instantiated_types = kwargs["__instantiated_types"]
        if self._entity_cls not in instantiated_types:
            instantiated_types[self._entity_cls] = self._entity_cls(*args, **kwargs)
            
        return Relationship(instantiated_types[self._entity_cls], **self._kwargs)


class Relationship(object):
    def __init__(self, target, process_results, wrap_type, generate_context, join=None, args=None):
        if join is None:
            join = {}
        if args is None:
            args = {}

        self._target = target
        self._generate_context = generate_context
        self._join = join
        self._args = args
        self._process_results = process_results
        self._wrap_type = wrap_type

    @property
    def parent_join_keys(self):
        return self._join.keys()

    def fetch(self, request, context):
        child_context = self._generate_context(request, context)
        child_request = assoc(request, join_fields=self._join.values())
        results = self._target.fetch(child_request, child_context)
        key_func = lambda result: result.join_values
        return RelationshipResults(results, self._process_results, self.parent_join_keys)
    
    def to_graphql_field(self):
        # TODO: differentiate between root and non-root types properly
        if self._join:
            def resolve(source, args, context, info):
                return source[info.field_name]
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


def single(entity_cls, generate_context, **kwargs):
    return RelationshipDefinition(
        entity_cls=entity_cls,
        generate_context=generate_context,
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


def many(entity_cls, generate_context, **kwargs):
    return RelationshipDefinition(
        entity_cls=entity_cls,
        generate_context=generate_context,
        process_results=lambda x: x,
        wrap_type=lambda graphql_type: GraphQLList(graphql_type),
        **kwargs
    )


class JoinType(Value):
    def __init__(self, *args, **kwargs):
        instantiated_types = kwargs.pop("__instantiated_types", {})
        
        generate_fields = self.fields
        self.fields = lambda: dict(
            (field_name, self._instantiate_field(field, args, kwargs, instantiated_types))
            for field_name, field in generate_fields().items()
        )
        self._graphql_type = None

    def _instantiate_field(self, field, args, kwargs, instantiated_types):
        if isinstance(field, RelationshipDefinition):
            return field.instantiate(*args, __instantiated_types=instantiated_types, **kwargs)
        else:
            return field

    @property
    def name(self):
        return type(self).__name__

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
                        result[field_name] = children.get(result)

        return [
            Result(
                dict((field, result[field]) for field in requested_fields),
                tuple(result[field] for field in request.join_fields),
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


class RootJoinType(JoinType):
    def generate_context(self, request, context):
        return None
    
    def fetch_immediates(self, request, context):
        return [{}]

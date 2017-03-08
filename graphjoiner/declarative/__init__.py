from functools import partial
import re

from graphql import GraphQLArgument, GraphQLInterfaceType
import six

import graphjoiner


def executor(root):
    root_type = root.__graphjoiner__
    return graphjoiner.executor(root_type)


class ObjectTypeMeta(type):
    def __new__(meta, name, bases, attrs):
        cls = super(ObjectTypeMeta, meta).__new__(meta, name, bases, attrs)
        if attrs.get("__abstract__"):
            return cls

        fields = _declare_fields(cls)

        cls.__graphjoiner__ = graphjoiner.JoinType(
            name=cls.__name__,
            fields=fields,
            fetch_immediates=cls.__fetch_immediates__,
            interfaces=_declare_interfaces(attrs),
        )

        return cls


def _declare_fields(cls):
    def fields():
        return dict(
            (field_definition.field_name, field_definition.__get__(None, cls))
            for key, field_definition in six.iteritems(cls.__dict__)
            if isinstance(field_definition, FieldDefinition)
        )

    for key, field_definition in six.iteritems(cls.__dict__):
        if isinstance(field_definition, FieldDefinition):
            field_definition.attr_name = key
            field_definition.field_name = _snake_case_to_camel_case(key)
            field_definition._owner = cls

    return fields


def _declare_interfaces(attrs):
    interfaces = attrs.get("__interfaces__", [])

    def to_graphql_core_interface(interface):
        if isinstance(interface, type) and issubclass(interface, InterfaceType):
            return interface.__graphql__
        else:
            return interface


    return list(map(to_graphql_core_interface, interfaces))


class ObjectType(six.with_metaclass(ObjectTypeMeta)):
    __abstract__ = True


class RootType(ObjectType):
    __abstract__ = True

    @staticmethod
    def __fetch_immediates__(*args):
        return [()]


class FieldDefinition(object):
    # TODO: make sure _owner isn't overwritten once set
    _owner = None
    _value = None
    field_name = None
    attr_name = None

    def __get__(self, obj, type=None):
        if self._owner is None:
            self._owner = type

        return self.field()

    def field(self):
        if self._value is None:
            self._value = self.instantiate()
            self._value.field_name = self.field_name
            self._value.attr_name = self.attr_name

        return self._value


def field(**kwargs):
    return SimpleFieldDefinition(**kwargs)


class SimpleFieldDefinition(FieldDefinition):
    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def instantiate(self):
        return graphjoiner.field(**self._kwargs)


def join_builder(build_join):
    def wrapped(target, *args, **kwargs):
        filter = kwargs.pop("filter", None)
        return lambda func: RelationshipDefinition(
            func=func,
            target=target,
            filter=filter,
            build_join=lambda local: build_join(local, target, *args, **kwargs),
        )

    return wrapped


def relationship(select_values, relationship_type):
    return LazyFieldDefinition(lambda: select_values()(relationship_type))

first_or_none = partial(relationship, relationship_type=graphjoiner.first_or_none)
single = partial(relationship, relationship_type=graphjoiner.single)
many = partial(relationship, relationship_type=graphjoiner.many)


class RelationshipDefinition(FieldDefinition):
    def __init__(self, func, target, filter, build_join):
        self._func = func
        self._target = target
        self._filter = filter
        self._build_join = build_join
        self._args = []

    def instantiate(self):
        build_query, join = self._build_join(self._owner)

        def build_query_with_args(args, parent_query, context):
            query = build_query(parent_query, context)

            if self._filter is not None:
                query = self._filter(query)

            for arg_name, _, refine_query in self._args:
                if arg_name in args:
                    query = refine_query(query, args[arg_name])

            return query

        args = dict(
            (arg_name, GraphQLArgument(arg_type))
            for arg_name, arg_type, _ in self._args
        )

        return self._func(self._target.__graphjoiner__, build_query_with_args, join=join, args=args)

    def arg(self, arg_name, arg_type):
        def add_arg(refine_query):
            self._args.append((arg_name, arg_type, refine_query))

        return add_arg


def extract(relationship, field_name):
    return ExtractFieldDefinition(relationship, field_name)


class ExtractFieldDefinition(FieldDefinition):
    def __init__(self, relationship, field_name):
        self._relationship = relationship
        self._field_name = field_name

    def instantiate(self):
        if self._relationship._owner is None:
            self._relationship._owner = self._owner

        return graphjoiner.extract(self._relationship.field(), self._field_name)


class LazyFieldDefinition(FieldDefinition):
    def __init__(self, func):
        self._func = func
        self._value = None
        self._setup = []

    def instantiate(self):
        field_definition = self._func()

        for setup in self._setup:
            setup(field_definition)

        field_definition.field_name = self.field_name
        field_definition.attr_name = self.attr_name
        return field_definition.__get__(None, self._owner)

    def arg(self, arg_name, arg_type):
        def add_arg(refine_query):
            self._setup.append(lambda field: field.arg(arg_name, arg_type)(refine_query))

        return add_arg



def _snake_case_to_camel_case(value):
    return value[0].lower() + re.sub(r"_(.)", lambda match: match.group(1).upper(), value[1:])


@join_builder
def select(local, target, join_query=None, join_fields=None):
    if join_fields is None:
        join_fields = {}
    else:
        join_fields = dict(
            (local_field.field_name, remote_field.field_name)
            for local_field, remote_field in six.iteritems(join_fields)
        )

    def build_query(parent_query, context):
        target_query = target.__select_all__()
        if join_query is None:
            return target_query
        else:
            return join_query(parent_query, target_query)

    return build_query, join_fields


class InterfaceTypeMeta(type):
    def __new__(meta, name, bases, attrs):
        cls = super(InterfaceTypeMeta, meta).__new__(meta, name, bases, attrs)
        if attrs.get("__abstract__"):
            return cls

        def fields():
            fields = _declare_fields(cls)()
            return dict(
                (key, field.to_graphql_field())
                for key, field in six.iteritems(fields)
            )

        cls.__graphql__ = GraphQLInterfaceType(
            name=cls.__name__,
            fields=fields,
            resolve_type=lambda: None,
        )

        return cls


class InterfaceType(six.with_metaclass(InterfaceTypeMeta)):
    __abstract__ = True

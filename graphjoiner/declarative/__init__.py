from functools import partial
import re

from graphql import GraphQLArgument
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

        def fields():
            return dict(
                (field_definition.field_name, field_definition.__get__(None, cls))
                for key, field_definition in six.iteritems(cls.__dict__)
                if isinstance(field_definition, FieldDefinition)
            )

        cls.__graphjoiner__ = graphjoiner.JoinType(
            name=cls.__name__,
            fields=fields,
            fetch_immediates=cls.__fetch_immediates__,
            interfaces=attrs.get("__interfaces__", []),
        )

        for key, field_definition in six.iteritems(cls.__dict__):
            if isinstance(field_definition, FieldDefinition):
                field_definition.attr_name = key
                field_definition.field_name = _snake_case_to_camel_case(key)
                field_definition._owner = cls

        return cls


class ObjectType(six.with_metaclass(ObjectTypeMeta)):
    __abstract__ = True

    @staticmethod
    def __field__(**kwargs):
        return graphjoiner.field(**kwargs)


class RootType(ObjectType):
    __abstract__ = True

    @staticmethod
    def __fetch_immediates__(*args):
        return [()]

    @staticmethod
    def __relationship__(target, join):
        def select(parent_select, context):
            return target.__select_all__()

        return select, {}


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


def field(func=None, **kwargs):
    if callable(func):
        return LazyFieldDefinition(func, **kwargs)
    else:
        return SimpleFieldDefinition(**kwargs)


class SimpleFieldDefinition(FieldDefinition):
    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def instantiate(self):
        return self._owner.__field__(**self._kwargs)


def _relationship_definition(func, target, join=None, filter=None):
    return RelationshipDefinition(
        func=func,
        target=target,
        join=join,
        filter=filter,
    )


first_or_none = partial(_relationship_definition, graphjoiner.first_or_none)
single = partial(_relationship_definition, graphjoiner.single)
many = partial(_relationship_definition, graphjoiner.many)


class RelationshipDefinition(FieldDefinition):
    def __init__(self, func, target, join, filter):
        self._func = func
        self._target = target
        self._join = join
        self._filter = filter
        self._args = []

    def instantiate(self):
        generate_select, join = self._owner.__relationship__(self._target, self._join)

        def generate_select_with_args(args, parent_select, context):
            select = generate_select(parent_select, context)

            if self._filter is not None:
                select = self._filter(select)

            for arg_name, _, refine_select in self._args:
                if arg_name in args:
                    select = refine_select(select, args[arg_name])

            return select

        args = dict(
            (arg_name, GraphQLArgument(arg_type))
            for arg_name, arg_type, _ in self._args
        )

        # TODO: in general join selection needs to consider both sides of the relationship
        return self._func(self._target.__graphjoiner__, generate_select_with_args, join=join, args=args)

    def arg(self, arg_name, arg_type):
        def add_arg(refine_select):
            self._args.append((arg_name, arg_type, refine_select))

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
        def add_arg(refine_select):
            self._setup.append(lambda field: field.arg(arg_name, arg_type)(refine_select))

        return add_arg



def _snake_case_to_camel_case(value):
    return value[0].lower() + re.sub(r"_(.)", lambda match: match.group(1).upper(), value[1:])

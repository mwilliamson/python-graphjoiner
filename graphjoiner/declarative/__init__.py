import collections
from functools import partial, wraps
import inspect
import re
import types

import attr
import graphql
from graphql import GraphQLArgument, GraphQLInputObjectType, GraphQLInterfaceType, GraphQLList, GraphQLNonNull
import six

import graphjoiner
from .lazy import lazy, lazy_property


def executor(root, mutation=None):
    root_type = root.__graphjoiner__
    if mutation is None:
        mutation_type = None
    else:
        mutation_type = mutation.__graphjoiner__

    return graphjoiner.executor(root_type, mutation=mutation_type)


class Type(object):
    pass


class InputType(Type):
    pass


def _is_declarative_input_type(type_):
    return (isinstance(type_, type) and issubclass(type_, InputType)) or isinstance(type_, InputType)


class ObjectTypeMeta(type):
    def __new__(meta, name, bases, attrs):
        cls = super(ObjectTypeMeta, meta).__new__(meta, name, bases, attrs)
        if attrs.get("__abstract__"):
            return cls

        _, fields = _declare_fields(cls)

        name = attrs.get("__name__")
        if name is not None:
            cls.__name__ = name

        cls.__graphjoiner__ = graphjoiner.JoinType(
            name=cls.__name__,
            fields=fields,
            fetch_immediates=getattr(cls, "__fetch_immediates__", None),
            interfaces=lambda: _declare_interfaces(attrs),
        )
        cls.__graphql__ = cls.__graphjoiner__.to_graphql_type()

        return cls


def get_field_definitions(cls):
    dicts = {}
    for base in reversed(inspect.getmro(cls)):
        dicts.update(base.__dict__)

    return [
        (field_key, field_definition)
        for key, value in six.iteritems(dicts)
        for field_key, field_definition in _attr_to_field_definitions(key, value)
    ]


def _attr_to_field_definitions(key, value):
    if isinstance(value, FieldDefinition):
        return ((key, value),)
    elif isinstance(value, FieldSet):
        return six.iteritems(value._fields)
    else:
        return ()


def _declare_fields(cls):
    field_definitions = get_field_definitions(cls)

    def fields():
        return dict(
            (field_definition.field_name, field_definition.__get__(None, cls))
            for key, field_definition in field_definitions
        )

    for key, field_definition in field_definitions:
        field_definition.attr_name = key
        field_definition.field_name = _snake_case_to_camel_case(key)
        field_definition._owner = cls

    return [
        field_definition
        for _, field_definition in field_definitions
    ], fields


def _declare_interfaces(attrs):
    interfaces = attrs.get("__interfaces__", [])
    if not isinstance(interfaces, collections.Iterable):
        interfaces = interfaces()

    def to_graphql_core_interface(interface):
        if isinstance(interface, type) and issubclass(interface, InterfaceType):
            return interface.__graphql__
        else:
            return interface


    return list(map(to_graphql_core_interface, interfaces))


class ObjectType(six.with_metaclass(ObjectTypeMeta, Type)):
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
    def __init__(self, type, **kwargs):
        self._type = type
        self._kwargs = kwargs

    @lazy_property
    def type(self):
        if isinstance(self._type, types.LambdaType):
            return self._type()
        else:
            return self._type

    def instantiate(self):
        type_ = _to_graphql_core_type(self.type)
        return graphjoiner.field(type=type_, **self._kwargs)


def _to_graphql_core_type(type_):
    if (isinstance(type_, type) and issubclass(type_, Type)) or isinstance(type_, Type):
        return type_.__graphql__
    else:
        return type_


def join_builder(build_join):
    def wrapped(*args, **kwargs):
        filter = kwargs.pop("filter", None)
        return lambda func: RelationshipDefinition(
            func=func,
            filter=filter,
            build_join=lambda local: build_join(local, *args, **kwargs),
        )

    wrapped.build = build_join

    return wrapped


def field_set(**fields):
    return FieldSet(fields)


class FieldSet(object):
    def __init__(self, fields):
        self._fields = fields


def relationship(select_values, relationship_type, args=None, internal=False):
    return LazyFieldDefinition(
        lambda: select_values()(partial(relationship_type, internal=internal)),
        args=args,
    )

first_or_null = partial(relationship, relationship_type=graphjoiner.first_or_null)
single = partial(relationship, relationship_type=graphjoiner.single)
single_or_null = partial(relationship, relationship_type=graphjoiner.single_or_null)
many = partial(relationship, relationship_type=graphjoiner.many)


class RelationshipDefinition(FieldDefinition):
    def __init__(self, func, filter, build_join):
        self._func = func
        self._filter = filter
        self._build_join = build_join
        self._args = []

    def instantiate(self):
        self._target, build_query, join = self._build_join(self._owner)

        def build_query_with_args(args, parent_query, context):
            query = build_query(parent_query, context=context)

            if self._filter is not None:
                query = self._filter(query)

            for arg_name, _, refine_query in self._args:
                if arg_name in args:
                    query = refine_query(query, args[arg_name], context=context)

            return query

        args = dict(
            (arg_name, GraphQLArgument(arg_type))
            for arg_name, arg_type, _ in self._args
        )

        return self._func(self._target.__graphjoiner__, build_query_with_args, join=join, args=args)

    def arg(self, arg_name, arg_type):
        def add_arg(refine_query):
            self._add_arg(arg_name, arg_type, refine_query)

        return add_arg

    def add_arg(self, arg_name, arg_type):
        self._add_arg(
            arg_name,
            arg_type,
            lambda args, arg_value: self._target.__add_arg__(args, arg_name, arg_value),
        )

    def _add_arg(self, arg_name, arg_type, refine_query):
        if _is_declarative_input_type(arg_type):
            read_arg_value = arg_type.__read__
            arg_type = arg_type.__graphql__
        else:
            read_arg_value = lambda x: x

        refine_query = _optional_argument("context", refine_query, positional_args=2)

        def new_refine_query(query, arg_value, *args, **kwargs):
            return refine_query(query, read_arg_value(arg_value), *args, **kwargs)

        self._args.append((arg_name, arg_type, new_refine_query))


def _optional_argument(arg_name, func, positional_args):
    func_args, _, _, _ = inspect.getargspec(func)
    extra_func_args = func_args[positional_args:]
    if arg_name in extra_func_args:
        return func
    else:
        @wraps(func)
        def new_func(*args, **kwargs):
            del kwargs[arg_name]
            return func(*args, **kwargs)

        return new_func


def extract(relationship, field):
    if isinstance(field, six.string_types):
        return ExtractFieldDefinition(relationship, field)
    else:
        return LazyFieldDefinition(lambda: ExtractFieldDefinition(relationship, field().field_name))


class ExtractFieldDefinition(FieldDefinition):
    def __init__(self, relationship, field_name):
        self._relationship = relationship
        self._field_name = field_name

    def instantiate(self):
        if self._relationship._owner is None:
            self._relationship._owner = self._owner

        return graphjoiner.extract(self._relationship.field(), self._field_name)


class LazyFieldDefinition(FieldDefinition):
    def __init__(self, func, args=None):
        if args is None:
            args = {}

        self._func = func
        self._value = None

        def arg_setup(arg_name, arg_type):
            return lambda field: field.add_arg(arg_name, arg_type)

        self._setup = [
            arg_setup(arg_name, arg_type)
            for arg_name, arg_type in six.iteritems(args)
        ]

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
    return value[0].lower() + re.sub(r"_(.)", lambda match: match.group(1).upper(), value[1:]).rstrip("_")


@join_builder
def select(local, target, join_query=None, join_fields=None):

    def build_query(parent_query):
        target_query = target.__select_all__()
        if join_query is None:
            return target_query
        else:
            return join_query(parent_query, target_query)

    return join.build(local, target, query=build_query, join_fields=join_fields)


@join_builder
def join(local, target, query, join_fields):
    build_query = _optional_argument("context", query, positional_args=1)

    if join_fields is None:
        join_fields = {}
    else:
        join_fields = dict(
            (local_field.field_name, remote_field.field_name)
            for local_field, remote_field in six.iteritems(join_fields)
        )

    return target, build_query, join_fields


class InterfaceTypeMeta(type):
    def __new__(meta, name, bases, attrs):
        cls = super(InterfaceTypeMeta, meta).__new__(meta, name, bases, attrs)
        if attrs.get("__abstract__"):
            return cls

        def fields():
            _, fields = _declare_fields(cls)
            return dict(
                (key, field.to_graphql_field())
                for key, field in six.iteritems(fields())
            )

        cls.__graphql__ = GraphQLInterfaceType(
            name=cls.__name__,
            fields=fields,
            resolve_type=lambda: None,
        )

        return cls


class InterfaceType(six.with_metaclass(InterfaceTypeMeta, Type)):
    __abstract__ = True


def fields(cls):
    return cls.__fields__()


class InputObjectTypeMeta(type):
    def __new__(meta, name, bases, attrs):
        cls = super(InputObjectTypeMeta, meta).__new__(meta, name, bases, attrs)
        if attrs.get("__abstract__"):
            return cls

        field_definitions, fields = _declare_fields(cls)
        fields = lazy(fields)
        cls.__fields__ = staticmethod(lambda: list(field_definitions))


        cls.__graphql__ = GraphQLInputObjectType(
            name=cls.__name__,
            fields=lambda: dict(
                (key, field.to_graphql_input_field())
                for key, field in six.iteritems(fields())
            ),
        )

        def __init__(self, **kwargs):
            attr.attrs(
                these=dict(
                    raw_=attr.attrib(default=undefined),
                    **dict(
                        (field.attr_name, attr.attrib(default=getattr(field, "default", undefined)))
                        for field in fields().values()
                    )
                ),
                cmp=False,
                slots=True,
                frozen=True,
            )(cls)
            return cls.__init__(self, **kwargs)

        cls.__init__ = __init__


        @staticmethod
        def read_arg_value(value):
            def get_value(field_definition):
                field = field_definition.__get__(None, cls)
                field_value = value[field.field_name]
                return _read_input_value(field_definition.type, field_value)

            return cls(
                raw_=value,
                **dict(
                    (field_definition.attr_name, get_value(field_definition))
                    for field_definition in field_definitions
                    if field_definition.field_name in value
                )
            )

        cls.__read__ = read_arg_value

        return cls


def _read_input_value(input_type, value):
    if value is not None and value is not undefined and _is_declarative_input_type(input_type):
        return input_type.__read__(value)
    else:
        return value


class InputObjectType(six.with_metaclass(InputObjectTypeMeta, InputType)):
    __abstract__ = True


class DictQuery(object):
    @staticmethod
    def __select_all__():
        return {}

    @staticmethod
    def __add_arg__(args, arg_name, arg_value):
        args = args.copy()
        args[arg_name] = arg_value
        return args


class Mutation(DictQuery):
    @classmethod
    def __fetch_immediates__(cls, *args, **kwargs):
        return cls.__mutate__(*args, **kwargs)


def mutation_field(target):
    return single(lambda: select(target()), args=target().__args__)


class _Undefined(object):
    def __bool__(self):
        return False

    def __nonzero__(self):
        return False

    def __str__(self):
        return "undefined"


undefined = _Undefined()


class ScalarInputType(InputType):
    @staticmethod
    def __read__(value):
        return value


class Boolean(ScalarInputType):
    __graphql__ = graphql.GraphQLBoolean


class Float(ScalarInputType):
    __graphql__ = graphql.GraphQLFloat


class Int(ScalarInputType):
    __graphql__ = graphql.GraphQLInt


class String(ScalarInputType):
    __graphql__ = graphql.GraphQLString


class NonNull(InputType):
    def __init__(self, of_type):
        self.of_type = of_type

    def __read__(self, value):
        return _read_input_value(self.of_type, value)

    @property
    def __graphql__(self):
        return GraphQLNonNull(_to_graphql_core_type(self.of_type))


class List(InputType):
    def __init__(self, of_type):
        self.of_type = of_type

    def __read__(self, value):
        if value is None or value is undefined:
            return value
        else:
            return [_read_input_value(self.of_type, element) for element in value]

    @property
    def __graphql__(self):
        return GraphQLList(_to_graphql_core_type(self.of_type))

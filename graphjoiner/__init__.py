import abc
import collections

from graphql import GraphQLError, GraphQLField, GraphQLInputObjectField, GraphQLNonNull, GraphQLObjectType, GraphQLList, GraphQLSchema
from graphql.execution import execute as graphql_execute, ExecutionResult
from graphql.execution.values import get_variable_values
from graphql.language import ast as ast_types
from graphql.language.parser import parse
from graphql.validation import validate
import six

from .requests import request_from_graphql_ast, request_from_graphql_document, Request, field_key
from .schemas import is_subtype
from .util import to_multidict


def executor(root, mutation=None):
    if mutation is None:
        mutation_type = None
    else:
        mutation_type = _nullable(mutation.to_graphql_type())

    default_schema = GraphQLSchema(
        query=_nullable(root.to_graphql_type()),
        mutation=mutation_type,
    )

    def execute(query, variables=None, context=None, schema=None):
        if schema is None:
            schema = default_schema
        elif not is_subtype(default_schema, schema):
            raise ValueError("schema argument must be superschema of main schema")

        return _execute(
            schema=schema,
            root=root,
            mutation=mutation,
            query=query,
            variables=variables,
            context=context,
        )

    return execute


def execute(root, *args, **kwargs):
    return executor(root)(*args, **kwargs)


def _execute(schema, root, query, context=None, variables=None, mutation=None):
    if variables is None:
        variables = {}

    try:
        ast = parse(query)

        validation_errors = validate(schema, ast)
        if validation_errors:
            return ExecutionResult(
                errors=validation_errors,
                invalid=True,
            )

        variable_definitions = [
            variable_definition
            for definition in ast.definitions
            if isinstance(definition, ast_types.OperationDefinition)
            for variable_definition in (definition.variable_definitions or [])
        ]
        variable_values = get_variable_values(schema, variable_definitions, variables)

        # The Python implementation of GraphQL currently lacks support
        # for nulls, so we use the uncoerced variables when handling the
        # request.
        #
        # See: https://github.com/graphql-python/graphql-core/issues/118
        request = request_from_graphql_document(ast, root, mutation_root=mutation, variables=variables)
        data = root.fetch(request.query, None, context=context)[0].value

        if request.schema_query is not None:
            schema_result = graphql_execute(
                schema,
                request.schema_query,
                variable_values=variable_values,
            )
            if schema_result.invalid:
                return schema_result

            data.update(schema_result.data)

        return ExecutionResult(data=data, errors=None)
    except GraphQLError as error:
        return ExecutionResult(errors=[error], invalid=True)


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


class FieldBase(object):
    pass


class Field(FieldBase):
    target = None
    args = {}

    def __init__(self, type, **kwargs):
        self.type = type
        for key, value in six.iteritems(kwargs):
            setattr(self, key, value)

    def immediate_selections(self, parent, selection):
        return (_request_to_immediate_selection(selection), )
    
    def create_reader(self, request, parent_query, context):
        return lambda immediates: immediates[0]

    def to_graphql_field(self):
        return GraphQLField(
            type=self.type,
            resolver=_resolve_fetched_field,
            args=self.args,
        )

    def to_graphql_input_field(self):
        return GraphQLInputObjectField(type=self.type)


def _resolve_fetched_field(source, info, **args):
    return source[field_key(info.field_asts[0])]


def relationship(join=None, args=None, internal=False, **kwargs):
    if join is None:
        join = {}
    if args is None:
        args = {}

    return Relationship(join=join, args=args, internal=internal, **kwargs)


class Relationship(FieldBase):
    def __init__(self, target, process_results, wrap_type, build_query, join, args, internal):
        self.target = target
        self.build_query = build_query
        self.join = join
        self.args = args
        self._process_results = process_results
        self._wrap_type = wrap_type
        self.internal = internal

        self._parent_join_keys = tuple("_graphjoiner_joinToChildrenKey_" + parent_key for parent_key in self.join.keys())

    def copy(self, target=None, build_query=None, join=None, args=None, internal=None):
        if target is None:
            target = self.target
        if build_query is None:
            build_query = self.build_query
        if join is None:
            join = self.join
        if args is None:
            args = self.args
        if internal is None:
            internal = self.internal

        return Relationship(
            target=target,
            build_query=build_query,
            join=join,
            args=args,
            wrap_type=self._wrap_type,
            process_results=self._process_results,
            internal=internal,
        )

    def immediate_selections(self, parent, selection):
        fields = parent.fields()
        return [
            _request_field(field=fields[field_name])
            for field_name in self.join.keys()
        ]

    def create_reader(self, request, parent_query, context):
        query = self.build_query(request.args, parent_query, context)
        join_fields = self.target.join_fields()
        join_selections = [
            _request_field(field=join_fields[child_key])
            for child_key in self.join.values()
        ]

        child_request = request.copy(join_selections=join_selections)
        results = self.target.fetch(child_request, query, context=context)
        
        indexed_results = to_multidict(
            (result.join_values, result.value)
            for result in results
        )
        
        return lambda immediates: self._process_results(indexed_results.get(immediates, []))

    def to_graphql_field(self):
        # TODO: differentiate between root and non-root types properly
        if self.join:
            resolve = _resolve_fetched_field
        else:
            def resolve(source, info, **args):
                request = request_from_graphql_ast(
                    info.field_asts[0],
                    self.target,
                    variables=info.variable_values,
                    field=self,
                    fragments=info.fragments,
                )
                return self.create_reader(request, None, context=info.context)(())

        return GraphQLField(
            type=self._wrap_type(self.target.to_graphql_type()),
            resolver=resolve,
            args=self.args,
        )


def single(target, build_query, **kwargs):
    return relationship(
        target=target,
        build_query=build_query,
        process_results=_single,
        wrap_type=lambda graphql_type: graphql_type,
        **kwargs
    )


def _single(values):
    if len(values) == 1:
        return values[0]
    else:
        raise GraphQLError("Expected 1 value but got {}".format(len(values)))


def single_or_null(target, build_query, **kwargs):
    return relationship(
        target=target,
        build_query=build_query,
        process_results=_single_or_none,
        wrap_type=lambda graphql_type: _nullable(graphql_type),
        **kwargs
    )


def _single_or_none(values):
    if len(values) == 0:
        return None
    elif len(values) > 1:
        raise GraphQLError("Expected up to 1 value but got {}".format(len(values)))
    else:
        return values[0]


def first_or_null(target, build_query, **kwargs):
    return relationship(
        target=target,
        build_query=build_query,
        process_results=_first_or_none,
        wrap_type=lambda graphql_type: _nullable(graphql_type),
        **kwargs
    )


def _first_or_none(values):
    if len(values) == 0:
        return None
    else:
        return values[0]


def many(target, build_query, **kwargs):
    return relationship(
        target=target,
        build_query=build_query,
        process_results=lambda x: x,
        wrap_type=lambda graphql_type: GraphQLNonNull(GraphQLList(graphql_type)),
        **kwargs
    )



def extract(relationship, field_name):
    return relationship.copy(
        target=ScalarJoinType(relationship.target, field_name),
        internal=False,
    )



class ScalarJoinType(Value):
    def __init__(self, target, field_name):
        self._target = target
        self._field_name = field_name

    @property
    def _field(self):
        return self._target.fields()[self._field_name]

    def fields(self):
        return self._field.target.fields()

    def join_fields(self):
        return self._target.join_fields()

    def fetch(self, request, query, context):
        field_request = Request(
            key=self._field_name,
            field=self._field,
            selections=request.selections,
            join_selections=(),
            args={},
        )
        results = self._target.fetch(request.copy(selections=[field_request]), query, context=context)
        return [
            Result(value=result.value[self._field_name], join_values=result.join_values)
            for result in results
        ]

    def to_graphql_type(self):
        return self._field.to_graphql_field().type


class JoinType(Value):
    def __init__(self, name, fetch_immediates, fields, interfaces=None):
        if interfaces is None:
            interfaces = ()

        self._name = name
        self._fetch_immediates = fetch_immediates
        self._generate_fields = fields
        self._interfaces = interfaces
        self._fields = None
        self._graphql_type = None

    def fields(self):
        if self._fields is None:
            self._fields = self._generate_fields()
        return self._fields

    def join_fields(self):
        return self.fields()

    def fetch(self, request, query, context):
        immediate_selections = []
        immediate_slices = []
        
        for selection in request.selections:
            immediate_selections_for_field = selection.field.immediate_selections(self, selection)
            immediate_slices.append(slice(
                len(immediate_selections),
                len(immediate_selections) + len(immediate_selections_for_field),
            ))
            immediate_selections += immediate_selections_for_field
            
        rows = self._fetch_immediates(tuple(immediate_selections) + tuple(request.join_selections), query, context)
        
        readers = []
        
        for selection, immediate_slice in zip(request.selections, immediate_slices):
            reader = selection.field.create_reader(selection, query, context)
            readers.append((selection.key, immediate_slice, reader))
        
        def read_row(row):
            return Result(
                dict(
                    (key, read(row[immediate_slice]))
                    for key, immediate_slice, read in readers
                ),
                row[len(immediate_selections):],
            )
    
        return [
            read_row(row)
            for row in rows
        ]

    def to_graphql_type(self):
        if self._graphql_type is None:
            self._graphql_type = GraphQLObjectType(
                name=self._name,
                fields=lambda: collections.OrderedDict(
                    (name, field.to_graphql_field())
                    for name, field in six.iteritems(self.fields())
                    if not getattr(field, "internal", False)
                ),
                interfaces=self._interfaces,
            )

        return GraphQLNonNull(self._graphql_type)


def RootJoinType(**kwargs):
    return JoinType(fetch_immediates=lambda *_: [()], **kwargs)


def _nullable(graphql_type):
    if isinstance(graphql_type, GraphQLNonNull):
        return graphql_type.of_type
    else:
        return graphql_type


class ImmediateSelection(object):
    def __init__(self, field, args):
        self.field = field
        self.args = args
        
        
def _request_field(field):
    return ImmediateSelection(
        field=field,
        args={},
    )


def _request_to_immediate_selection(request):
    return ImmediateSelection(field=request.field, args=request.args)

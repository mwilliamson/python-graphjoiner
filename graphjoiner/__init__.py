import abc
from functools import partial
from itertools import groupby

from attr import assoc
from graphql import GraphQLError, GraphQLField, GraphQLObjectType, GraphQLList, GraphQLSchema
from graphql.execution import execute as graphql_execute, ExecutionResult
from graphql.language.parser import parse
from graphql.validation import validate
import six

from .requests import request_from_graphql_ast, request_from_graphql_document, Request, field_key
from .util import partition, unique


def executor(root):
    schema = GraphQLSchema(query=root.to_graphql_type())
    return partial(_execute, schema, root)


def execute(root, *args, **kwargs):
    return executor(root)(*args, **kwargs)


def _execute(schema, root, query, context=None, variables=None):
    try:
        schema = GraphQLSchema(query=root.to_graphql_type())
        ast = parse(query)
        validation_errors = validate(schema, ast)
        if validation_errors:
            return ExecutionResult(
                errors=validation_errors,
                invalid=True,
            )

        request = request_from_graphql_document(ast, root, context=context, variables=variables)
        data = root.fetch(request.query, None)[0].value

        if request.schema_query is not None:
            schema_result = graphql_execute(
                schema,
                request.schema_query,
                variable_values=variables,
            )
            if schema_result.invalid:
                return schema_result

            data.update(schema_result.data)

        return ExecutionResult(data=data, errors=[])
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

    def to_graphql_field(self):
        return GraphQLField(
            type=self.type,
            resolver=_resolve_fetched_field,
            args=self.args,
        )


def _resolve_fetched_field(source, args, context, info):
    return source[field_key(info.field_asts[0])]


def relationship(join=None, args=None, **kwargs):
    if join is None:
        join = {}
    if args is None:
        args = {}

    return Relationship(join=join, args=args, **kwargs)


class Relationship(FieldBase):
    def __init__(self, target, process_results, wrap_type, build_query, join, args):
        self.target = target
        self.build_query = build_query
        self.join = join
        self.args = args
        self._process_results = process_results
        self._wrap_type = wrap_type

        self._parent_join_keys = tuple("_graphjoiner_joinToChildrenKey_" + parent_key for parent_key in self.join.keys())

    def copy(self, target=None, build_query=None, join=None, args=None):
        if target is None:
            target = self.target
        if build_query is None:
            build_query = self.build_query
        if join is None:
            join = self.join
        if args is None:
            args = self.args

        return Relationship(
            target=target,
            build_query=build_query,
            join=join,
            args=args,
            wrap_type=self._wrap_type,
            process_results=self._process_results,
        )

    def parent_join_selections(self, parent):
        fields = parent.fields()
        return [
            Request(field=fields[field_name], key=key)
            for field_name, key in zip(self.join.keys(), self._parent_join_keys)
        ]

    def fetch(self, request, parent_query):
        query = self.build_query(request.args, parent_query, request.context)
        join_fields = self.target.join_fields()
        join_selections = [
            Request(key="_graphjoiner_joinToParentKey_" + child_key, field=join_fields[child_key])
            for child_key in self.join.values()
        ]

        child_request = assoc(request, join_selections=join_selections)
        results = self.target.fetch(child_request, query)
        return RelationshipResults(
            results=results,
            process_results=self._process_results,
            parent_join_keys=self._parent_join_keys,
        )

    def to_graphql_field(self):
        # TODO: differentiate between root and non-root types properly
        if self.join:
            resolve = _resolve_fetched_field
        else:
            def resolve(source, args, context, info):
                request = request_from_graphql_ast(
                    info.field_asts[0],
                    self.target,
                    context=context,
                    variables=info.variable_values,
                    field=self,
                    fragments=info.fragments,
                )
                return self.fetch(request, None).get(())

        return GraphQLField(
            type=self._wrap_type(self.target.to_graphql_type()),
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


def single(target, build_query, **kwargs):
    return relationship(
        target=target,
        build_query=build_query,
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


def first_or_none(target, build_query, **kwargs):
    return relationship(
        target=target,
        build_query=build_query,
        process_results=_first_or_none,
        wrap_type=lambda graphql_type: graphql_type,
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
        wrap_type=lambda graphql_type: GraphQLList(graphql_type),
        **kwargs
    )



def extract(relationship, field_name):
    return relationship.copy(
        target=ScalarJoinType(relationship.target, field_name),
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
            return self._field.target.fields()
        else:
            return {}

    def join_fields(self):
        return self._target.join_fields()

    def fetch(self, request, query):
        field_request = Request(key=self._field_name, field=self._field, selections=request.selections, context=request.context)
        results = self._target.fetch(assoc(request, selections=[field_request]), query)
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

    def fetch(self, request, query):
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


        keys = tuple(selection.key for selection in immediate_selections)

        results = [
            dict(zip(keys, row))
            for row in self._fetch_immediates(immediate_selections, query, request.context)
        ]

        for selection in relationship_selections:
            children = selection.field.fetch(selection, query)
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
                name=self._name,
                fields=lambda: dict(
                    (name, field.to_graphql_field())
                    for name, field in six.iteritems(self.fields())
                ),
                interfaces=self._interfaces,
            )

        return self._graphql_type


def RootJoinType(**kwargs):
    return JoinType(fetch_immediates=lambda *_: [()], **kwargs)

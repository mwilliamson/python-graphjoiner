import re

from graphql import GraphQLArgument
import six

import graphjoiner


def executor(root):
    root_type = root._graphjoiner
    
    def execute(*args, **kwargs):
        return graphjoiner.execute(root_type, *args, **kwargs)
    
    return execute


def root_join_type(cls):
    return create_join_type(cls, joiner=RootJoiner())


class RootJoiner(object):
    def fetch_immediates(self, *args):
        return [{}]
    
    def join_select(self, target, parent_select, child_select):
        return child_select
    
    def join_to(self, target):
        return {}


def create_join_type(cls, joiner):
    def fields():
        return dict(
            (field_definition.field_name, field_definition.__get__(None, cls))
            for key, field_definition in six.iteritems(cls.__dict__)
            if isinstance(field_definition, FieldDefinition)
        )
    
    cls._graphjoiner = graphjoiner.JoinType(
        name=cls.__name__,
        fields=fields,
        fetch_immediates=joiner.fetch_immediates,
    )
    cls._joiner = joiner
    
    for key, field_definition in six.iteritems(cls.__dict__):
        if isinstance(field_definition, FieldDefinition):
            field_definition.field_name = _snake_case_to_camel_case(key)
            field_definition._owner = cls
    
    return cls


class FieldDefinition(object):
    _owner = None
    
    def __get__(self, obj, type=None):
        if self._owner is None:
            self._owner = type
            
        return self.field()


def field(**kwargs):
    return SimpleFieldDefinition(**kwargs)


class SimpleFieldDefinition(FieldDefinition):
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._value = None
    
    def field(self):
        if self._value is None:
            self._value = self._instantiate()
        
        return self._value
    
    def _instantiate(self):
        return self._owner._joiner.simple_field(**self._kwargs)


def single(target):
    return RelationshipDefinition(graphjoiner.single, target)


def many(target):
    return RelationshipDefinition(graphjoiner.many, target)


class RelationshipDefinition(FieldDefinition):
    def __init__(self, func, target):
        self._func = func
        self._get_target = target
        self._value = None
        self._args = []
    
    def field(self):
        if self._value is None:
            self._value = self._instantiate()
        
        return self._value
    
    @property
    def _target(self):
        if hasattr(self._get_target, "_graphjoiner"):
            return self._get_target
        else:
            return self._get_target()
    
    def _instantiate(self):
        def generate_select(args, parent_select):
            select = self._target._joiner.select()
            select = self._owner._joiner.join_select(self._target, parent_select, select)
            
            for arg_name, _, refine_select in self._args:
                if arg_name in args:
                    select = refine_select(select, args[arg_name])
            
            return select
        
        return self._func(
            self._target._graphjoiner,
            select=generate_select,
            # TODO: in general join selection needs to consider both sides of the relationship
            join=self._owner._joiner.join_to(self._target),
            args=dict(
                (arg_name, GraphQLArgument(arg_type))
                for arg_name, arg_type, _ in self._args
            ),
        )
        
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
    
    def field(self):
        return graphjoiner.extract(self._relationship.field(), self._field_name)
        


def _snake_case_to_camel_case(value):
    return value[0].lower() + re.sub(r"_(.)", lambda match: match.group(1).upper(), value[1:])

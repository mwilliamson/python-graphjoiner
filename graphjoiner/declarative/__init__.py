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
    
    def join_to(self, target):
        return {}


def create_join_type(cls, joiner):
    def fields():
        # TODO: snake_case to camelCase
        return dict(
            (key, getattr(cls, key))
            for key in dir(cls)
            if isinstance(getattr(cls, key), graphjoiner.FieldBase)
        )
    
    cls._graphjoiner = graphjoiner.JoinType(
        name=cls.__name__,
        fields=fields,
        fetch_immediates=joiner.fetch_immediates,
    )
    cls._joiner = joiner
    
    return cls


class FieldDefinition(object):
    pass


def field(**kwargs):
    return SimpleFieldDefinition(**kwargs)


class SimpleFieldDefinition(FieldDefinition):
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._value = None
    
    def __get__(self, obj, type=None):
        if self._value is None:
            self._owner = type
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
        self._target = target
        self._value = None
        self._args = []
    
    def __get__(self, obj, type=None):
        if self._value is None:
            self._owner = type
            self._value = self._instantiate()
        
        return self._value
    
    def _instantiate(self):
        def generate_select(args, parent_select):
            select = self._target._joiner.select()
            
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
    pass



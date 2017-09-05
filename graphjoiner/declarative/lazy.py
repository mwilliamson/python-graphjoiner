import functools


def lazy(func):
    result = []

    def get():
        if len(result) == 0:
            result.append(func())

        return result[0]

    return get


class lazy_property(object):
    def __init__(self, func):
        self._func = func
        functools.wraps(self._func)(self)

    def __get__(self, obj, cls):
        if obj is None:
            return self

        value = obj.__dict__[self.__name__] = self._func(obj)
        return value

def partition(func, values):
    true = []
    false = []

    for value in values:
        if func(value):
            true.append(value)
        else:
            false.append(value)

    return true, false


def single(values):
    if len(values) == 1:
        return values[0]
    else:
        raise Exception("Expected 1 but got {}".format(len(values)))


def find(predicate, values):
    for value in values:
        if predicate(value):
            return value


def unique(values, key):
    result = []
    seen = set()

    for value in values:
        key_value = key(value)
        if key_value not in seen:
            seen.add(key_value)
            result.append(value)

    return result

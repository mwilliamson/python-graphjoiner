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

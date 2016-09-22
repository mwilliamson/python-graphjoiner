def partition(func, values):
    true = []
    false = []
    
    for value in values:
        if func(value):
            true.append(value)
        else:
            false.append(value)

    return true, false

def lazy(func):
    result = []

    def get():
        if len(result) == 0:
            result.append(func())

        return result[0]

    return get

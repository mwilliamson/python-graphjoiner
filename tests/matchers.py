from hamcrest import equal_to, has_properties


def is_successful_result(data):
    return has_properties(
        data=data,
        errors=equal_to([]),
        invalid=equal_to(False),
    )

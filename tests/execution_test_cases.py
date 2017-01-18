from hamcrest import assert_that

from .matchers import is_successful_result


class ExecutionTestCases(object):
    def test_querying_list_of_entities(self):
        query = """
            {
                books {
                    id
                    title
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "books": [
                {
                    "id": 1,
                    "title": "Leave It to Psmith",
                },
                {
                    "id": 2,
                    "title": "Right Ho, Jeeves",
                },
                {
                    "id": 3,
                    "title": "Catch-22",
                },
            ]
        }))


    def test_querying_list_of_entities_with_child_entity(self):
        query = """
            {
                books {
                    id
                    author {
                        name
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "books": [
                {
                    "id": 1,
                    "author": {
                        "name": "PG Wodehouse",
                    },
                },
                {
                    "id": 2,
                    "author": {
                        "name": "PG Wodehouse",
                    },
                },
                {
                    "id": 3,
                    "author": {
                        "name": "Joseph Heller",
                    },
                },
            ]
        }))


    def test_querying_single_entity_with_arg(self):
        # TODO: add test for non-top-level arg
        query = """
            {
                author(id: 1) {
                    name
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "name": "PG Wodehouse",
            },
        }))


    def test_single_entity_is_null_if_not_found(self):
        query = """
            {
                author(id: 100) {
                    name
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": None,
        }))



    def test_querying_single_entity_with_child_entities(self):
        query = """
            {
                author(id: 1) {
                    books {
                        title
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "books": [
                    {"title": "Leave It to Psmith"},
                    {"title": "Right Ho, Jeeves"},
                ],
            },
        }))


    def test_querying_extracted_scalar(self):
        query = """
            {
                author(id: 1) {
                    bookTitles
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "bookTitles": [
                    "Leave It to Psmith",
                    "Right Ho, Jeeves",
                ],
            },
        }))


    def test_querying_extracted_object(self):
        query = """
            {
                book(id: 1) {
                    booksBySameAuthor {
                        title
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "booksBySameAuthor": [
                    {"title": "Leave It to Psmith"},
                    {"title": "Right Ho, Jeeves"},
                ],
            },
        }))


    def test_scalar_field_aliases(self):
        query = """
            {
                author(id: 1) {
                    authorName: name
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "authorName": "PG Wodehouse",
            },
        }))


    def test_can_alias_same_scalar_field_multiple_times(self):
        query = """
            {
                author(id: 1) {
                    authorName: name
                    name: name
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "authorName": "PG Wodehouse",
                "name": "PG Wodehouse",
            },
        }))


    def test_top_level_relationship_field_aliases(self):
        query = """
            {
                wodehouse: author(id: 1) {
                    name
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "wodehouse": {
                "name": "PG Wodehouse"
            }
        }))


    def test_can_alias_same_top_level_field_multiple_times_with_different_arguments(self):
        query = """
            {
                wodehouse: author(id: 1) {
                    name
                }
                heller: author(id: 2) {
                    name
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "wodehouse": {
                "name": "PG Wodehouse"
            },
            "heller": {
                "name": "Joseph Heller"
            }
        }))


    def test_nested_relationship_field_aliases(self):
        query = """
            {
                author(id: 1) {
                    b: books {
                        title
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "b": [
                    {"title": "Leave It to Psmith"},
                    {"title": "Right Ho, Jeeves"},
                ]
            }
        }))


    def test_field_alias_in_child_does_not_clash_with_join_fields(self):
        query = """
            {
                author(id: 1) {
                    books {
                        authorId: title
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "books": [
                    {"authorId": "Leave It to Psmith"},
                    {"authorId": "Right Ho, Jeeves"},
                ]
            }
        }))


    def test_field_alias_in_parent_does_not_clash_with_join_fields(self):
        query = """
            {
                author(id: 1) {
                    id: name
                    books {
                        title
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "author": {
                "id": "PG Wodehouse",
                "books": [
                    {"title": "Leave It to Psmith"},
                    {"title": "Right Ho, Jeeves"},
                ]
            }
        }))


    def test_variable_can_be_used_in_top_level_argument(self):
        query = """
            query getAuthor($authorId: Int) {
                author(id: $authorId) {
                    id: name
                    books {
                        title
                    }
                }
            }
        """

        result = self.execute(query, variables={"authorId": 1})

        assert_that(result, is_successful_result(data={
            "author": {
                "id": "PG Wodehouse",
                "books": [
                    {"title": "Leave It to Psmith"},
                    {"title": "Right Ho, Jeeves"},
                ]
            }
        }))

    def test_querying_list_of_entities_with_fragment_spread(self):
        query = """
            {
                book(id: 1) {
                    ...BookIdentifiers
                }
            }

            fragment BookIdentifiers on Book {
                id
                title
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "id": 1,
                "title": "Leave It to Psmith",
            }
        }))

    def test_querying_list_of_entities_with_nested_fragment_spread(self):
        query = """
            {
                book(id: 1) {
                    ...BookGubbins
                }
            }

            fragment BookGubbins on Book {
                ...BookIdentifiers
            }

            fragment BookIdentifiers on Book {
                id
                title
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "id": 1,
                "title": "Leave It to Psmith",
            }
        }))

    def test_querying_list_of_entities_with_inline_fragment(self):
        query = """
            {
                book(id: 1) {
                    ... on Book {
                        id
                        title
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "id": 1,
                "title": "Leave It to Psmith",
            }
        }))

    def test_scalar_fields_are_merged(self):
        query = """
            {
                book(id: 1) {
                    author {
                        name
                    }

                    author {
                        name
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "author": {
                    "name": "PG Wodehouse",
                }
            }
        }))

    def test_object_fields_are_merged(self):
        query = """
            {
                book(id: 1) {
                    author {
                        id
                    }

                    author {
                        name
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "author": {
                    "id": 1,
                    "name": "PG Wodehouse",
                }
            }
        }))

    def test_nested_object_fields_are_merged(self):
        query = """
            {
                book(id: 1) {
                    author {
                        books {
                            id
                        }
                    }

                    author {
                        books {
                            title
                        }
                    }
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "author": {
                    "books": [
                        {
                            "id": 1,
                            "title": "Leave It to Psmith"
                        },
                        {
                            "id": 2,
                            "title": "Right Ho, Jeeves"
                        }
                    ]
                }
            }
        }))

    def test_include_directive_on_field_conditionally_includes_field(self):
        query = """
            {
                book(id: 1) {
                    id @include(if: false)
                    title @include(if: true)
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "title": "Leave It to Psmith"
            }
        }))

    def test_skip_directive_on_field_conditionally_skips_field(self):
        query = """
            {
                book(id: 1) {
                    id @skip(if: true)
                    title @skip(if: false)
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "title": "Leave It to Psmith"
            }
        }))

    def test_both_include_and_skip_directives_must_be_satisified(self):
        query = """
            {
                book(id: 1) {
                    includeFalse_skipFalse: title @include(if: false) @skip(if: false)
                    includeFalse_skipTrue: title @include(if: false) @skip(if: true)
                    includeTrue_skipFalse: title @include(if: true) @skip(if: false)
                    includeTrue_skipTrue: title @include(if: true) @skip(if: true)
                }
            }
        """

        result = self.execute(query)

        assert_that(result, is_successful_result(data={
            "book": {
                "includeTrue_skipFalse": "Leave It to Psmith"
            }
        }))

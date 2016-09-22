from hamcrest import assert_that, equal_to


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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
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
        query = """
            {
                author(id: 1) {
                    name
                }
            }
        """
        
        result = self.execute(query)
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
            "author": {
                "books": [
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
        
        assert_that(result, equal_to({
            "author": {
                "authorName": "PG Wodehouse",
            },
        }))


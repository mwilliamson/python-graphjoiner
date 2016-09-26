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
        # TODO: add test for non-top-level arg
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
        

    def test_querying_scalar_list(self):
        query = """
            {
                author(id: 1) {
                    bookTitles
                }
            }
        """
        
        result = self.execute(query)
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
            "author": {
                "authorName": "PG Wodehouse",
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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
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
        
        assert_that(result, equal_to({
            "author": {
                "id": "PG Wodehouse",
                "books": [
                    {"title": "Leave It to Psmith"},
                    {"title": "Right Ho, Jeeves"},
                ]
            }
        }))

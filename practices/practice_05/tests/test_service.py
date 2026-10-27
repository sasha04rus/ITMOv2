import unittest

from app import service


class SubscriptionRegressionTests(unittest.TestCase):
    def setUp(self):
        service.subscribers.clear()

    def tearDown(self):
        service.subscribers.clear()

    def test_subscribe_trims_and_deduplicates_exact_names(self):
        self.assertEqual(service.subscribe(" Ann "), {"subscribed": True})
        service.subscribe("Ann")
        self.assertEqual(service.subscribers, {"Ann"})
        service.subscribe("ann")
        self.assertEqual(service.subscribers, {"Ann", "ann"})

    def test_unsubscribe_success_and_noop(self):
        service.subscribe("Alice")
        self.assertTrue(service.unsubscribe(" Alice "))
        self.assertFalse(service.unsubscribe("Alice"))

    def test_empty_names_raise(self):
        for operation in (service.subscribe, service.unsubscribe):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ValueError):
                    operation(" \t\n")

    def test_list_sorted_and_independent(self):
        for name in ("Bob", "Alice", "Анна"):
            service.subscribe(name)
        result = service.list_subscribers()
        self.assertEqual(result, ["Alice", "Bob", "Анна"])
        result.clear()
        self.assertEqual(len(service.subscribers), 3)


class SearchTests(unittest.TestCase):
    def setUp(self):
        service.subscribers.clear()
        for name in service.DEMO_NAMES:
            service.subscribe(name)

    def tearDown(self):
        service.subscribers.clear()

    def test_latin_and_cyrillic_substrings_ignore_case(self):
        self.assertEqual(service.search_subscribers(" ALI "), ["Alice"])
        self.assertEqual(service.search_subscribers("АН"), ["Анна"])
        self.assertEqual(service.search_subscribers("oB"), ["Bob"])

    def test_unicode_strip_matches_python_rules(self):
        self.assertEqual(service.search_subscribers("\u001cALI\u001c"), ["Alice"])
        self.assertEqual(service.normalize_query("\u2003Ан\u2003"), "Ан")

    def test_empty_and_whitespace_queries_return_all_sorted(self):
        expected = ["Alice", "Bob", "Анна", "Борис"]
        self.assertEqual(service.search_subscribers(), expected)
        self.assertEqual(service.search_subscribers("  \t\n"), expected)

    def test_no_match_and_empty_storage_are_successful(self):
        self.assertEqual(service.search_subscribers("not present"), [])
        service.subscribers.clear()
        self.assertEqual(service.search_subscribers(""), [])

    def test_search_result_is_independent_and_storage_unchanged(self):
        before = set(service.subscribers)
        result = service.search_subscribers("a")
        result.append("External")
        result.clear()
        self.assertEqual(service.subscribers, before)

    def test_100_code_points_accepted_and_101_rejected(self):
        for symbol in ("a", "\U0001f600"):
            with self.subTest(symbol=symbol):
                self.assertEqual(service.search_subscribers(symbol * 100), [])
                with self.assertRaises(service.QueryError) as caught:
                    service.search_subscribers(symbol * 101)
                self.assertEqual(caught.exception.code, "query_too_long")

    def test_length_checked_after_strip_before_casefold(self):
        query = "ß" * 100
        service.subscribe(query)
        self.assertEqual(service.search_subscribers("  " + query + "  "), [query])

    def test_casefold_without_transliteration_or_accent_normalization(self):
        for name in ("Straße", "Елена", "Ёлка", "é"):
            service.subscribe(name)
        self.assertEqual(service.search_subscribers("STRASSE"), ["Straße"])
        self.assertEqual(service.search_subscribers("ел"), ["Елена"])
        self.assertEqual(service.search_subscribers("e\u0301"), [])
        self.assertEqual(service.search_subscribers("anna"), [])

    def test_non_string_query_rejected(self):
        for query in (None, 42, []):
            with self.subTest(query=query):
                with self.assertRaises(service.QueryError) as caught:
                    service.search_subscribers(query)
                self.assertEqual(caught.exception.code, "invalid_query")


if __name__ == "__main__":
    unittest.main()

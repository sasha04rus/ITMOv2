import unittest

from practices.practice_04.service.subscriptions import service


class TestSubscriptions(unittest.TestCase):
    def setUp(self):
        service.subscribers.clear()

    def test_unsubscribe_success_and_noop(self):
        service.subscribe("Alice")
        self.assertTrue(service.unsubscribe(" Alice "))
        self.assertFalse(service.unsubscribe("Alice"))

    def test_unsubscribe_empty_raises(self):
        with self.assertRaises(ValueError):
            service.unsubscribe("   ")

    def test_list_sorted(self):
        service.subscribe("Bob")
        service.subscribe("Alice")
        self.assertEqual(service.list_subscribers(), ["Alice", "Bob"])


if __name__ == "__main__":
    unittest.main()

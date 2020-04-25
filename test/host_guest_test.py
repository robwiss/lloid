import unittest
from lloidbot.queue_manager import Action, Error, Host, Guest

class HostGuestTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_host_equal(self):
        h1 = Host(1)
        h2 = Host(1)

        assert h1 == h2

    def test_host_not_equal(self):
        h1 = Host(1)
        h2 = Host(2)

        assert h1 != h2

    def test_host_comparison_by_id(self):
        h1 = Host(1)

        assert h1 == 1
        assert h1 != 2

    def test_add_to_queue(self):
        h = Host(1)
        assert h.addToQueue(1) == (Action.ADDED_TO_QUEUE, Guest(1,h))
        assert h.addToQueue(2) == (Action.ADDED_TO_QUEUE, Guest(2,h))

        assert 1 in h.queue
        assert 2 in h.queue
        assert 3 not in h.queue

    def test_wont_add_if_already_queued(self):
        h = Host(1)
        assert h.addToQueue(1) == (Action.ADDED_TO_QUEUE, Guest(1,h))
        assert h.addToQueue(1) == (Error.ALREADY_QUEUED, Guest(1,h))


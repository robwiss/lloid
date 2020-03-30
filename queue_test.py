import unittest
import turnips
import sqlite3
from turnips import Status
from datetime import datetime
from unittest import mock 
import freezegun

alice = turnips.Turnip('global', 1, 'Alice', 'ALICE', 0, None, [None]*12)
bella = turnips.Turnip('nookmart', 2, 'Bella', 'BELLA', 5, None, [None]*12)
# March 24, 2020 - Tuesday
tuesday_morning = datetime(2020, 3, 24, 10, 20)
tuesday_evening = datetime(2020, 3, 24, 21, 20)
wednesday_early = datetime(2020, 3, 25, 4, 0)
saturday_evening = datetime(2020, 3, 28, 21, 30)
saturday_end = datetime(2020, 3, 28, 23, 59)
sunday_morning = datetime(2020, 3, 29, 10, 40)
sunday_evening = datetime(2020, 3, 29, 18, 40)

class TestQueue(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.market = turnips.StalkMarket(self.db)
 
        t = self.market.get_all()
        
        assert len(t) == 0

    def insert_sample_rows(self):
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset, 'global')
        self.market.declare(bella.id, bella.name, 100, bella.dodo, bella.gmtoffset, 'nookmart')
    
    def tearDown(self):
        self.db.execute("delete from turnips")
        self.db.close()

    # we need multiple queues per person
    @freezegun.freeze_time(tuesday_morning)
    def test_queue_created(self):
        assert len(self.market.queue.queues) == 0 
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)
        assert len(self.market.queue.queues) == 1
        self.market.declare(bella.id, bella.name, 150, bella.dodo, bella.gmtoffset)
        assert len(self.market.queue.queues) == 2 

    @freezegun.freeze_time(tuesday_morning)
    def test_wont_dupe_queues(self):
        assert len(self.market.queue.queues) == 0 
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)
        assert len(self.market.queue.queues) == 1
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)
        assert len(self.market.queue.queues) == 1

    @freezegun.freeze_time(tuesday_morning)
    def test_request_next_dequeues(self):
        self.insert_sample_rows()

        assert len(self.market.queue.requesters) == 0 
        self.market.request(100, alice.id)
        assert len(self.market.queue.requesters) == 1
        assert self.market.queue.queues[alice.id].qsize() == 1
        n = self.market.next(alice.id)
        assert n[0] == 100
        assert n[1].id == alice.id
        assert len(self.market.queue.requesters) == 0
        assert self.market.queue.queues[alice.id].qsize() == 0

    @freezegun.freeze_time(tuesday_morning)
    def test_request_next_returns_queue_size(self):
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)

        first = self.market.request(100, alice.id)
        second = self.market.request(101, alice.id)
        third = self.market.request(102, alice.id)
        fourth = self.market.request(103, alice.id)

        assert first == 1
        assert second == 2
        assert third == 3
        assert fourth == 4


    @freezegun.freeze_time(tuesday_morning)
    def test_close(self):
        self.insert_sample_rows()
        self.market.request(100, bella.id)
        self.market.request(101, bella.id)
        self.market.request(102, bella.id)

        n = self.market.next(bella.id)
        assert n[0] == 100

        remaining, status = self.market.close(bella.id)
        assert status == Status.SUCCESS
        assert len(remaining) == 2
        assert 101 in remaining
        assert 102 in remaining


    @freezegun.freeze_time(tuesday_morning)
    def test_cant_close_twice(self):
        self.insert_sample_rows()
        self.market.request(100, bella.id)
        self.market.request(101, bella.id)
        self.market.request(102, bella.id)

        self.market.next(bella.id)
        remaining, status = self.market.close(bella.id)
        assert status == Status.SUCCESS
        assert len(remaining) == 2

        remaining, status = self.market.close(bella.id)
        assert status == Status.ALREADY_CLOSED
        assert remaining is None

    @freezegun.freeze_time(tuesday_morning)
    def test_wont_accept_dupe_request(self):
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)

        assert len(self.market.queue.requesters) == 0 
        self.market.request(100, alice.id)
        assert len(self.market.queue.requesters) == 1
        self.market.request(100, alice.id)
        assert len(self.market.queue.requesters) == 1 

    @freezegun.freeze_time(tuesday_morning)
    def test_wont_accept_dupe_request_across_different_owners(self):
        self.insert_sample_rows()

        assert len(self.market.queue.requesters) == 0 
        self.market.request(100, alice.id)
        assert len(self.market.queue.requesters) == 1
        self.market.request(100, bella.id)
        assert len(self.market.queue.requesters) == 1 
        assert len(self.market.queue.queues) == 2
        assert self.market.queue.queues[alice.id].qsize() == 1
        assert self.market.queue.queues[bella.id].qsize() == 0

if __name__ == '__main__':
    unittest.main() 
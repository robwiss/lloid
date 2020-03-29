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
        self.queue = turnips.Queue(self.market)
 
        t = self.market.get_all()
        
        assert len(t) == 0

    def insert_sample_rows(self):
        self.db.execute("replace into turnips(chan, nick, dodo, utcoffset) values"
                        "( 'global', 'Alice', 'ALICE', 0 )")
        self.db.execute("replace into turnips(chan, nick, dodo, utcoffset) values"
                        "( 'nookmart', 'Bella', 'BELLA', 5 )")
        self.market.declare(alice.nick, 150, alice.dodo, alice.tz)
    
    def tearDown(self):
        self.db.execute("delete from turnips")
        self.db.close()

    def test_queue(self):
        pass

    def test_wont_queue_dupe(self):
        assert self.queue.add(100, 1)
        assert not self.queue.add(100, 1)

if __name__ == '__main__':
    unittest.main() 
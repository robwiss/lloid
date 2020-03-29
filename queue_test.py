import unittest
import turnips
import sqlite3
from turnips import Status
from datetime import datetime
from unittest import mock 
import freezegun

class TestQueue(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.market = turnips.StalkMarket(self.db)
 
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

    def test_queue_standard(self):
        self.queue.queue
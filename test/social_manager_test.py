import unittest
import sqlite3
from lloidbot import turnips
from lloidbot.social_manager import SocialManager
from lloidbot.queue_manager import QueueManager
from datetime import datetime
import freezegun

alice = turnips.Turnip('global', 1, 'Alice', 'ALICE', 0, None, [None]*14)
bella = turnips.Turnip('nookmart', 2, 'Bella', 'BELLA', 5, None, [None]*14)
cally = turnips.Turnip('nookmart', 3, 'Cally', 'CALLY', 6, None, [None]*14)
deena = turnips.Turnip('nookmart', 4, 'Deena', 'DEENA', 7, None, [None]*14)

# March 24, 2020 - Tuesday
tuesday_morning = datetime(2020, 3, 24, 10, 20)
tuesday_evening = datetime(2020, 3, 24, 21, 20)
wednesday_early = datetime(2020, 3, 25, 4, 0)
saturday_evening = datetime(2020, 3, 28, 21, 30)
saturday_end = datetime(2020, 3, 28, 23, 59)
sunday_morning = datetime(2020, 3, 29, 10, 40)
sunday_evening = datetime(2020, 3, 29, 18, 40)


class TestSocialManager(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        
        self.market = turnips.StalkMarket(self.db)
        queueManager = QueueManager(self.market)
        self.manager = SocialManager(queueManager)
 
        t = self.market.get_all()
        
        assert len(t) == 0

    def insert_sample_rows(self):
        self.db.execute("replace into turnips(chan, id, nick, dodo, utcoffset) values"
                        "( 'global', 1, 'Alice', 'ALICE', 0 )")
        self.db.execute("replace into turnips(chan, id, nick, dodo, utcoffset) values"
                        "( 'nookmart', 2, 'Bella', 'BELLA', 5 )")
    
    def tearDown(self):
        self.db.execute("delete from turnips")
        self.db.close()
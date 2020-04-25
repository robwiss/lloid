import unittest
import sqlite3
from lloidbot import turnips
from lloidbot.social_manager import SocialManager, Action
from lloidbot import queue_manager
from lloidbot.queue_manager import QueueManager
from datetime import datetime
import freezegun

standard_description = "test_description"
updated_description = "updated_description"

alice = turnips.Turnip('global', 1, 'Alice', 'ALICE', 0, standard_description, None, [None]*14)
bella = turnips.Turnip('nookmart', 2, 'Bella', 'BELLA', 5, standard_description, None, [None]*14)
cally = turnips.Turnip('nookmart', 3, 'Cally', 'CALLY', 6, None, None, [None]*14)
deena = turnips.Turnip('nookmart', 4, 'Deena', 'DEENA', 7, None, None, [None]*14)

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

    @freezegun.freeze_time(tuesday_morning)
    def test_post_listing(self):
        res = self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo, alice.gmtoffset)
        assert len(res) == 2

        expected = (Action.CONFIRM_LISTING_POSTED, alice.id)
        assert expected in res

        expected = (Action.POST_LISTING, alice.id, 150, standard_description, tuesday_morning)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_post_listing_missing_dodo(self):
        res = self.manager.post_listing(alice.id, alice.name, 150, standard_description)
        assert len(res) == 1

        expected = (Action.ACTION_REJECTED, queue_manager.Status.DODO_REQUIRED)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_post_listing_missing_tz(self):
        res = self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo)
        assert len(res) == 1

        expected = (Action.ACTION_REJECTED, queue_manager.Status.TIMEZONE_REQUIRED)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_update_listing(self):
        self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo, alice.gmtoffset)

        res = self.manager.post_listing(alice.id, alice.name, 250, standard_description, alice.dodo, alice.gmtoffset)
        assert len(res) == 2

        expected = (Action.CONFIRM_LISTING_UPDATED, alice.id)
        assert expected in res

        expected = (Action.UPDATE_LISTING, alice.id, 250, standard_description, tuesday_morning)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_update_listing_missing_dodo(self):
        self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo, alice.gmtoffset)

        res = self.manager.post_listing(alice.id, alice.name, 250, standard_description)
        assert len(res) == 2

        expected = (Action.CONFIRM_LISTING_UPDATED, alice.id)
        assert expected in res

        expected = (Action.UPDATE_LISTING, alice.id, 250, standard_description, tuesday_morning)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_update_listing_updates_description(self):
        self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo, alice.gmtoffset)

        res = self.manager.post_listing(alice.id, alice.name, 150, updated_description, alice.dodo, alice.gmtoffset)
        assert len(res) == 2

        expected = (Action.CONFIRM_LISTING_UPDATED, alice.id)
        assert expected in res

        expected = (Action.UPDATE_LISTING, alice.id, 150, updated_description, tuesday_morning)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_update_listing_without_desc_does_not_nuke_existing_desc(self):
        res = self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo, alice.gmtoffset, standard_description)

        res = self.manager.post_listing(alice.id, alice.name, 250, None, alice.dodo, alice.gmtoffset)
        assert len(res) == 2

        expected = (Action.CONFIRM_LISTING_UPDATED, alice.id)
        assert expected in res

        expected = (Action.UPDATE_LISTING, alice.id, 250, standard_description, tuesday_morning)
        assert expected in res

    @freezegun.freeze_time(tuesday_morning)
    def test_queue_for_listing(self):
        self.manager.post_listing(alice.id, alice.name, 150, standard_description, alice.dodo, alice.gmtoffset, standard_description)

        res = self.manager.reaction_added(1, alice.id)
        assert len(res) == 1
        r, guest, host, ahead = res[0]
        assert r == Action.CONFIRM_QUEUED
        assert guest == 1
        assert host == alice.id
        assert len(ahead) == 0

        res = self.manager.reaction_added(2, alice.id)
        assert len(res) == 1
        r, guest, host, ahead = res[0]
        assert r == Action.CONFIRM_QUEUED
        assert guest == 2
        assert host == alice.id
        assert len(ahead) == 1
        assert 1 in ahead

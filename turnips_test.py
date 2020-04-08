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

class TestTurnips(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.market = turnips.StalkMarket(self.db)
 
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

    def test_get_all(self):
        self.insert_sample_rows()

        t = self.market.get_all()
        assert len(t) == 2, t
        assert t[0].equals(alice), "%s did not equal %s" % (t[0], alice) 
        assert t[1].equals(bella), "%s did not equal %s" % (t[1], bella)

    def test_get_by_id(self):
        self.insert_sample_rows()

        t = self.market.get(alice.id)
        assert t.equals(alice)

        t = self.market.get(bella.id)
        assert t.equals(bella)

    @freezegun.freeze_time(tuesday_morning)
    def test_insert_new(self):
        result = self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)
        assert result == Status.SUCCESS, result

        t = self.market.get(alice.id)
        assert t.history[2] == 150
        assert t.current_price() == 150

    @freezegun.freeze_time(tuesday_morning)
    def test_insert_existing(self):
        self.insert_sample_rows()
        t = self.market.get(alice.id)
        assert t.history[2] is None
        self.market.declare(alice.id, alice.name, 150, alice.dodo, alice.gmtoffset)

        t = self.market.get(alice.id)
        assert t.history[2] == 150
        assert t.current_price() == 150

    # Test inserting something where the bot's local time is morning, but the user has an offset.
    @freezegun.freeze_time(tuesday_morning)
    def test_insert_morning_with_offset(self):
        result = self.market.declare(bella.id, bella.name, 150, bella.dodo, bella.gmtoffset)
        assert result == Status.SUCCESS, result

        t = self.market.get(bella.id)
        assert t.history[2] is None
        assert t.history[3] == 150
        assert t.current_price() == 150

    @freezegun.freeze_time(tuesday_evening)
    def test_insert_evening_with_offset(self):
        result = self.market.declare(bella.id, bella.name, 150, bella.dodo, bella.gmtoffset)
        assert result == Status.SUCCESS, result

    @freezegun.freeze_time(wednesday_early)
    def test_insert_early_morning_with_offset(self):
        result = self.market.declare(bella.id, bella.name, 150, bella.dodo, bella.gmtoffset)
        assert result == Status.SUCCESS, result

        t = self.market.get(bella.id)
        assert t.history[2] is None
        assert t.history[3] is None
        assert t.history[4] == 150
        assert t.current_price() == 150

    def test_insert_no_timezone(self):
        result = self.market.declare(alice.id, alice.name, 150, alice.dodo)
        assert result == Status.TIMEZONE_REQUIRED

    def test_insert_no_dodo(self):
        result = self.market.declare(alice.id, alice.name, 150)
        assert result == Status.TIMEZONE_REQUIRED

    @freezegun.freeze_time(tuesday_morning)
    def test_insert_with_implicit_tz_and_dodo(self):
        self.insert_sample_rows()
        result = self.market.declare(alice.id, alice.name, 150)
        assert result == Status.SUCCESS

    @freezegun.freeze_time(sunday_morning)
    def test_insert_on_sunday(self):
        self.insert_sample_rows()
        result = self.market.declare(alice.id, alice.name, 150)
        assert result == Status.ITS_SUNDAY

    @freezegun.freeze_time(saturday_evening)
    def test_insert_on_saturday_evening(self):
        self.insert_sample_rows()
        result = self.market.declare(alice.id, alice.name, 150)
        assert result == Status.SUCCESS

    @freezegun.freeze_time(saturday_end)
    def test_insert_on_saturday_1159(self):
        self.insert_sample_rows()
        result = self.market.declare(alice.id, alice.name, 150)
        assert result == Status.SUCCESS

if __name__ == '__main__':
    unittest.main() 
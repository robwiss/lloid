import sqlite3
from datetime import datetime, timedelta
import queue

intervals = {
    "1a": 0,
    "1b": 1,
    "2a": 2,
    "2b": 3,
    "3a": 4,
    "3b": 5,
    "4a": 6,
    "4b": 7,
    "5a": 8,
    "5b": 9,
    "6a": 10,
    "6b": 11,
}

def current_datetime(offset):
    return datetime.utcnow() + timedelta(hours=offset)

def compute_current_interval(offset):
    local = current_datetime(offset)
    if local.hour < 8 or local.hour >= 22:
        return None, None
    day_of_week = local.weekday() + 1
    interval = "a"
    #if day_of_week >= 7 or day_of_week <= 0:
    #	return None, None
    if local.hour >= 12:
        interval = "b"
    return str(day_of_week) + interval, local.weekday()*2

class Turnip:
    def __init__(self, chan, idx, name, dodo, gmtoffset, latest_time, history):
        self.chan = chan
        self.id = idx
        self.name = name
        self.dodo = dodo
        self.gmtoffset = gmtoffset
        self.latest_time = latest_time
        self.history = history

    def clone(self):
        return Turnip(self.chan, self.id, self.name, self.dodo, self.gmtoffset, self.latest_time, self.history)

    def equals(self, t):
        return self.chan == t.chan and self.id == t.id and self.name == t.name and \
               self.dodo == t.dodo and self.gmtoffset == t.gmtoffset and \
               self.history == t.history
    
    def current_time(self):
        return current_datetime(self.gmtoffset)

    def current_price(self):
        interval, _ = compute_current_interval(self.gmtoffset)
        return self.history[intervals[interval]]

    def __str__(self):
        return "%s - %s - %s - %s - %s" % (self.chan, self.name, self.dodo, self.gmtoffset, self.history)
    
    @staticmethod
    def from_row(row):
        return Turnip(row[0], row[1], row[2], row[3], row[4], row[5], list(row[6:]))

class StalkMarket:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db_init()
        self.queue = Queue(self)

    def db_init(self):
        self.db.execute("""create table if not exists turnips(chan, id, nick, dodo, utcoffset, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, 
                primary key(chan, id))""")

        self.wipe_old_prices()

        self.db.commit()

    def get(self, idx, chan=None):
        results = None
        if chan is not None:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b from turnips where chan=? and id=?", (chan,idx)).fetchall()
        else:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b from turnips where id=?", (idx,)).fetchall()

        if results is None:
            return []
        elif len(results) == 0:
            return None
        else:
            return Turnip.from_row(results[0])

    def request(self, requester, owner):
        self.queue.request(requester, owner)
        return self.queue.queues[owner].qsize()

    def next(self, owner):
        return self.queue.next(owner)

    def close(self, owner):
        return self.queue.close(owner)

    def declare(self, idx, name, price, dodo=None, tz=None, chan=None):
        turnip = self.get(idx, chan)
        if tz is None: 
            if turnip is None or turnip.gmtoffset is None:
                return Status.TIMEZONE_REQUIRED
            tz = turnip.gmtoffset

        interval, _ = compute_current_interval(tz)
        if interval is None:
            return Status.CLOSED
        elif interval == '7a' or interval == '7b':
            return Status.ITS_SUNDAY

        field = "val" + interval

        if dodo is None:
            if turnip is None or turnip.gmtoffset is None:
                return Status.DODO_REQUIRED
            dodo = turnip.dodo

        if turnip is None:
            self.db.execute("replace into turnips(chan, id, nick, dodo," + field + ", utcoffset, latest_time) values"
                    " (?,?,?,?,?,?,?)", (chan, idx, name, dodo, price, tz, current_datetime(tz)))
        else:
            self.db.execute("update turnips set " + field + "=?, utcoffset=?, latest_time=? where id=? ", 
                (price, tz, current_datetime(tz), idx))

        self.db.commit()

        self.queue.new_queue(idx)

        return Status.SUCCESS

    def exists(self, user, chan=None):
        r = self.get_all(chan)
        for u in r:
            if u[0] == user:
                return True
        return False
    
    def get_all(self, chan=None):
        results = None
        if chan is not None:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b from turnips where chan=?", (chan,)).fetchall()
        else:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b from turnips ").fetchall()

        if results is None:
            return []
        else:
            return [Turnip.from_row(r) for r in results]

    def wipe_old_prices(self):
        # day = 24 * 60 * 60 # seconds
        # week = 7 * day
        turnips = self.get_all()
        for t in turnips:
            latest = datetime.strptime(t.latest_time, "%Y-%m-%d %H:%M:%S.%f")
            if latest.weekday() > current_datetime(t.gmtoffset).weekday() or (current_datetime(t.gmtoffset) - latest).days > 6:
                print ("wiping")
                self.db.execute("update turnips set val1a=NULL, val1b=NULL, val2a=NULL, val2b=NULL, val3a=NULL, val3b=NULL, val4a=NULL, val4b=NULL, val5a=NULL, val5b=NULL, val6a=NULL, val6b=NULL, dodo=NULL where nick=?", (t.name,) )


class Status:
    SUCCESS = 0
    TIMEZONE_REQUIRED = 1
    PRICE_REQUIRED = 2
    DODO_REQUIRED = 3
    ITS_SUNDAY = 4
    CLOSED = 5
    ALREADY_CLOSED = 6

class Queue:
    def __init__(self, market):
        self.market = market
        self.queues = {}
        self.requesters = {}
    
    def new_queue(self, owner):
        self.queues[owner] = queue.Queue()

    def request(self, guest, owner):
        if guest in self.requesters:
            return False
        self.requesters[guest] = owner
            
        self.queues[owner].put((guest, owner))

        return True

    def next(self, owner):
        q = self.queues[owner].get(block=True)
        del self.requesters[q[0]]
        return (q[0], self.market.get(q[1]))

    def close(self, owner):
        if owner not in self.queues:
            return None, Status.ALREADY_CLOSED
        q = self.queues[owner]
        del self.queues[owner]

        leftovers = []
        while not q.empty():
            r = q.get()[0]
            leftovers += [r]
            del self.requesters[r]

        return leftovers, Status.SUCCESS
    
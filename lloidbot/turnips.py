import sqlite3
from datetime import datetime, timedelta
import queue
import logging
import enum

logger = logging.getLogger('lloid')

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
    "7a": 12,
    "7b": 13
}

def current_datetime(offset):
    return datetime.utcnow() + timedelta(hours=offset)

def compute_current_interval(offset):
    local = current_datetime(offset)

    day_of_week = local.weekday() + 1
    interval = "a"
    #if day_of_week >= 7 or day_of_week <= 0:
    #	return None, None
    if local.hour >= 12:
        interval = "b"
    return str(day_of_week) + interval, local.weekday()*2

class Turnip:
    def __init__(self, chan, idx, name, dodo, gmtoffset, description, latest_time, history):
        self.chan = chan
        self.id = idx
        self.name = name
        self.dodo = dodo
        self.gmtoffset = gmtoffset
        self.description = description
        self.latest_time = latest_time
        self.history = history

    def clone(self):
        return Turnip(self.chan, self.id, self.name, self.dodo, self.gmtoffset, self.description, self.latest_time, self.history)

    def equals(self, t):
        return self.chan == t.chan and self.id == t.id and self.name == t.name and \
               self.dodo == t.dodo and self.gmtoffset == t.gmtoffset and \
               self.description == t.description and self.history == t.history
    
    def current_time(self):
        return current_datetime(self.gmtoffset)

    def current_price(self):
        interval, _ = compute_current_interval(self.gmtoffset)
        return self.history[intervals[interval]]

    def __str__(self):
        return "%s - %s - %s - %s - %s - %s" % (self.chan, self.name, self.dodo, self.gmtoffset, self.description, self.history)
    
    @staticmethod
    def from_row(row):
        return Turnip(row[0], row[1], row[2], row[3], row[4], row[5], row[6], list(row[7:]))

class StalkMarket:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db_init()
        self.queue = Queue(self)

    def db_init(self):
        self.db.execute("""create table if not exists turnips(chan, id, nick, dodo, utcoffset, description, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, val7a, val7b,
                primary key(chan, id))""")

        self.wipe_old_prices()

        self.db.commit()

    def has_listing(self, author):
        return author in self.queue.queues

    def get(self, idx, chan=None):
        results = None
        if chan is not None:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, description, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, val7a, val7b from turnips where chan=? and id=?", (chan,idx)).fetchall()
        else:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, description, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, val7a, val7b from turnips where id=?", (idx,)).fetchall()

        if results is None:
            return []
        elif len(results) == 0:
            return None
        else:
            return Turnip.from_row(results[0])

    def request(self, requester, owner):
        r = self.queue.request(requester, owner)
        if not r:
            return False, None
        return True, len(self.queue.queues[owner])

    def forfeit(self, requester):
        return self.queue.forfeit(requester)

    def next(self, owner):
        return self.queue.next(owner)

    def close(self, owner):
        return self.queue.close(owner)

    def declare(self, idx, name, price, dodo=None, tz=None, description=None, chan=None):
        print(idx, name, price, dodo, tz, description, chan)
        turnip = self.get(idx, chan)
        if dodo is None:
            if turnip is None or turnip.gmtoffset is None:
                return Status.DODO_REQUIRED
            dodo = turnip.dodo
        if tz is None: 
            if turnip is None or turnip.gmtoffset is None:
                return Status.TIMEZONE_REQUIRED
            tz = turnip.gmtoffset

        interval, _ = compute_current_interval(tz)
        #if interval == '7a' or interval == '7b':
        #    return Status.ITS_SUNDAY

        field = "val" + interval

        if turnip is None:
            self.db.execute("replace into turnips(chan, id, nick, dodo," + field + ", utcoffset, description, latest_time) values"
                    " (?,?,?,?,?,?,?,?)", (chan, idx, name, dodo, price, tz, description, current_datetime(tz)))
        else:
            if description is None or description.strip() == "":
                description = turnip.description
            self.db.execute("update turnips set " + field + "=?, dodo=?, utcoffset=?, description=?, latest_time=? where id=? ", 
                (price, dodo, tz, description, current_datetime(tz), idx))

        self.db.commit()

        return self.queue.new_queue(idx)

    def exists(self, user, chan=None):
        r = self.get_all(chan)
        for u in r:
            if u[0] == user:
                return True
        return False
    
    def get_all(self, chan=None):
        results = None
        if chan is not None:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, description, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, val7a, val7b from turnips where chan=?", (chan,)).fetchall()
        else:
            results = self.db.execute("select chan, id, nick, dodo, utcoffset, description, latest_time, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, val7a, val7b from turnips ").fetchall()

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
                self.db.execute("update turnips set val1a=NULL, val1b=NULL, val2a=NULL, val2b=NULL, val3a=NULL, val3b=NULL, val4a=NULL, val4b=NULL, val5a=NULL, val5b=NULL, val6a=NULL, val6b=NULL, val7a=NULL, val7b=NULL, dodo=NULL where id=?", (t.id,) )
        self.db.commit()

class Status(enum.Enum):
    SUCCESS = 0
    TIMEZONE_REQUIRED = 1
    PRICE_REQUIRED = 2
    DODO_REQUIRED = 3
    ITS_SUNDAY = 4
    CLOSED = 5
    ALREADY_CLOSED = 6
    ALREADY_OPEN = 7
    QUEUE_EMPTY = 8

class Queue:
    def __init__(self, market):
        self.market = market
        self.queues = {}
        self.requesters = {} # person requesting access -> owner they're requesting for
    
    def new_queue(self, owner):
        if owner in self.queues:
            return Status.ALREADY_OPEN

        self.queues[owner] = []

        return Status.SUCCESS

    def request(self, guest, owner):
        if guest in self.requesters:
            return False
        self.requesters[guest] = owner
        
        if owner not in self.queues:
            return False
        self.queues[owner] += [(guest, owner)]

        return True

    def forfeit(self, guest):
        if guest not in self.requesters:
            return False
        owner = self.requesters[guest]

        while owner in self.queues and (guest, owner) in self.queues[owner]:
            self.queues[owner].remove( (guest, owner) )

        while guest in self.requesters:
            del self.requesters[guest]

        return True

    def next(self, owner):
        t = self.market.get(owner)
        name = "???"
        if t is not None and t != []:
            name = t.name
        if owner not in self.queues:
            logger.info(f"owner {name} was not among queues. they must be already closed")
            return None, Status.ALREADY_CLOSED
        elif len(self.queues[owner]) == 0:
            # print(f"{name}'s queue has nobody in it")
            return None, Status.QUEUE_EMPTY
        
        logger.info(f"{name}'s queue has content")
        q = self.queues[owner].pop(0)

        if q is None:
            logger.info(f"{name}'s queue had [None] in it, so start the closing procedure")
            return None, Status.ALREADY_CLOSED
        guest, _ = q

        if guest in self.requesters:
            del self.requesters[guest]

        logger.info(f"returning {name}'s next guest'")
        return (guest, self.market.get(owner)), Status.SUCCESS

    def close(self, owner):
        if owner not in self.queues:
            return None, Status.ALREADY_CLOSED
        q = self.queues[owner]
        remaining = [qq[0] for qq in q]

        while len(q) > 0:
            g, _ = q.pop(0)
            while g in self.requesters:
                del self.requesters[g]

        self.queues[owner] += [None]
        del self.queues[owner]

        return remaining, Status.SUCCESS
    
from lloidbot.turnips import Status
import logging
import enum

logger = logging.getLogger('lloid')

# This class manages the logic of a complex queue that has more features than a standard 
# FIFO queue. The additional features generally correspond to the expected usage by the discord
# bot, but should be more generic than that so as not to be tied to discord.
# 
# Each method will return a list of tuples representing actions taken by the
# manager in the order they were taken. An example result might be:
# visitor_done -> (Action.CODE_DISPENSED, alice, bella, XDODO, [cally, deena])
# In other words, calling visitor_done results in the code 'XDODO' being dispensed to Alice, for 
# the island belonging to Bella, with Cally and Deena still waiting in line. Note that
# the caller is responsible for actually sending these messages to the users; the 
# manager only manages internal state.
class QueueManager:
    def __init__(self, market):
        self.market = market
        self.hosts = {} # owner to instance of Host
        self.guests = {} # guest to instance of Guest

    def declare(self, idx, name, price, dodo=None, tz=None, description=None, chan=None):
        preexisted = idx in self.hosts 
        status = self.market.declare(idx, name, price, dodo, tz, description, chan)
        if status in (Status.SUCCESS, Status.ALREADY_OPEN):
            act = Action.LISTING_ACCEPTED
            if preexisted:
                act = Action.LISTING_UPDATED
            else:
                self.hosts[idx] = Host(idx)
            return [(act, self.market.get(idx))]
        elif status in (Status.TIMEZONE_REQUIRED, Status.DODO_REQUIRED):
            return [(Action.NOTHING, status)]
        else:
            logger.warning(f"Declaration from user {name} resulted in a status of {status}, which should never even happen")
            return [(Action.UNKNOWN_ERROR, status)]

    # Queue manager should not know about timeouts--that's something for the social manager
    # to decide. So a timeout would most likely be handled the same way within the queue
    # manager.
    def visitor_done(self, guest):
        pass

    def visitor_request_queue(self, guest, owner):
        if guest in self.guests and self.guests[guest].status == Guest.WAITING:
            return [(Action.NOTHING, Error.ALREADY_QUEUED)]
        if owner not in self.hosts:
            return [(Action.NOTHING, Error.NO_SUCH_QUEUE)]

        guests_ahead = self.hosts[owner].queue[:]
        status, guest = self.hosts[owner].addToQueue(guest)
        if status == Action.ADDED_TO_QUEUE:
            self.guests[guest.id] = Guest(guest, owner)
            return [(Action.ADDED_TO_QUEUE, guests_ahead)]
        else:
            return [(Action.NOTHING, status)]

    def visitor_request_dequeue(self, guest, owner):
        pass

    def host_pause(self):
        pass

    def host_next(self, owner):
        if owner not in self.hosts:
            return [(Action.NOTHING, Error.NO_SUCH_QUEUE)]
        guest, e = self.hosts[owner].pop()
        if e == Error.QUEUE_EMPTY:
            return [(Action.NOTHING, Error.QUEUE_EMPTY)]
        return [(Action.POPPED_FROM_QUEUE, guest, owner)]
    
class Map1to1:
    def __init__(self):
        self.l2r = {}
        self.r2l = {}

    def __contains__(self, x):
        return x in self.l2r 

    def get_left(self, r):
        return self.r2l[r]
    
    def get_right(self, l):
        return self.l2r[l]

    def associate(self, l, r):
        self.l2r[l] = r
        self.r2l[r] = l
        return True

    def del_left(self, l):
        if l not in self.l2r:
            return False
        r = self.l2r[l] 
        del self.l2r[l]
        del self.r2l[r]
        return True

    def del_right(self, r):
        if r not in self.r2l:
            return False
        l = self.r2l[r] 
        del self.l2r[l]
        del self.r2l[r]
        return True

class Action(enum.Enum): # A list of actions that were taken by the queue manager upon receiving an event
    # Each one is accompanied by supplementary information which the caller will receive;
    # this will facilitate the construction of user-friendly messages on the caller's side.
    UNKNOWN_ERROR = -1
    NOTHING = 0 # reason
    INFO = 1 # supplementary parameters depend on information requested
    ADDED_TO_QUEUE = 2 # guest id, owner id, [guests ahead]
    REMOVED_FROM_QUEUE = 3 # guest id, owner id
    CODE_DISPENSED = 4 # guest id, owner id, dodo code, [remaining guests]
    LISTING_ACCEPTED = 5 # turnip (an instance of Turnip) 
    LISTING_UPDATED = 6 # turnip, price, [queued guests]
    LISTING_CLOSED = 7 # owner, [queued guests]
    DISPENSING_BLOCKED = 8 # owner, [queued guests]
    DISPENSING_REACTIVATED = 9 # owner, [queued guests]
    POPPED_FROM_QUEUE = 10 # guest id, owner id -- this differs from REMOVED as the latter implies that it's an abnormal situation (eg: visitor leaving line or getting kicked)

class Error(enum.Enum):
    UNKNOWN = 0
    ALREADY_QUEUED = 1
    QUEUE_EMPTY = 2
    NO_SUCH_QUEUE = 3

class Host:
    def __init__(self, owner_id):
        self.id = owner_id
        self.capacity = 1
        self.queue = [] # Queue of guest objects
        self.outgoing_queue = [] # Best guess at who is currently on the island 

    def __eq__(self, h):
        if isinstance(h, Host):
            return self.id == h.id
        else:
            return self.id == h

    def findQueuedGuest(self, guest_id):
        if guest_id not in self.queue:
            return None
        else:
            index = self.queue.index(guest_id)
            return self.queue[index]

    def addToQueue(self, guest_id):
        if guest_id in self.queue:
            return Error.ALREADY_QUEUED, self.findQueuedGuest(guest_id)
        guest = Guest(guest_id, self)
        self.queue += [guest]
        return Action.ADDED_TO_QUEUE, guest

    def pop(self):
        if len(self.queue) <= 0:
            return None, Error.QUEUE_EMPTY
        v = self.queue.pop(0)
        self.outgoing_queue += [v]
        v.status = Guest.VISITING
        return v, None

class Guest:
    WAITING = "Waiting"
    VISITING = "Visiting"
    DONE = "Done"

    def __init__(self, guest_id, host):
        self.id = guest_id
        self.host = host
        self.status = Guest.WAITING

    def __eq__(self, g):
        if isinstance(g, Guest):
            return self.id == g.id
        else:
            return self.id == g
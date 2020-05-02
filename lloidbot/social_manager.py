from lloidbot.turnips import Status
from lloidbot import queue_manager
import logging
import enum
from functools import wraps
import asyncio

queue = []
queue_interval_minutes = 10
queue_interval = 60 * queue_interval_minutes
poll_sleep_interval = 5

logger = logging.getLogger('lloid')

# This class should manage the queuing on the abstract idea of a social platform 
# (discord, IRC, etc). Currently, we assume a Discord-like featureset, but we
# should make sure to handle cases where the platform doesn't support things--eg:
# IRC won't let you delete messages, or react to them.
# This should map actions taken on a platform (eg: reaction) to the command the 
# action is intended to represent (eg: queue up).
# We'll figure this next part out later, but this class may not actually belong 
# here as in the ideal case, the bot shouldn't have to wait for the caller to provide
# it with a message id--which it needs to perform its duty.
#
# It should receive actions from the queue manager and translate them into message actions
# that the caller can perform. 
# eg: call_next -> host_next -> (CODE_DISPENSED) -> 
#     return [SEND_CODE (to guest), SEND_WARNING (to next guest), SEND_NOTIFICATION (to host)]
class SocialManager:
    def __init__(self, queueManager):
        self.queueManager = queueManager

    def post_listing(self, user_id, name, price, description=None, dodo=None, tz=None, chan=None):
        out = []
        res = self.queueManager.declare(user_id, name, price, dodo, tz, description)
        for r in res:
            status, *params = r
            if status == queue_manager.Action.LISTING_ACCEPTED:
                turnip = params[0]
                out += [(Action.CONFIRM_LISTING_POSTED, user_id)]
                out += [(Action.POST_LISTING, user_id, price, description, turnip.current_time())]
            elif status == queue_manager.Action.LISTING_UPDATED:
                turnip = params[0]
                out += [(Action.CONFIRM_LISTING_UPDATED, user_id)]
                out += [(Action.UPDATE_LISTING, turnip.id, turnip.current_price(), turnip.description, turnip.current_time())]
            elif status == queue_manager.Action.NOTHING:
                out += [(Action.ACTION_REJECTED, params[0])]
            else:
                logger.warning(f"""Posting the following listing resulted in a status of {status.name}. """
                                f"""Arguments given to the listing were: {user_id} | {name} | {description} | {price} | {dodo} | {tz} | {chan} """) 

        return out

    def register_message(self, user_id, message_id):
        pass

    def reaction_added(self, user_id, host_id):
        out = []
        res = self.queueManager.visitor_request_queue(user_id, host_id)
        for action, p in res:
            if action == queue_manager.Action.ADDED_TO_QUEUE:
                out += [(Action.CONFIRM_QUEUED, user_id, host_id, p)]
        return out

# These actions are values that will be returned by social manager, and represent
# actions that the caller should take upon receiving the result. These actions
# should be achievable using features available on standard chat platforms, but 
# should not be specific to any chat platform.
# For instance, reactions are not available on IRC, so there should not be any
# UNREACT_GUEST action. Instead, we have UPDATE_QUEUE_INFO, which a Discord-specific
# caller may decide means removing the guest's reaction to the message, but which an 
# IRC-specific caller might implement as a message posted by the bot somewhere--or 
# even as a no-op, if it's deemed too annoying to get such updates on IRC.
class Action(enum.Enum):
    ACTION_REJECTED = 0 # reason
    CONFIRM_LISTING_POSTED = 1 # owner_id
    POST_LISTING = 2 # owner id, price, description, turnip.current_time()
    CONFIRM_LISTING_UPDATED = 3 # owner id
    UPDATE_LISTING = 4 # owner_id, price, description, turnip.current_time()
    CONFIRM_QUEUED = 5 # guest_id, owner_id, queueAhead

class TimedActions(enum.Enum):
    CREATE_TIMER = 1 # key, length_seconds, post-timer callback
    CANCEL_TIMER = 2 # key

class TimedSocialManager(SocialManager):
    def __init__(self, queueManager):
        SocialManager.__init__(self, queueManager)

        self.guest_timers = {} # guests -> timers

    def guest_loop(self, guest_id, owner_id):
        pass

    def guest_timed_out(self, guest_id):
        pass

    def post_listing(self, user_id, name, price, description=None, dodo=None, tz=None, chan=None):
        res = super().post_listing(user_id, name, price, description, dodo, tz, chan)

        return res

    def host_requested_pause(self, owner_id):
        pass

    def host_requested_next(self, owner_id):
        pass

    def reaction_added(self, user_id, host_id):
        res = super.reaction_added(user_id, host_id)

        return res


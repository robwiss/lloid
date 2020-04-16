from lloidbot.turnips import Status
from lloidbot.queue_manager import QueueManager
import logging
import enum

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

    def post_listing(self, user_id, name, price, dodo=None, tz=None, chan=None):
        
        pass

    def register_message(self, user_id, message_id):
        pass

    def reaction_added(self, user_id, message_id):
        pass

# These actions are values that will be returned by social manager, and represent
# actions that the caller should take upon receiving the result. These actions
# should be achievable using features available on standard chat platforms, but 
# should not be specific to any chat platform.
# For instance, reactions are not available on IRC, so there should not be any
# UNREACT_GUEST action. Instead, we have UPDATE_QUEUE_INFO, which on Discord
# may consist of unreacting to the message, but on IRC might correspond to a 
# message posted by the bot somewhere--or even to a no-op, if it's deemed too
# annoying to get such updates on IRC.
class Action(enum.Enum):
    CONFIRM_LISTING_POSTED = 1 # owner_id
    POST_LISTING = 2 # owner id, price, description, turnip.current_time()
    CONFIRM_LISTING_UPDATED = 3 # owner id
    UPDATE_LISTING = 4 # owner_id, price, description, turnip.current_time()
    CONFIRM_QUEUED = 5 # guest_id, owner_id
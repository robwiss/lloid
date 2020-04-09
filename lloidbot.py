import discord
from discord.utils import get
import sqlite3
import turnips
import asyncio
import sys
from dotenv import load_dotenv
import os
import re
import sentry_sdk

queue = []
queue_interval = 60*10
poll_sleep_interval = 5


class Command:
    Successful = 0
    Error = 1

    # Command types
    Close = 2
    Done = 3
    QueueInfo = 4
    Pause = 5
    Next = 6

    def __init__(self, command):
        print(command.strip().lower())
        if command.strip().lower() == "close":
            self.status = Command.Successful
            self.cmd = Command.Close
            return
        elif command.strip().lower() == "done":
            self.status = Command.Successful
            self.cmd = Command.Done
            return
        elif command.strip().lower() == "!queueinfo":
            self.status = Command.Successful
            self.cmd = Command.QueueInfo
            return
        elif command.strip().lower() == "pause":
            self.status = Command.Successful
            self.cmd = Command.Pause
            return
        elif command.strip().lower() == "next":
            self.status = Command.Successful
            self.cmd = Command.Next
            return

        self.price = None
        self.dodo = None
        self.tz = None
        self.status = Command.Successful
        self.cmd = 0
        self.description = None

        if command is None:
            self.status = Command.Error
            return
        commands = command.split(maxsplit=3)
        if len(commands) == 0:
            self.status = Command.Error
            return
        else:
            if commands[0].isdigit():
                self.price = int(commands[0])
            else:
                self.status = Command.Error
                return
            if len(commands) > 1:
                if not re.match(r'[A-HJ-NP-Y0-9]{5}', commands[1], re.IGNORECASE):
                    self.status = Command.Error
                    return
                self.dodo = commands[1]
            if len(commands) > 2:
                try:
                    self.tz = int(commands[2])
                except ValueError:
                    self.status = Command.Error
                    return
            if len(commands) > 3:
                self.description = commands[3]
        

class Lloid(discord.Client):
    Successful = 0
    AlreadyClosed = 1
    QueueEmpty = 2

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        if self.initialized is None or not self.initialized:
            print("Initializing.")
            self.initialized = True
            self.report_channel = self.get_channel(int(os.getenv("ANNOUNCE_ID")))
            self.chan = 'global'
            self.db = sqlite3.connect("test.db") 
            self.market = turnips.StalkMarket(self.db)
            self.associated_user = {} # message id -> id of the user the message is about
            self.associated_message = {} # reverse mapping of the above
            self.sleepers = {}
            self.recently_departed = {}
            self.requested_pauses = {} # owner -> int representing number of requested pauses remaining 
            self.is_paused = {} # owner -> boolean
            self.descriptions = {} # owner -> description
        print(f"Sample data to verify data integrity: {self.associated_user}")

    async def on_raw_reaction_add(self, payload):
        channel = await client.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = await client.fetch_user(payload.user_id)

        if user == client.user or message.author != client.user:
            return
        if payload.emoji.name == '🦝':
            print(f"{user.name} reacted with raccoon")
            await self.queue_user(payload.message_id, user)

    async def queue_user(self, message_id, user):
        if message_id in self.associated_user:
            status, size = self.market.request(user.id, self.associated_user[message_id])
            if status:
                owner_name = self.get_user(self.associated_user[message_id]).name
                print(f"queued {user.name} up for {owner_name}")

                if size == 0:
                    size = 1
                interval_s = queue_interval * (size - 1) // 60
                interval_e = queue_interval * size // 60
                await user.send(f"Queued you up for a dodo code for {owner_name}. Estimated time: {interval_s}-{interval_e} minutes, give or take (it waits 10 minutes for each person before letting someone in, but the people ahead of you may finish early and let you in earlier). "
                "If you want to queue up elsewhere, or if you have to go, just unreact and it'll free you up.\n\n"
                "In the meantime, please be aware of common courtesy--once you have the code, it's possible for you to come back in any time you want. "
                "However, please don't just do so willy-nilly, and instead, **requeue and use the bot as a flow control mechanism, even if you already know the code**. "
                "Also, a lot of people might be ahead of you, so please just **go in, do the one thing you're there for, and leave**. "
                "If you're there to sell turnips, don't look for Saharah or shop at Nook's! And please, **DO NOT USE the minus (-) button to exit!** "
                "There are reports that exiting via minus button can result in people getting booted without their loot getting saved. Use the airport!")
            else:
                await user.send("It sounds like either the market is now closed, or you're in line elsewhere at the moment.")
        else:
            k = self.associated_user.keys
            print(f"{reaction.message.id} was not found in {k}")

    async def on_raw_reaction_remove(self, payload):
        if payload.emoji.name == '🦝' and payload.message_id in self.associated_user and payload.user_id in self.market.queue.requesters:
            user = await client.fetch_user(payload.user_id)
            print(f"{user.name} unreacted with raccoon")
            owner_name = self.get_user(self.associated_user[payload.message_id]).name
            waiting_for = self.market.queue.requesters[payload.user_id]
            if waiting_for == self.associated_user[payload.message_id] and self.market.forfeit(payload.user_id):
                await user.send("Removed you from the queue for %s." % owner_name)

    async def on_disconnect(self):
        print("Lloid got disconnected.")

    async def let_next_person_in(self, owner):
        task = None
        task, status = self.market.next(owner)
        if status == turnips.Status.QUEUE_EMPTY:
            return Lloid.QueueEmpty
        elif status == turnips.Status.ALREADY_CLOSED: # Then the owner closed
            print(f"Closed queue for {owner}")
            return Lloid.AlreadyClosed

        print(f"Letting {self.get_user(task[0]).name} in to {task[1].name}")
        await self.get_user(task[0]).send(f"Hope you enjoy your trip to **{task[1].name}**'s island! "
        "Be polite, observe social distancing, leave a tip if you can, and **please be responsible and message me \"__done__\" when you've left.**. "
        f"The Dodo code is **{task[1].dodo}**.")
        q = self.market.queue.queues[owner]
        print(f"Remainder in queue = {len(q)}")
        if len(q) > 0:
            print(f"looking up {q[0][0]}")
            next_in_line = self.get_user(q[0][0])
            if next_in_line is not None:
                print("Sending warning")
                await next_in_line.send((f"Your flight to **{task[1].name}**'s island is boarding soon! "
                "Please have your tickets ready, we'll be calling you in shortly!"))
        print(f"{self.get_user(task[0]).name} has departed for {task[1].name}'s island")
        self.recently_departed[task[0]] = owner
        try:
            await self.associated_message[owner].remove_reaction('🦝', self.get_user(task[0]))
        except Exception as ex:
            print("Couldn't remove reaction; error: %s" % ex)

        print("should have been successful")
        return Lloid.Successful

    async def reset_sleep(self, owner):
        print("resetting sleep")
        if owner in self.sleepers:
            print("cancelling current sleep")
            self.sleepers[owner].cancel()
        self.sleepers[owner] = self.loop.create_task(asyncio.sleep(queue_interval))

        try:
            await self.sleepers[owner]
        except:
            print("sleep was cancelled")
            pass

        if owner in self.sleepers:  # not yet sure why sometimes owner is not in self.sleepers
            del self.sleepers[owner]

    async def queue_manager(self, owner):
        self.is_paused[owner] = False
        while True:
            # pauses should go here because the queue might be empty when the owner calls pause
            # if it's empty when that happens, then it never reaches the reset_sleep call at the end.
            # we can't move that reset_sleep call up here because that means it would sleep before handing
            # out the first code.
            while owner in self.requested_pauses and self.requested_pauses[owner] > 0:
                print(f"Sleeping upon request, {self.requested_pauses[owner]}")
                self.is_paused[owner] = True
                self.requested_pauses[owner] -= 1
                await self.reset_sleep(owner)
            self.is_paused[owner] = False

            status = await self.let_next_person_in(owner)
            if status == Lloid.QueueEmpty:
                # print("queue seems empty, sleeping then polling again")
                await asyncio.sleep(poll_sleep_interval)
                continue
            elif status == Lloid.AlreadyClosed:
                print("Lloid apparently closed")
                break

            print("Should reset sleep now")
            await self.reset_sleep(owner)
        print("Exited the loop. This can only happen if the queue was closed.")

    async def handle_queueinfo(self, message):
        guest = message.author.id
        if guest not in self.market.queue.requesters:
            await message.channel.send("You don't seem to be queued up for anything. "
            "It could also be that the code got sent to you just now. Please check your DMs.")
            return
        owner = self.market.queue.requesters[guest]
        q = self.market.queue.queues[owner]
        qsize = len(q)
        index = -1
        try:
            index = [qq[0] for qq in q].index(guest)
        except:
            pass

        if index < 0:
            await message.channel.send("You don't seem to be queued up for anything.")
        else:
            await message.channel.send(f"Your position in the queue is {index} in a queue of {qsize} people. Position 0 means you're next.")

    async def on_message(self, message):
        # Lloid should not respond to self
        if message.author == client.user:
            return

        if isinstance(message.channel, discord.DMChannel):
            print(f">>>> (PM) {message.author.name}: {message.content}")
            command = Command(message.content)

            if command.status == Command.Successful:
                if command.cmd == Command.QueueInfo:
                    await self.handle_queueinfo(message)
                    return
                elif command.cmd == Command.Pause and message.author.id in self.market.queue.queues:
                    if self.market.has_listing(message.author.id):
                        await message.channel.send(f"Okay, extending waiting period by another {queue_interval // 60} minutes. "
                        "You can cancel this by letting the next person in with **next**.")
                        self.is_paused[message.author.id] = True
                        if message.author.id not in self.requested_pauses:
                            self.requested_pauses[message.author.id] = 0
                        self.requested_pauses[message.author.id] += 1
                        return
                    else:
                        await message.channel.send("If you want to move to the back of the line, unqueue and requeue. "
                        "If you think the island is congested, please tell the host to pause with the same command you just sent.")
                elif command.cmd == Command.Next:
                    if self.market.has_listing(message.author.id):
                        await message.channel.send("Okay, letting the next person in.")
                        self.requested_pauses[message.author.id] = 0
                        await self.let_next_person_in(message.author.id)
                        await self.reset_sleep(message.author.id)
                        return
                    else:
                        await message.channel.send("Nice try.")
                elif command.cmd == Command.Close:
                    if message.author.id not in self.market.queue.queues:
                        await message.channel.send("You don't seem to have a market open.")
                        return
                    await message.channel.send("Thanks for responsibly closing your doors! I'll give my condolences to the people still in line, if any.")
                    denied, status = self.market.close(message.author.id)
                    if status == turnips.Status.SUCCESS:
                        for d in denied:
                            await self.get_user(d).send("Apologies, but it looks like the person you were waiting for closed up.")
                        # await self.associated_message[message.author.id].edit(content=">>> Sorry! This island has been delisted!")
                        # await self.associated_message[message.author.id].unpin()
                        await self.associated_message[message.author.id].delete()
                        del self.associated_user[self.associated_message[message.author.id].id]
                        del self.associated_message[message.author.id]
                        if message.author.id in self.requested_pauses:
                            del self.requested_pauses[message.author.id]
                elif command.cmd == Command.Done:
                    guest = message.author.id
                    owner = self.recently_departed.pop(guest, None)
                    if owner in self.is_paused and self.is_paused[owner]:
                        await message.channel.send("Thanks for the heads-up! "
                        "The queue is actually paused at the moment, so the host will be the one to let the next person in.")
                        return
                    if owner is not None and owner in self.sleepers:
                        self.sleepers[owner].cancel()
                        await message.channel.send("Thanks for the heads-up! Letting the next person in now.")
                else:
                    res = self.market.declare(message.author.id, message.author.name, command.price, command.dodo, command.tz)
                    if res == turnips.Status.ALREADY_OPEN:
                        await message.channel.send("Updated your info. Anyone still in line will get the updated codes.")
                    elif res == turnips.Status.SUCCESS:
                        if message.author.id in self.sleepers:
                            print("Owner has previous outstanding timers. Cancelling them now.")
                            self.sleepers[message.author.id].cancel()
                        self.requested_pauses[message.author.id] = 0
                        await message.channel.send("Okay! Please be responsible and message \"**close**\" to indicate when you've closed. "
                        "You can update the dodo code with the normal syntax. "
                        f"Messaging me \"**pause**\" will extend the cooldown timer by {queue_interval // 60} minutes each time. "
                        "You can also let the next person in and reset the timer to normal by messaging me \"**next**\".")
                        
                        turnip = self.market.get(message.author.id)
                        desc = ""
                        if command.description is not None:
                            self.descriptions[message.author.id] = command.description
                            desc = f"\n**{turnip.name}** adds: {command.description}"
                        
                        msg = await self.report_channel.send(f">>> **{turnip.name}** has turnips selling for **{turnip.current_price()}**. "
                        f'Local time: **{turnip.current_time().strftime("%a, %I:%M %p")}**. '
                        f"React to this message with 🦝 to be queued up for a code. {desc}")
                        await msg.add_reaction('🦝')
                        self.associated_user[msg.id] = message.author.id
                        self.associated_message[message.author.id] = msg

                        self.loop.create_task(self.queue_manager(message.author.id))
                    elif res == turnips.Status.TIMEZONE_REQUIRED:
                        await message.channel.send(("This seems to be your first time setting turnips, "
                        "so you'll need to provide both a dodo code and a GMT offset (just a positive or negative integer). The dodo code can be a placeholder if you want."))
                    elif res == turnips.Status.PRICE_REQUIRED:
                        await message.channel.send("You'll need to tell us how much the turnips are at least.")
                    elif res == turnips.Status.DODO_REQUIRED:
                        await message.channel.send(("This seems to be your first time setting turnips, "
                        "so you'll need to provide both a dodo code and a GMT offset (just a positive or negative integer). The dodo code can be a placeholder if you want."))
                    elif res == turnips.Status.ITS_SUNDAY:
                        await message.channel.send("I'm afraid the turnip prices aren't set on Sundays, so will you please come again tomorrow instead?")
                    elif res == turnips.Status.CLOSED:
                        print("This message should no longer be reachable (status = closed)")
            else:
                await message.channel.send("Usage: \"[price] [optional dodo code] [optional gmt offset--an integer such as -5 or 8] [optional description, markdown supported]\"\n\n "
                "The quotes (\")and square brackets ([]) are not part of the input!\n\n"
                "Example usage: *123 C0FEE 8*\n\n "
                "All arguments are required if you wish to include a description, but feel free to put a placeholder price like 1 if you were opening for reasons other than turnips.")
        else:
            await self.public_message_handler(message)

    async def public_message_handler(self, message):
        if message.content == "!queueinfo":
            await self.handle_queueinfo(message)


if __name__ == "__main__":
    print ("Starting Lloid...")
    load_dotenv()
    token = os.getenv("TOKEN")
    interval = os.getenv("QUEUE_INTERVAL")
    sentry_dsn = os.getenv("SENTRY_DSN")

    if not token:
        raise Exception('TOKEN env variable is not defined')

    if not os.getenv("ANNOUNCE_ID"):
        raise Exception('ANNOUNCE_ID env variable is not defined')

    if sentry_dsn:
        sentry_sdk.init(sentry_dsn)
        print("Connected to Sentry")

    if interval:
        queue_interval = int(interval)
        print(f"Set interval to {interval}")

    client = Lloid()
    client.initialized = False
    client.run(token)

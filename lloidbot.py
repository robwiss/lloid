import discord
from discord.utils import get
import sqlite3
import turnips
import asyncio
import sys
from dotenv import load_dotenv
import os
import re

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

    async def on_reaction_add(self, reaction, user):
        if user == client.user or reaction.message.author != client.user:
            return
        if reaction.emoji == '🦝':
            print ("%s reacted with raccoon" % user.name)
            await self.queue_user(reaction, user)

    async def queue_user(self, reaction, user):
        if reaction.message.id in self.associated_user:
            status, size = self.market.request(user.id, self.associated_user[reaction.message.id])
            if status:
                print("queued %s up for %s" % (user.name, self.get_user(self.associated_user[reaction.message.id]).name))
                if size == 0:
                    size = 1
                interval_s = queue_interval * (size - 1) // 60
                interval_e = queue_interval * size // 60
                await user.send("Queued you up for a dodo code. Estimated time: %d-%d minutes, give or take. If you want to queue up elsewhere, or if you have to go, just unreact and it'll free you up. \n\nIn the meantime, please be aware of common courtesy--once you have the code, it's possible for you to come back in any time you want. However, please don't just do so willy-nilly, and instead, **requeue and use the bot as a flow control mechanism, even if you already know the code**. Also, a lot of people might be ahead of you, so please just **go in, do the one thing you're there for, and leave**. If you're there to sell turnips, don't look for Saharah or shop at Nook's! And please, **DO NOT USE the minus (-) button to exit!** There are reports that exiting via minus button can result in people getting booted without their loot getting saved. Use the airport!" % (interval_s, interval_e))
            else:
                await user.send("It sounds like either the market is now closed, or you're in line elsewhere at the moment.")

    async def on_reaction_remove(self, reaction, user):
        if reaction.emoji == '🦝' and reaction.message.id in self.associated_user and user.id in self.market.queue.requesters:
            print ("%s unreacted with raccoon" % user.name)
            waiting_for = self.market.queue.requesters[user.id]
            if waiting_for == self.associated_user[reaction.message.id] and self.market.forfeit(user.id):
                await user.send("Removed you from the queue.")

    async def let_next_person_in(self, owner):
        task = None
        try:
            task = self.market.next(owner)
        except:
            return Lloid.QueueEmpty
        if task is None: # Then the owner closed
            print("Closed queue for %s" % owner)
            return Lloid.AlreadyClosed

        print("Letting %s in to %s" % (self.get_user(task[0]).name, task[1].name))
        await self.get_user(task[0]).send("Hope you enjoy your trip to **%s**'s island! Be polite, observe social distancing, leave a tip if you can, and **please be responsible and message me \"__done__\" when you've left.**. The Dodo code is **%s**." % (task[1].name, task[1].dodo))
        q = list(self.market.queue.queues[owner].queue)
        print("remainder in queue = %d" % len(q))
        if len(q) > 0:
            print("looking up %s" % q[0][0])
            next_in_line = self.get_user(q[0][0])
            if next_in_line is not None:
                print("sending warning")
                await next_in_line.send("Your flight to **%s**'s island is boarding soon! Please have your tickets ready, we'll be calling you in shortly!" % task[1].name)
        print("%s has departed for %s's island" % (self.get_user(task[0]).name, task[1].name))
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

        if owner in self.sleepers: # not yet sure why sometimes owner is not in self.sleepers
            del self.sleepers[owner]
        
    async def queue_manager(self, owner):
        self.is_paused[owner] = False
        while True:
            # pauses should go here because the queue might be empty when the owner calls pause
            # if it's empty when that happens, then it never reaches the reset_sleep call at the end.
            # we can't move that reset_sleep call up here because that means it would sleep before handing
            # out the first code.
            while owner in self.requested_pauses and self.requested_pauses[owner] > 0:
                print("sleeping upon request, %d" % self.requested_pauses[owner])
                self.is_paused[owner] = True
                self.requested_pauses[owner] -= 1
                await self.reset_sleep(owner)
            self.is_paused[owner] = False

            status = await self.let_next_person_in(owner)
            if status == Lloid.QueueEmpty:
                await asyncio.sleep(poll_sleep_interval)
                continue
            elif status == Lloid.AlreadyClosed:
                print("lloid apparently closed")
                break

            print("should reset sleep now")
            await self.reset_sleep(owner)

    async def handle_queueinfo(self, message):
        guest = message.author.id
        if guest not in self.market.queue.requesters:
            await message.channel.send("You don't seem to be queued up for anything. It could also be that the code got sent to you just now. Please check your DMs.")
            return
        owner = self.market.queue.requesters[guest]
        q = self.market.queue.queues[owner]
        qsize = q.qsize()
        index = -1
        try:
            index = [qq[0] for qq in list(q.queue)].index(guest)
        except:
            pass
        
        if index < 0:
            await message.channel.send("You don't seem to be queued up for anything.")
        else:
            await message.channel.send("Your position in the queue is %d in a queue of %d people. Position 0 means you're next." % (index, qsize))

    async def on_message(self, message):
        # Lloid should not respond to self
        if message.author == client.user:
            return

        if isinstance(message.channel, discord.DMChannel):
            print(">>>> (PM) %s: %s" % (message.author.name, message.content) )
            command = Command(message.content)

            if command.status == Command.Successful:
                if command.cmd == Command.QueueInfo:
                    await self.handle_queueinfo(message)
                    return
                elif command.cmd == Command.Pause and message.author.id in self.market.queue.queues:
                    await message.channel.send("Okay, extending waiting period by another %d minutes. You can cancel this by letting the next person in with **next**." % (queue_interval // 60))
                    self.is_paused[message.author.id] = True
                    if message.author.id not in self.requested_pauses:
                        self.requested_pauses[message.author.id] = 0
                    self.requested_pauses[message.author.id] += 1
                    return
                elif command.cmd == Command.Next:
                    await message.channel.send("Okay, letting the next person in.")
                    self.requested_pauses[message.author.id] = 0
                    await self.let_next_person_in(message.author.id)
                    await self.reset_sleep(message.author.id)
                    return
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
                        await message.channel.send("Thanks for the heads-up! The queue is actually paused at the moment, so the host will be the one to let the next person in.")
                        return
                    if owner is not None and owner in self.sleepers:
                        self.sleepers[owner].cancel()
                        await message.channel.send("Thanks for the heads-up! Letting the next person in now.")
                else:
                    res = self.market.declare(message.author.id, message.author.name, command.price, command.dodo, command.tz)
                    if res == turnips.Status.ALREADY_OPEN:
                        await message.channel.send("Updated your info. Anyone still in line will get the updated codes.")
                    elif res == turnips.Status.SUCCESS:
                        await message.channel.send("Okay! Please be responsible and message \"**close**\" to indicate when you've closed. You can update the dodo code with the normal syntax. Messaging me \"**pause**\" will extend the cooldown timer by %d minutes each time. You can also let the next person in and reset the timer to normal by messaging me \"**next**\"." % ( queue_interval // 60))
                        
                        turnip = self.market.get(message.author.id)
                        desc = ""
                        if command.description is not None:
                            self.descriptions[message.author.id] = command.description
                            desc = "\n**%s** adds: %s" % (turnip.name, command.description)
                        
                        msg = await self.report_channel.send(">>> **%s** has turnips selling for **%d**. Local time: **%s**. React to this message with 🦝 to be queued up for a code. %s" % (turnip.name, turnip.current_price(), turnip.current_time().strftime("%a, %I:%M %p"), desc))
                        await msg.add_reaction('🦝')
                        self.associated_user[msg.id] = message.author.id
                        self.associated_message[message.author.id] = msg

                        self.loop.create_task( self.queue_manager(message.author.id) )
                    elif res == turnips.Status.TIMEZONE_REQUIRED:
                        await message.channel.send("This seems to be your first time setting turnips, so you'll need to provide both a dodo code and a GMT offset (just a positive or negative integer). The dodo code can be a placeholder if you want.")
                    elif res == turnips.Status.PRICE_REQUIRED:
                        await message.channel.send("You'll need to tell us how much the turnips are at least.")
                    elif res == turnips.Status.DODO_REQUIRED:
                        await message.channel.send("This seems to be your first time setting turnips, so you'll need to provide both a dodo code and a GMT offset (just a positive or negative integer). The dodo code can be a placeholder if you want.")
                    elif res == turnips.Status.ITS_SUNDAY:
                        await message.channel.send("I'm afraid the turnip prices aren't set on Sundays, so will you please come again tomorrow instead?")
                    elif res == turnips.Status.CLOSED:
                        await message.channel.send("That doesn't sound right. The Nooklings should be closed at this time. If you've got something weird going on with your timezone, please add or subtract from your UTC offset to match their times.")
            else:
                await message.channel.send("Usage: \"[price] [optional dodo code] [optional gmt offset--an integer such as -5 or 8] [optional description, markdown supported]\"\n\n The quotes (\")and square brackets ([]) are not part of the input!\n\nExample usage: *123 C0FEE 8*\n\n All arguments are required if you wish to include a description, but feel free to put a placeholder price like 1 if you were opening for reasons other than turnips.")
        else:
            await self.public_message_handler(message)
            # await message.channel.send("Please message Lloid directly with your turnip prices! %s" % message.channel)

    async def public_message_handler(self, message):
        if message.content == "!queueinfo":
            await self.handle_queueinfo(message)

if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("TOKEN")
    interval = os.getenv("QUEUE_INTERVAL")

    if not token:
        raise Exception('TOKEN env variable is not defined')

    if not os.getenv("ANNOUNCE_ID"):
        raise Exception('ANNOUNCE_ID env variable is not defined')

    if interval:
        queue_interval = int(interval)
        print(f"Set interval to {interval}")

    client = Lloid()
    client.run(token)

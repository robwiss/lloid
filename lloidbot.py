import discord
from discord.utils import get
import sqlite3
import turnips
import asyncio
import sys

queue = []
queue_interval = 60*5
poll_sleep_interval = 5

class Command:
    Successful = 0
    Error = 1

    # Command types
    Close = 2
    Done = 3

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

        self.price = None
        self.dodo = None
        self.tz = None
        self.status = Command.Successful
        self.cmd = 0

        if command is None:
            self.status = Command.Error
            return
        commands = command.split()
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
                if len(commands[1]) != 5:
                    self.status = Command.Error
                    return
                self.dodo = commands[1]
            if len(commands) > 2:
                try:
                    self.tz = int(commands[2])
                except ValueError:
                    self.status = Command.Error
                    return
        

class Lloid(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        self.report_channel = discord.utils.get(self.get_all_channels(), name='turnips')
        self.chan = 'global'
        # await self.report_channel.send("I'm online")
        self.db = sqlite3.connect("test.db") 
        self.market = turnips.StalkMarket(self.db)
        self.associated_user = {} # message id -> id of the user the message is about
        self.associated_message = {} # reverse mapping of the above
        self.sleepers = {}
        self.recently_departed = {}

    async def on_reaction_add(self, reaction, user):
        if user == client.user or reaction.message.author != client.user:
            print("Not a reaction i should care about")
            return
        print ("reacted")
        print (reaction.message.id, self.associated_user)
        if reaction.emoji == '🦝':
            await self.queue_user(reaction, user)

    async def queue_user(self, reaction, user):
        if reaction.message.id in self.associated_user:
            status, size = self.market.request(user.id, self.associated_user[reaction.message.id])
            if status:
                print("queued %s up for %s" % (user.id, self.associated_user[reaction.message.id]))
                if size == 0:
                    size = 1
                interval_s = queue_interval * (size - 1) // 60
                interval_e = queue_interval * size // 60
                await user.send("Queued you up for a dodo code. Estimated time: %d-%d minutes, give or take. If you want to queue up elsewhere, or if you have to go, just unreact and it'll free you up." % (interval_s, interval_e))
            else:
                await user.send("It sounds like either the market is now closed, or you're in line elsewhere at the moment.")

    async def on_reaction_remove(self, reaction, user):
        if reaction.emoji == '🦝' and reaction.message.id in self.associated_user and user.id in self.market.queue.requesters:
            waiting_for = self.market.queue.requesters[user.id]
            if waiting_for == self.associated_user[reaction.message.id] and self.market.forfeit(user.id):
                await user.send("Removed you from the queue.")

    async def queue_manager(self, owner):
        while True:
            task = None
            try:
                task = self.market.next(owner)
            except:
                await asyncio.sleep(poll_sleep_interval)
                continue
            if task is None: # Then the owner closed
                print("Closed queue for %s" % owner)
                break

            await self.get_user(task[0]).send("Hope you enjoy your trip to **%s**'s island! Be polite, observe social distancing, leave a tip if you can, and **please be responsible and message me \"__done__\" when you've left.**. The Dodo code is **%s**." % (task[1].name, task[1].dodo))
            q = list(self.market.queue.queues[owner].queue)
            if len(q) > 0:
                next_in_line = self.get_user(q[0])
                if next_in_line is not None:
                    next_in_line.send("Your flight to **%s**'s island is boarding soon! Please have your tickets ready, we'll be calling you in shortly! (5 minutes or less)" % task[1].name)
                print(q[0])

            self.sleepers[owner] = self.loop.create_task(asyncio.sleep(queue_interval))
            self.recently_departed[task[0]] = owner
            print("%s just departed for %s" % (task[0], owner))
            try:
                await self.sleepers[owner]
            except:
                pass
            if owner in self.sleepers:
                del self.sleepers[owner]

    async def on_message(self, message):
        # Lloid should not respond to self
        if message.author == client.user:
            return

        if isinstance(message.channel, discord.DMChannel): 
            command = Command(message.content)
            if command.status == Command.Successful:
                if command.cmd == Command.Close:
                    await message.channel.send("Thanks for responsibly closing your doors! I'll give my condolences to the people still in line, if any.")
                    denied, status = self.market.close(message.author.id)
                    if status == turnips.Status.SUCCESS:
                        for d in denied:
                            await self.get_user(d).send("Apologies, but it looks like the person you were waiting for closed up.")
                        await self.associated_message[message.author.id].edit(content=">>> Sorry! This island has been delisted!")
                        # await self.associated_message[message.author.id].unpin()
                        del self.associated_user[self.associated_message[message.author.id].id]
                        del self.associated_message[message.author.id]
                elif command.cmd == Command.Done:
                    guest = message.author.id
                    if guest in self.recently_departed:
                        owner = self.recently_departed[guest]
                        self.sleepers[owner].cancel()
                        await message.channel.send("Thanks for the heads-up! Letting the next person in now.")
                else:
                    res = self.market.declare(message.author.id, message.author.name, command.price, command.dodo, command.tz)
                    if res == turnips.Status.SUCCESS or res == turnips.Status.ALREADY_OPEN:
                        await message.channel.send("Okay! Please be responsible and message \"**close**\" to indicate when you've closed. You can update the dodo code with the normal syntax.")
                        
                        turnip = self.market.get(message.author.id)
                        msg = await self.report_channel.send(">>> **%s** has turnips selling for **%d**. Local time: **%s**. React to this message with 🦝 to be queued up for a code." % (turnip.name, turnip.current_price(), turnip.current_time().strftime("%a, %I:%M %p")))
                        # await msg.pin()
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
                await message.channel.send("Usage: \"[price] [optional dodo code] [optional gmt offset]\"")
        else:
            await self.public_message_handler(message)
            # await message.channel.send("Please message Lloid directly with your turnip prices! %s" % message.channel)
    
    async def public_message_handler(self, message):
        if message.content == "!queueinfo":
            guest = message.author.id
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
                timeleft = index * queue_interval
                await message.channel.send("Approximate time left for you: %d seconds. Remaining people in whole queue: %d" % (timeleft, qsize))


client = Lloid()
with open("secret") as f:
    client.run(f.readline())
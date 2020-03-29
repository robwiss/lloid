import discord
import sqlite3
import turnips

queue = []

class Command:
    Successful = 0
    Error = 1

    def __init__(self, command):
        self.price = None
        self.dodo = None
        self.tz = None
        self.status = Command.Successful

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
        self.report_channel = discord.utils.get(self.get_all_channels(), name='lloidonly')
        self.chan = 'global'
        await self.report_channel.send("I'm online")
        self.db = sqlite3.connect("test.db") 
        self.market = turnips.StalkMarket(self.db)

    async def on_message(self, message):
        # Lloid should not respond to self
        if message.author == client.user:
            return

        if isinstance(message.channel, discord.DMChannel): 
            command = Command(message.content)
            if command.status == Command.Successful:
                res = self.market.declare(message.author.id, message.author.name, command.price, command.dodo, command.tz)
                if res == turnips.Status.SUCCESS:
                    await message.channel.send("Done.")

                    turnip = self.market.get(message.author.id)
                    await self.report_channel.send("%s has turnips selling for %d. Local time: %s" % (turnip.name, turnip.current_price(), turnip.current_time().strftime("%a, %I:%M %p")))

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
            pass 
            # await message.channel.send("Please message Lloid directly with your turnip prices! %s" % message.channel)


client = Lloid()
with open("secret") as f:
    client.run(f.readline())
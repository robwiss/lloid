from datetime import datetime, timedelta
import time, functools
import discord
import sqlite3

# Don't forget to install timers: pip install discord-timers -U

def db_init(db):
    db.execute("""create table if not exists turnips(chan, nick, dodo, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, utcoffset, latesttime, 
            primary key(chan, nick))""")

    wipe_old_prices(db)

    db.commit()


def utc():
    return time.gmtime()

def current_datetime(offset):
    return datetime.utcnow() + timedelta(hours=offset)

def wipe_old_prices(db):
    # day = 24 * 60 * 60 # seconds
    # week = 7 * day
    turnips = get_all(db)
    for t in turnips:
        latest = datetime.strptime(t[14], "%Y-%m-%d %H:%M:%S.%f")
        if latest.weekday() > current_datetime(t[13]).weekday() or (current_datetime(t[13]) - latest).days > 6:
            print ("wiping")
            db.execute("update turnips set val1a=NULL, val1b=NULL, val2a=NULL, val2b=NULL, val3a=NULL, val3b=NULL, val4a=NULL, val4b=NULL, val5a=NULL, val5b=NULL, val6a=NULL, val6b=NULL where nick=?", (t[0],) )

def get_all(db, chan=None):
    if chan is not None:
        return db.execute("select nick, dodo, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, utcoffset, latesttime from turnips where chan=?", (chan,)).fetchall()
    else:
        return db.execute("select nick, dodo, val1a, val1b, val2a, val2b, val3a, val3b, val4a, val4b, val5a, val5b, val6a, val6b, utcoffset, latesttime from turnips ").fetchall()

def get_timezone(db, nick, chan):
    return db.execute("select utcoffset from turnips where nick=?", (nick,)).fetchone()

def get_dodo(db, nick, chan):
    return db.execute("select dodo from turnips where nick=?", (nick,)).fetchone()

def get_highest(db, chan):
    rows = get_all(db, chan)

    r = []
    for user in rows:
        interval, index = compute_current_interval(user[14])
        if interval == "7a" or interval == "7b":
            continue
        if index is not None and user[index] is not None:
            r += [(user[0], user[index], user[14])]

    if r:
        return functools.reduce(lambda a,b: a if a[1] > b[1] else b, r)
    else:
        return None

def compute_current_interval(offset):
    local = current_datetime(offset)
    if local.hour < 10 or local.hour >= 22:
        return None, None
    day_of_week = local.weekday() + 1
    add = 2
    interval = "a"
    #if day_of_week >= 7 or day_of_week <= 0:
    #	return None, None
    if local.hour >= 12:
        add = 3
        interval = "b"
    return str(day_of_week) + interval, local.weekday()*2  + add

def exists(db, user, chan):
    r = get_all(db, chan)
    for u in r:
        if u[0] == user:
            return True
    return False

def update(db, chan, nick, dodo, val, tz):
    interval, _ = compute_current_interval(tz)
    field = "val" + interval
    if not exists(db, nick, chan):
        db.execute("replace into turnips(chan, nick, dodo," + field + ", utcoffset, latesttime) values"
                   " (?,?,?,?,?)", (chan, nick, val, tz, current_datetime(tz)))
    else:
        db.execute("update turnips set " + field + "=?, utcoffset=?, latesttime=? where nick=? ", 
            (val, tz, current_datetime(tz), nick))

    db.commit()

def is_int(s):
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()

def split_in_two(inp):
    spl = inp.strip().split(None, 1)
    head = spl[0]
    tail = None

    if len(spl) > 1:
        head = spl[0]
        tail = spl[1]
    return head, tail

#@hook.command
#@hook.command("st")
#@hook.command("setnips")
def setturnips(inp, nick='', chan='', db=None):
    "!st <price> [optional UTC offset]"
    db_init(db)

    if inp is None or inp.strip() == "":
        return ("!turnips <price> [optional dodo code] [optional UTC offset]", False)

    head, tail = split_in_two(inp)

    if not head.strip().isdigit():
        return ("Just the price, please", False)
    if int(head.strip()) >= 1000:
        return ("That sounds unrealistically high.", False)

    tz = None
    existing_timezone = get_timezone(db, nick, chan)
    inf = ""
    if tail is not None and is_int(tail.split()[-1]) and abs(int(tail.split()[-1])) < 24:
        tz = int(tail.split()[-1])
    elif existing_timezone is not None:
        tz = existing_timezone[0]

    dodo = get_dodo(db, nick, chan)
    if dodo is not None:
        dodo = dodo[0]
    if tail is not None and len(tail.split()[0]) > 2:
        dodo = tail.split()[0][:5]

    if dodo is None or tz is None: 
        return ("This seems to be your first time setting turnips, so you'll need to provide both a dodo code and a timezone. The dodo code can be a placeholder if you want.", False)

    interval, _ = compute_current_interval(tz)
    print (interval)
    if interval is None:
        return ("That doesn't sound right. The Nooklings should be closed at this time. If you've got an ordinance, please add or subtract from your UTC offset to match their times.", False)

    if interval == "7a" or interval == "7b":
        return ("I'm afraid the turnip prices aren't set on Sundays, so will you please come again tomorrow instead?", False)

    update(db, chan, nick, dodo, int(head.strip()), tz)

    return ("Done. %s" % inf, True)

#@hook.command
#@hook.command("t")
def top(inp, chan='', db=None):
    db_init(db)

    t = get_highest(db, chan)

    if t is None:
        return "No active turnip prices on record. You can view previous prices from this week with !market"

    zone = "(currently %s)" % (current_datetime(t[3])).strftime("%A, %I:%M %p, %d-%m-%Y")

    return "Highest active turnip price comes from %s (%s) with %s. %s" % (t[0], t[1], t[2], zone)

#@hook.command
#@hook.command("dt")
def delturnip(inp, chan='', nick='', db=None):
    if inp.strip() != "":
        nick = inp.strip()
    db.execute("delete from turnips where lower(nick) = lower(?)", (nick,))
    db.commit()

    return "Done."

def formatPrices(prices):
    s = ":"
    for p in prices:
        if p is None:
            s += "__:"
        else:
            s += str(p) + ":"
    return s

# @hook.command
def market(inp, chan='', pm=None, db=None):
    db_init(db)

    pm("You can update your market status with !st <price> [optional UTC offset]")

    r = get_all(db, chan)
    # r.sort(key=lambda t: -t[2])
    if len(r) == 0:
        pm("Nobody's listed any prices that are still active.")

    for dude in r:
        zone = "(currently %s)" % (current_datetime(dude[14])).strftime("%A, %I:%M %p, %d-%m-%Y")
        _, index = compute_current_interval(dude[14])
        if index is not None and dude[index] is not None:
            pm("%s: - %s bells - %s - pattern: %s" % (dude[0], dude[index], zone, formatPrices(dude[2:index+1])))
        elif index is None:
            pm("%s: - Closed - %s - pattern: %s" % (dude[0], zone, formatPrices(dude[2:14])))
        else:
            pm("%s: - Current price unknown - %s - pattern: %s" % (dude[0], zone, formatPrices(dude[2:14])))


class Lloid(discord.Client):
    async def market(self, inp, chan='', pm=None, db=None):
        db_init(db)

        await pm("You can update your market status with !st <price> [optional UTC offset]")

        r = get_all(db, chan)
        # r.sort(key=lambda t: -t[2])
        if len(r) == 0:
            await pm("Nobody's listed any prices that are still active.")

        for dude in r:
            zone = "(currently %s)" % (current_datetime(dude[13])).strftime("%A, %I:%M %p, %d-%m-%Y")
            _, index = compute_current_interval(dude[13])
            if index is not None and dude[index] is not None:
                await pm("%s: - %s bells - pattern: %s" % (dude[0], dude[index], zone, formatPrices(dude[1:index+1])))
            elif index is None:
                await pm("%s: - Closed - %s - pattern: %s" % (dude[0], zone, formatPrices(dude[1:13])))
            else:
                await pm("%s: - Current price unknown - %s - pattern: %s" % (dude[0], zone, formatPrices(dude[1:13])))

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        self.report_channel = discord.utils.get(self.get_all_channels(), name='lloidonly')
        self.chan = 'global'
        self.pm = lambda msg: self.report_channel.send(msg)
        await self.pm("I'm online")
        self.db = sqlite3.connect("test.db") 
        db_init(self.db)

    async def on_pm(self, message):
        command = message.content.split()
        if len(command) == 0:
            return
        
        
        response, status = setturnips(message.content, message.author.name, self.chan, self.db)
        await self.pm()
        if status:


    async def on_message(self, message):
        if message.author == client.user:
            return

        if message.channel == discord.DMChannel:
            await self.on_pm(message)
            return

        command = message.content
        rest = None

        content = message.content.split(None, 1)

        if len(content) > 1 and content[0][0] == "!":
            command, rest = content

        if command == '!market':
            await self.market(rest, self.chan, self.pm, self.db)
        elif command == '!turnips':
            response, _ = setturnips(rest, self.chan, None, self.db)
            await message.channel.send(response)
        elif command == '!top':
            response = top(rest, self.chan, self.db)
            await message.channel.send(response)


client = Lloid()
client.run('NjkxMjM4MTUyMTAyMzQ2Nzgz.XndE8Q.FRvf4Rz4jamFF1QL95OeOevTbUs')
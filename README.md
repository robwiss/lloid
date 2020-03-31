# lloid
A turnip tracker for Discord

I hacked this together quickly so that we'd be ready for the turnip rush later this week. It lets Discord users declare your turnip price, so that people can queue up for visits. There's a delay between codes being handed out, so it's perfect if you have a ton of people clamoring to get into your town.
A lot of code was ported over from an IRC bot I made that tracked turnip prices, so if you're exploring the code, you may find some functionality that isn't really being used... but which I might someday.

Running:
1. You'll need Python 3.5 at minimum (I haven't tested it on that; I'm on 3.6.9).
2. Install discord.py.
3. On the platform you want to run it, place lloidbot.py, turnips.py, and a file called 'secret'
4. The secret file just contains your secret key for your Discord bot.
5. Run lloidbot.py

Tweaking:
I haven't made this thing highly configurable but you can change the queue delay time by changing queue_interval in lloidbot.py to the number of seconds you want.
The channel it joins is #turnips; just search through lloidbot.py to find where you can change that. I, uh, haven't supported it being on multiple channels or Discords yet.
The bot can pin and unpin listings, but I haven't actually tested this out because it doesn't have permissions to do so on the Discord I'm on. Just comment out those lines if you wanna give it a try.

Usage:
1. If your Nooklings are buying turnips at a high price:
  a. PM Lloid the following: [price] [optional dodo] [optional gmt offset]
  b. The dodo code and gmt offset are not optional if it's your first time to set turnip prices.
  c. Lloid will then post in #turnips
  d. PM the bot the word 'close' without the quotes to delist your prices and send an apology to everyone still waiting in line.
  Examples:
    New user, Nooklings buying turnips at 150 bells, Dodo code is DODOX, and timezone is GMT+8:
      150 DODOX 8 
    Already declared a price/dodo code/timezone before, but you had network problems so you had to get a new Dodo code.
      150 DODOY
    Moved to another country, so you have a new timezone.
      150 DODOZ -5
    Same play session, but prices changed to 20 bells so you have to update the listing:
      20 

2. If you saw a high price being posted in #turnips:
  a. React with the raccoon emoji. Lloid will make the initial reaction to help out.
  b. You'll be queued along with anyone else who reacted. Codes will be dispensed in 5 minute intervals (by default), but it may be less if your community is responsible about informing the bot when they've finished their turnip hawking.
  c. If you got a code, sold your turnips, and left the airport, then please do everyone a favor and message Lloid 'done' without the quotes. This will wake it up from sleeping and let the next person in early instead of having them wait the full five minutes.
  d. If you have yet to get a code and you find that you have pressing business to attend to, you can remove yourself from the queue by unreacting.
  

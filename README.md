<img src="https://github.com/bomjacob/VocaBot/blob/gh-pages/images/vocabot.png" height="200px" />

# VocaBot
Vocaloid Bot for the Telegram Messenger

Uses data from [VocaDB.net](http://vocadb.net) ([VocaDB/vocadb](https://github.com/VocaDB/vocadb)). Click [here](http://wiki.vocadb.net/wiki/29/license) for licensing information.

##How to use
###Easy method
Use from telegram via [@VocaDBBot](https://telegram.me/VocaDBBot) (temporary name).

###Set up yourself
You can also run the bot yourself by following these steps:

1. Install python 3, clone repository and install requirements via pip
2. Ask [@botfather](https://telegram.me/botfather) for a bot token and put it in `VOCABOT_TOKEN` environment variable. If you want botan tracking (optional) put your token `VOCABOT_BOTAN_TOKEN`. You might also want to change `OWNER_IDS` inside [VocaBot/constants.py](VocaBot/constants.py) (if you don't want me to be able to kill your bot that is).
3. Run `$ python3 main.py`

#Thanks to
* [VocaDB.net](http://vocadb.net) ([VocaDB/vocadb](https://github.com/VocaDB/vocadb)) and all the amazing editors on there
* [@Cawthorned](https://github.com/Cawthorned) for translations/personality modules (not currently implemented) and profile picture
* and let's not forget [https://github.com/python-telegram-bot/python-telegram-bot](python-telegram-bot)

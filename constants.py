from inter import underscore as _

__version__ = "0.1.0"
VOCADB_API_ENDPOINT = "http://vocadb.net/api/"
OWNER_ID = 95205500
DB_FILE = 'data.sqlite'
VOCADB_USER_AGENT = 'Telegram-VocaDBBot/{}'.format(__version__)

PV_SERVICES = ['SoundCloud', 'Youtube', 'NicoNicoDouga', 'Piapro', 'Vimeo', 'Bilibili']

START_TEXT = _("""Hello {user_name}! I'm {bot_name}.
I use VocaDB.net to find all your favourite Vocaloid songs and artists.
Write /help to see a list of commands.""")

ABOUT_TEXT = _("""Created by @bomjacob.
I use data from VocaDB.net. Click <a href="http://wiki.vocadb.net/wiki/29/license">here</a> for licensing information.
Dialogue and profile picture by @Awthornecay
My code is open-source and available at <a href="https://github.com/bomjacob/VocaBot">github</a>.
Telegram bot privacy mode is enabled so I can only see commands and direct replies.""")

HELP_TEXT = _("""/search - search for a vocaloid song in Romaji, English or Japanese
/artist - search for an artist
/top - browse the most popular vocaloid songs
/new - browse the newest additions to my database
/set_lang - set the general language, or change my personality module
/set_voca_lang - change what language titles and artists are displayed in
/cancel - cancel current operation
/about - display information about my creators and VocaDB
/help - display this message

You can also use my inline version outside of group chats by using {username}
/help_inline for more info about that.""")


INLINE_HELP_TEXT = _("""Inline Help""")

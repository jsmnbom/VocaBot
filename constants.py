from inter import underscore as _

__version__ = "0.1.1"
VOCADB_API_ENDPOINT = "http://vocadb.net/api/"
OWNER_ID = 95205500
DB_FILE = 'data.sqlite'
VOCADB_USER_AGENT = 'Telegram-{bot_name}/{version}'.format(bot_name='{bot_name}', version=__version__)

PV_SERVICES = ['SoundCloud', 'Youtube', 'NicoNicoDouga', 'Piapro', 'Vimeo', 'Bilibili']

START_TEXT = _("""Hello {user_name}! I'm {bot_name}.
I use VocaDB.net to find all your favourite Vocaloid songs and artists.
Write /help to see a list of commands.""")

ABOUT_TEXT = _("""<b>{bot_name} version {version}</b>
Created by @bomjacob.
Dialogue and profile picture by @Awthornecay.
I use data from VocaDB.net. Click <a href="http://wiki.vocadb.net/wiki/29/license">here</a> for licensing information.
My code is open-source and available at <a href="https://github.com/bomjacob/VocaBot">github</a>.
Telegram bot privacy mode is enabled so, <i>in group chats</i>, I can only see commands and direct replies.""").format(
    version=__version__, bot_name='{bot_name}')

HELP_TEXT = _("""/search - search for a vocaloid song in Romaji, English or Japanese
/artist - search for an artist
/top - browse the most popular vocaloid songs
/new - browse the newest additions to my database
/set_lang - set the general language, or change my personality module
/set_voca_lang - change what language titles and artists are displayed in
/cancel - cancel current operation
/about - display information about my creators and VocaDB
/help - display this message

You can also use my inline version outside of group chats by using {bot_name}""")

INLINE_HELP_TEXT = _("""Hello {user_name}! I'm {bot_name}.
I use VocaDB.net to find all your favourite Vocaloid songs and artists.
You can use my inline version by typing {bot_user_name} followed by any vocaloid song query.
Write /help to see a list of non-inline-commands.""")

SETTINGS_TEXT = _("""<b>Settings for {bot_name}</b>
<i>{type}</i>&#8201;&#8201;interface language: <code>{lang}</code>
Change: /set_lang

<i>{type}</i>&#8201;&#8201;incaDB language: <code>{voca_lang}</code>
Change: /set_voca_lang

VocaDB language is the language used for song and artist titles.
<i>User</i>&#8201;&#8201;language is used for private messages and inline requests whereas <i>chat</i>&#8201;&#8201;language is the language used in the current group chat.""")

import logging
import re
from urllib.parse import unquote

from telegram import ParseMode
from telegram.ext import ConversationHandler

from constants import __version__, OWNER_IDS
from i18n import _
from settings import translate
from util import botan_track

BASE_START_TEXT = _("""Hello {user_name}! I'm {bot_name}.
I use VocaDB.net to find all your favourite Vocaloid songs, artists and albums.
""")

START_TEXT = _("""Write /help to see a list of commands.""")

ABOUT_TEXT = _("""<b>About vocaloid</b>
For a detailed explanation of everything vocaloid please see <a href="http://vocadb.net/Help#Vocaloid">this article on VocaDB.net</a> (click on the vocaloid tab at the top).

<b>About this bot</b>
<i>{bot_name} version {version}</i>
Created by @bomjacob.
Dialogue and profile picture by @Awthornecay.
I use data from VocaDB.net. Click <a href="http://wiki.vocadb.net/wiki/29/license">here</a> for licensing information.
My code is open-source and available at <a href="https://github.com/bomjacob/VocaBot">github</a>.""")

# noinspection SpellCheckingInspection
PRIVACY_TEXT = _("""<b>Privacy information for {bot_name}</b>
<i>Applies both to inline and non-inline.</i>
Telegram bot privacy mode is enabled so, <i>in group chats</i>, I can only see commands and direct replies.
All bot requests are tracked via <a href="http://botan.io">Botan</a> which is powered by Yandex AppMetrica.
""")

HELP_TEXT = _("""/search - search for a vocaloid song, artist or album
/song - search for a song
/artist - search for an artist
/album - search for an album
/top - browse the most popular vocaloid songs
/new - browse the newest song additions
/trending - browse trending songs
/cancel - cancel current operation
/about - display info about my creators, vocaloid, and VocaDB
/privacy - display privacy notices
/settings - display or change language settings
/inline - display information and help about inline mode
/help - display this message

When searching you can use either English, Romaji or Japanese.
You can also use my inline version by typing {bot_name} in a chat.

You can also search for a song by sending me a link to a PV of it. This will require you to append my username to the message if in a group chat. Example:
<code>http://youtu.be/ll0arX6EZaw {bot_name}</code>""")

INLINE_HELP_TEXT = _("""You can use my inline version by typing {bot_name} followed by any vocaloid song query.
By default I will search songs, artists, and albums. If you want to limit me to songs, artists, or albums, prepend your query by <code>!s</code>, <code>!ar</code>, or <code>!al</code> respectively.
<b>Examples:</b>
<code>{bot_name} miku</code> will search songs, artists and albums.
<code>{bot_name} !s tell your world</code> will only search for songs.
<code>{bot_name} !al before light</code> will only search albums.

Write /help to see a list of non-inline-commands.""")


@translate
@botan_track
def start(bot, update, args, update_queue):
    if len(args) == 1 and args[0] == 'help_inline':
        bot.send_message(chat_id=update.message.chat.id,
                         text=BASE_START_TEXT.format(user_name=update.message.from_user.first_name,
                                                     bot_name=bot.name) + INLINE_HELP_TEXT.format(bot_name=bot.name),
                         disable_web_page_preview=True,
                         parse_mode=ParseMode.HTML)
        return
    elif len(args) > 0:
        # Webogram doesn't urldecode/unquote
        args = unquote(' '.join(args)).split(' ')
        if len(args) == 2 and args[0] == 'cmd':
            update.message.text = args[1]
            update_queue.put(update)
            return
    bot.send_message(chat_id=update.message.chat.id,
                     text=BASE_START_TEXT.format(user_name=update.message.from_user.first_name,
                                                 bot_name=bot.name) + START_TEXT,
                     disable_web_page_preview=True)


@translate
@botan_track
def about(bot, update):
    bot.send_message(chat_id=update.message.chat.id, text=ABOUT_TEXT.format(bot_name=bot.name, version=__version__),
                     parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@translate
@botan_track
def privacy(bot, update):
    bot.send_message(chat_id=update.message.chat.id, text=PRIVACY_TEXT.format(bot_name=bot.name, version=__version__),
                     parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@translate
@botan_track
def send_help(bot, update):
    bot.send_message(chat_id=update.message.chat.id, text=HELP_TEXT.format(bot_name=bot.name),
                     parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@translate
@botan_track
def inline(bot, update):
    bot.send_message(chat_id=update.message.chat.id, text=INLINE_HELP_TEXT.format(bot_name=bot.name),
                     disable_web_page_preview=True, parse_mode=ParseMode.HTML)


@translate
def kill(bot, update):
    logging.debug("Got /kill from %s" % update.message.from_user.id)
    if update.message.from_user.id in OWNER_IDS:
        logging.critical("Sending SIGTERM to self!")
        import signal
        import os
        import time
        time.sleep(5)
        os.kill(os.getpid(), signal.SIGTERM)
    else:
        bot.send_message(chat_id=update.message.chat.id, text=_("I can't let you do that, dave."))


@translate
def unknown(bot, update):
    if update.message.chat.type == 'private':
        bot.send_message(chat_id=update.message.chat.id,
                         text=_("Unknown command. Try again or type /help to see list of commands."))
    else:
        match = re.match(r'^/(?:((?:\S*?){bot_name})|((?:\S*)@(?:\S*))|(\S*))'.format(bot_name=bot.name),
                         update.message.text)
        if match:
            if match.groups()[0] or match.groups()[2]:
                bot.send_message(chat_id=update.message.chat.id,
                                 text=_("Unknown command. Try again or type /help to see list of commands."))


@translate
def cancel(bot, update):
    # We don't need (or rather we can't) to clear from browse.ongoing or inline.ongoing, since they both use unique keys
    bot.send_message(chat_id=update.message.chat.id, text=_('Operation cancelled. Type /help to see list of commands.'))
    return ConversationHandler.END

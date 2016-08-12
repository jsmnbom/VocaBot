import logging
import os
import sys

from telegram.ext import (Updater, ConversationHandler, CommandHandler, RegexHandler, CallbackQueryHandler,
                          MessageHandler, Filters, InlineQueryHandler)

import VocaBot.browse as browse
import VocaBot.info as info
import VocaBot.inline as inline
import VocaBot.settings as settings
import VocaBot.text as text
from VocaBot.constants import SettingState, BrowseState
from VocaBot.util import cancel_callback_query
from VocaBot.vocadb import voca_db

logger = logging.getLogger(__name__)


# TODO: Better error handling
# TODO: Use bot.send_chat_action?
# TODO: Handle what stuff should run_async and what should not better
# TODO: Maybe add a timeout to api and telegram requests too?

# noinspection SpellCheckingInspection
def init_log():
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# noinspection PyUnusedLocal
def error(bot, update, err):
    logger.warning('Update "%s" caused error "%s"' % (update, err))


def cancel(bot, update):
    # We don't need (or rather we can't) to clear from browse.ongoing or inline.ongoing, since they both use unique keys
    return ConversationHandler.END


def add_update_handlers(dp):
    browse_handler = ConversationHandler(
        entry_points=[
            CommandHandler('artist', browse.search_artist, pass_args=True, allow_edited=True),
            CommandHandler('song', browse.search_song, pass_args=True, allow_edited=True),
            CommandHandler('album', browse.search_album, pass_args=True, allow_edited=True),
            CommandHandler('search', browse.search_all, pass_args=True, allow_edited=True),
            CommandHandler('new', browse.new),
            CommandHandler('top', browse.top),
            RegexHandler(r'^/(dev)_(\d+)@?$', browse.derived, pass_groups=True),
            RegexHandler(r'^/(rel)_(\d+)@?$', browse.related, pass_groups=True),
            CallbackQueryHandler(browse.artist, pattern=r'^(arlist)\|(.*)\|(.*)$', pass_groups=True)
        ],
        states={
            BrowseState.page: [
                MessageHandler([Filters.text], browse.edited, allow_edited=True, pass_update_queue=True)
            ],
            BrowseState.input: [MessageHandler([Filters.text], browse.search_input, allow_edited=True)],
            BrowseState.input_song: [MessageHandler([Filters.text], browse.search_input_song, allow_edited=True)],
            BrowseState.input_artist: [MessageHandler([Filters.text], browse.search_input_artist, allow_edited=True)],
            BrowseState.input_album: [MessageHandler([Filters.text], browse.search_input_album, allow_edited=True)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    # Was inside BrowseState.page state, but we always want paging buttons to work.. even in semi old messages
    browse_page_handler = CallbackQueryHandler(browse.next_page, pattern=r'^(page)\|(.+)\|(.+)$', pass_groups=True)

    settings_handler = ConversationHandler(
        entry_points=[
            CommandHandler('settings', settings.start)
        ],
        states={
            SettingState.settings: [CallbackQueryHandler(settings.change)],
            SettingState.interface: [CallbackQueryHandler(settings.interface)],
            SettingState.voca: [CallbackQueryHandler(settings.voca)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    start_handler = CommandHandler('start', text.start, pass_args=True)
    help_handler = CommandHandler('help', text.send_help)
    inline_handler = CommandHandler('inline', text.inline)
    about_handler = CommandHandler('about', text.about)
    privacy_handler = CommandHandler('privacy', text.privacy)
    kill_handler = CommandHandler('kill', text.kill)

    # TODO: Handle edited_message in these too? (would be nice for eg. /artist pinocchio)
    song_handler = RegexHandler(r'^/(?:info|s)_(\d+)(@.+)?$', info.song, pass_groups=True)
    artist_handler = RegexHandler(r'^/(?:ar)_(\d+)(@.+)?$', info.artist, pass_groups=True)
    album_handler = RegexHandler(r'^/(?:al)_(\d+)(@.+)?$', info.album, pass_groups=True)

    lyrics_handler = CallbackQueryHandler(info.lyrics, pattern=r'^(?:ly)\|([^\|]*)\|?([^\|]*)?$', pass_groups=True)
    pv_handler = CallbackQueryHandler(info.pv, pattern=r'^(?:pv)\|([^\|]*)\|?([^\|]*)?$', pass_groups=True)
    album_list_handler = CallbackQueryHandler(info.album_list, pattern=r'^(?:allist)\|(.*)$', pass_groups=True)
    # Remove the spinning loading icon from buttons
    cancel_callback_query_handler = CallbackQueryHandler(cancel_callback_query)

    song_direct_handler = InlineQueryHandler(inline.song_direct, pattern=r'^!(?:s)#(\d+)$', pass_groups=True)
    song_search_handler = InlineQueryHandler(inline.song_search, pattern=r'^\!(?:s) ?(.*)$', pass_groups=True)
    album_direct_handler = InlineQueryHandler(inline.album_direct, pattern=r'^!(?:al)#(\d+)$', pass_groups=True)
    album_search_handler = InlineQueryHandler(inline.album_search, pattern=r'^\!(?:al) ?(.*)$', pass_groups=True)
    artist_direct_handler = InlineQueryHandler(inline.artist_direct, pattern=r'^!(?:ar?)#(\d+)$', pass_groups=True)
    artist_search_handler = InlineQueryHandler(inline.artist_search, pattern=r'^\!(?:ar?) ?(.*)$', pass_groups=True)
    inline_leftover_handler = InlineQueryHandler(inline.delegate)  # All who didn't match above regex

    # Add handlers to dispatcher
    dp.add_handler(browse_handler)
    dp.add_handler(browse_page_handler)
    dp.add_handler(settings_handler)

    dp.add_handler(start_handler)
    dp.add_handler(help_handler)
    dp.add_handler(inline_handler)
    dp.add_handler(about_handler)
    dp.add_handler(privacy_handler)
    dp.add_handler(kill_handler)

    dp.add_handler(song_handler)
    dp.add_handler(artist_handler)
    dp.add_handler(album_handler)

    dp.add_handler(lyrics_handler)
    dp.add_handler(pv_handler)
    dp.add_handler(album_list_handler)
    dp.add_handler(cancel_callback_query_handler)

    dp.add_handler(song_direct_handler)
    dp.add_handler(artist_direct_handler)
    dp.add_handler(album_direct_handler)
    dp.add_handler(song_search_handler)
    dp.add_handler(album_search_handler)  # Has to be before artist since the 'r' in 'ar' is optional there
    dp.add_handler(artist_search_handler)
    dp.add_handler(inline_leftover_handler)

    return dp


def main():
    token = os.getenv('VOCABOT_TOKEN')
    if not token:
        logging.critical('NO TOKEN FOUND!')
        sys.exit()

    updater = Updater(token)

    # Now we know bot name, set the user-agent of vocadb api session
    voca_db.set_name(updater.bot.name)

    dp = updater.dispatcher

    # Add main handlers
    dp = add_update_handlers(dp)

    # Also add our "log everything" error handler
    dp.add_error_handler(error)

    # Start fetching updates, we might wanna use webhooks instead at some points.
    updater.start_polling()

    # Loop till we quit
    updater.idle()


if __name__ == '__main__':
    debug = os.getenv('VOCABOT_DEBUG', False)
    init_log()

    main()

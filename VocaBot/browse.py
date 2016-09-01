import math
import uuid
from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ForceReply
from telegram.ext import ConversationHandler
from telegram.ext.dispatcher import run_async

import info
from constants import BrowseState
from contentparser import content_parser
from settings import with_voca_lang, translate, get_setting
from util import botan_track
from vocadb import voca_db

ongoing = {}
replies = {}


@run_async
@translate
def next_page(bot, update, groups):
    key, cur_page = groups[1], groups[2]
    cur_page = int(cur_page)
    try:
        page_data, counts, context = ongoing[key](cur_page)
    except KeyError:
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text='Expired! Please start over.')
        return ConversationHandler.END

    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          message_id=update.callback_query.message.message_id,
                          text=content_parser(page_data, context=context, counts=counts),
                          reply_markup=keyboard(key, counts),
                          parse_mode=ParseMode.HTML)
    bot.answer_callback_query(callback_query_id=update.callback_query.id)

    return BrowseState.page


def send_page_one(bot, update, key, page, state):
    page_data, counts, context = page(1)
    update.message = (update.message or update.callback_query.message)
    if counts[1] == 1 and len(page_data) == 1:
        entry = page_data[0]
        if 'songType' in entry or 'artistType' in entry or 'discType' in entry:
            if update.callback_query:
                bot.answer_callback_query(callback_query_id=update.callback_query.id)
            if 'songType' in entry:
                info.song(bot, update, [entry['id']])
            elif 'artistType' in entry:
                info.artist(bot, update, [entry['id']])
            elif 'discType' in entry:
                info.album(bot, update, [entry['id']])
            return None

    message_id = update.message.message_id
    if message_id in replies:
        sent_message = bot.edit_message_text(chat_id=(update.message or update.callback_query.message).chat.id,
                                             message_id=replies[message_id][1],
                                             text=content_parser(page_data, context=context, counts=counts),
                                             reply_markup=keyboard(key, counts),
                                             parse_mode=ParseMode.HTML)

    else:
        sent_message = bot.send_message(chat_id=(update.message or update.callback_query.message).chat.id,
                                        text=content_parser(page_data, context=context, counts=counts),
                                        reply_markup=keyboard(key, counts),
                                        parse_mode=ParseMode.HTML)

    replies[message_id] = (state, sent_message.message_id)

    if update.callback_query:
        bot.answer_callback_query(callback_query_id=update.callback_query.id)

    return BrowseState.page


def keyboard(key, counts):
    # We don't want a keyboard if there's no results
    if counts[1] == 0:
        return None

    cur_page = counts[0] // 3 + 1
    last_page = math.ceil((counts[1]) / 3)

    data = 'page|{}|{}'.format(key, '{}')
    buttons = [InlineKeyboardButton('First' if cur_page > 1 else ' ',
                                    callback_data=data.format(1) if cur_page > 1 else 'page'),
               InlineKeyboardButton('Previous'.format(cur_page - 1) if cur_page > 1 else ' ',
                                    callback_data=data.format((cur_page - 1)) if cur_page > 1 else 'page'),
               InlineKeyboardButton('•{}•'.format(cur_page),
                                    callback_data='page'),
               InlineKeyboardButton('Next'.format(cur_page + 1) if cur_page < last_page else ' ',
                                    callback_data=data.format(cur_page + 1) if cur_page < last_page else 'page'),
               InlineKeyboardButton('Last'.format(last_page) if cur_page < last_page else ' ',
                                    callback_data=data.format(last_page) if cur_page < last_page else 'page')]
    return InlineKeyboardMarkup([buttons])


def page_wrapper(f):
    @wraps(f)
    # @run_async  # This is a bad idea xD
    def wrapper(bot, update, *args, **kwargs):
        key = str(uuid.uuid4())

        if update.edited_message:
            update.message = update.edited_message

        page, state = f(bot, update, *args, **kwargs)
        # We might have just gotten a BrowseState instead of page.
        if page is None:
            return state

        state = send_page_one(bot, update, key, page, state)
        ongoing[key] = page
        return state

    return wrapper


@page_wrapper
@translate
@with_voca_lang
@botan_track
def search(bot, update, args, lang, songs=False, artists=False, albums=False, state=None):
    query = args if type(args) == str else ' '.join(args)
    if songs and artists and albums:
        entries = voca_db.entries(query, lang)
    elif songs:
        originals_only = get_setting('originals', bot, update)
        entries = voca_db.songs(query, lang, originals_only=originals_only)
    elif artists:
        entries = voca_db.artists(query, lang)
    elif albums:
        entries = voca_db.albums(query, lang)
    else:
        return None, None
    return entries, state


def search_input(bot, update):
    return search(bot, update, update.message.text, songs=True, artists=True, albums=True, state=BrowseState.input)


def search_input_song(bot, update):
    return search(bot, update, update.message.text, songs=True, state=BrowseState.input_song)


def search_input_artist(bot, update):
    return search(bot, update, update.message.text, artists=True, state=BrowseState.input_artist)


def search_input_album(bot, update):
    return search(bot, update, update.message.text, albums=True, state=BrowseState.input_album)


def search_all(bot, update, args):
    if not args:
        bot.send_message(chat_id=update.message.chat.id, text="Enter search query.", reply_markup=ForceReply())
        return BrowseState.input
    return search(bot, update, args, songs=True, artists=True, albums=True)


def search_song(bot, update, args):
    if not args:
        bot.send_message(chat_id=update.message.chat.id, text="Enter song search query.", reply_markup=ForceReply())
        return BrowseState.input_song
    return search(bot, update, args, songs=True)


def search_artist(bot, update, args):
    if not args:
        bot.send_message(chat_id=update.message.chat.id, text="Enter artist search query.", reply_markup=ForceReply())
        return BrowseState.input_artist
    return search(bot, update, args, artists=True)


def search_album(bot, update, args):
    if not args:
        bot.send_message(chat_id=update.message.chat.id, text="Enter album search query.", reply_markup=ForceReply())
        return BrowseState.input_album
    return search(bot, update, args, albums=True)


@page_wrapper
@translate
@with_voca_lang
@botan_track
def top(bot, update, lang):
    return voca_db.songs('', lang), None


@page_wrapper
@translate
@with_voca_lang
@botan_track
def new(bot, update, lang):
    return voca_db.songs('', lang, sort='AdditionDate'), None


@page_wrapper
@translate
@with_voca_lang
def artist(bot, update, groups, lang):
    if groups[1] == 'ps':
        return voca_db.songs('', lang, artist_id=groups[2]), None
    elif groups[1] == 'ls':
        return voca_db.songs('', lang, artist_id=groups[2], sort='AdditionDate'), None
    elif groups[1] == 'pa':
        return voca_db.albums('', lang, artist_id=groups[2], sort='RatingAverage'), None
    elif groups[1] == 'la':
        return voca_db.albums('', lang, artist_id=groups[2], sort='ReleaseDate'), None


@page_wrapper
@translate
@with_voca_lang
def derived(bot, update, groups, lang):
    return voca_db.derived(groups[1], lang), None


@page_wrapper
@translate
@with_voca_lang
def related(bot, update, groups, lang):
    return voca_db.related(groups[1], lang), None


@page_wrapper
@translate
@with_voca_lang
def trending(bot, update, lang):
    return voca_db.top_rated_songs(lang), None


@page_wrapper
@translate
@with_voca_lang
def albums_by_song(bot, update, groups, lang):
    return voca_db.albums_by_song(groups[1], lang), None


def edited(bot, update, update_queue):
    if update.edited_message:
        message_id = update.edited_message.message_id
        update.message = update.edited_message
        update.edited_message = None
        if message_id in replies:
            update_queue.put(update)
            return replies[message_id][0]

import os
import uuid
from functools import wraps
from uuid import uuid4

from telegram import InlineQueryResultArticle, Emoji, InputTextMessageContent, ParseMode
from telegram.ext.dispatcher import run_async

from contentparser import content_parser
from i18n import _
from info import song_keyboard, artist_keyboard, album_keyboard
from settings import with_voca_lang, translate, get_setting
from vocadb import voca_db

ongoing = {}
MAX_INLINE_RESULTS = 10
INLINE_CACHE_TIME = int(os.getenv('VOCABOT_INLINE_CACHE_TIME_OVERWRITE', 5 * 60))


def answer(bot, update, entries, offset='', switch_pm=None):
    if not switch_pm:
        switch_pm = (_('Click for help.'), 'help_inline')

    results = []

    for entry in entries:
        try:
            thumb = entry['mainPicture']['urlThumb']
        except KeyError:
            thumb = ''

        content = content_parser(entry, info=True, inline=True, bot_name=bot.username)
        if 'songType' in entry:
            description = _('{artist}\n{type} song').format(artist=entry['artistString'], type=entry['songType'])
            if 'favoritedTimes' in entry:
                description += ' ' + _('with {favorites} favourites').format(favorites=entry['favoritedTimes'])
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=Emoji.MUSICAL_NOTE + ' ' + entry['name'],
                description=description,
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(content, parse_mode=ParseMode.HTML,
                                                              disable_web_page_preview=True),
                reply_markup=song_keyboard(entry, inline=True)
            ))
        elif 'artistType' in entry:
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=Emoji.MICROPHONE + ' ' + entry['name'],
                description='{type}'.format(type=entry['artistType']),
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(content, parse_mode=ParseMode.HTML,
                                                              disable_web_page_preview=True),
                reply_markup=artist_keyboard(entry, inline=True)
            ))
        elif 'discType' in entry:
            description = '{artist}\n{type}'.format(artist=entry['artistString'], type=entry['discType'])
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=Emoji.OPTICAL_DISC + ' ' + entry['name'],
                description=description,
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(content, parse_mode=ParseMode.HTML,
                                                              disable_web_page_preview=True),
                reply_markup=album_keyboard(entry, inline=True)
            ))

    update.inline_query.answer(results=results,
                               cache_time=INLINE_CACHE_TIME,
                               is_personal=True,
                               next_offset=offset,
                               switch_pm_text=switch_pm[0],
                               switch_pm_parameter=switch_pm[1])


def delegate_handler(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        if not update.inline_query.offset == '':
            next_page(bot, update, *args, **kwargs)
        else:
            return f(bot, update, *args, **kwargs)

    return wrapper


@delegate_handler
def delegate(bot, update):
    if update.inline_query.query == '':
        top(bot, update)
    else:
        search(bot, update)


@run_async
@translate
@with_voca_lang
def song_direct(bot, update, groups, lang):
    data = voca_db.song(groups[0], 'MainPicture, Names, Lyrics, Artists, PVs', lang)
    answer(bot, update, [data])


@run_async
@translate
@with_voca_lang
def artist_direct(bot, update, groups, lang):
    data = voca_db.artist(groups[0], 'MainPicture, Names', lang)
    answer(bot, update, [data])


@run_async
@translate
@with_voca_lang
def album_direct(bot, update, groups, lang):
    data = voca_db.album(groups[0], 'MainPicture, Names', lang)
    answer(bot, update, [data])


def page_wrapper(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        page, switch_pm = f(bot, update, *args, **kwargs)
        key = str(uuid.uuid4())
        ongoing[key] = page
        data = page(1)
        offset = key + '|2' if data[1][0] + MAX_INLINE_RESULTS < data[1][1] else ''
        answer(bot, update, data[0], offset=offset, switch_pm=switch_pm)

    return wrapper


@run_async
@page_wrapper
@delegate_handler
@translate
@with_voca_lang
def top(bot, update, lang):
    return voca_db.songs('', lang, max_results=MAX_INLINE_RESULTS), None


@run_async
@page_wrapper
@delegate_handler
@translate
@with_voca_lang
def search(bot, update, lang):
    switch_pm = (_('Searching songs, artists and albums'), 'help_inline')
    return voca_db.entries(update.inline_query.query, lang, max_results=MAX_INLINE_RESULTS), switch_pm


@run_async
@page_wrapper
@delegate_handler
@translate
@with_voca_lang
def song_search(bot, update, groups, lang):
    switch_pm = (_('Searching only songs'), 'help_inline')
    originals_only = get_setting('originals', bot, update)
    return voca_db.songs(groups[0], lang, max_results=MAX_INLINE_RESULTS, originals_only=originals_only), switch_pm


@run_async
@page_wrapper
@delegate_handler
@translate
@with_voca_lang
def artist_search(bot, update, groups, lang):
    switch_pm = (_('Searching only artists'), 'help_inline')
    return voca_db.artists(groups[0], lang, max_results=MAX_INLINE_RESULTS), switch_pm


@run_async
@page_wrapper
@delegate_handler
@translate
@with_voca_lang
def album_search(bot, update, groups, lang):
    switch_pm = (_('Searching only albums'), 'help_inline')
    return voca_db.albums(groups[0], lang, max_results=MAX_INLINE_RESULTS), switch_pm


@run_async
@translate
@with_voca_lang
def next_page(bot, update, lang, *args, **kwargs):
    key, next_i = update.inline_query.offset.split('|')
    next_i = int(next_i)
    from_id = update.inline_query.from_user.id
    query = update.inline_query.query

    data = ongoing[key](next_i)
    offset = (key + '|' + str(next_i + 1)) if data[1][0] + ((next_i - 1) * MAX_INLINE_RESULTS) < data[1][1] else ''
    answer(bot, update, data[0], offset=offset)

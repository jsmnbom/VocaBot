import abc
import base64
import logging
import math
import re
from functools import wraps
from uuid import uuid4

from telegram import ParseMode, Emoji, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardHide, ForceReply, \
    ReplyKeyboardMarkup, KeyboardButton, InlineQueryResultArticle, InputTextMessageContent

from constants import PV_SERVICES, START_TEXT, HELP_TEXT, INLINE_HELP_TEXT, OWNER_ID, ABOUT_TEXT, SETTINGS_TEXT
from db import db, VOCA_LANGS, LANGS
from inter import underscore as _
from voca_db import voca_db

logger = logging.getLogger(__name__)


def with_voca_lang(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        return method(self, *args, **kwargs)

    return wrapper


def partition(l):
    if len(l) % 3 == 0:
        return [l[i:i + 3] for i in range(0, len(l), 3)]
    elif len(l) % 2 == 0:
        return [l[i:i + 2] for i in range(0, len(l), 2)]
    else:
        return [l[i:i + 3] for i in range(0, len(l), 3)]


class BaseHandler(object):
    def __init__(self, bot, update):
        self.id = 0
        self.chat_id = 0
        self.msg_id = 0
        self.bot = bot
        self.update = update
        self.voca_lang = None
        self.songs = []
        self.artists = []
        self.total = 0
        self.offset = 0
        self.inline = False
        self.inline_id = 0
        self.text = None

    def process(self):
        with _.using(db.get_lang(self.id)):
            self._process()

    @abc.abstractmethod
    def _process(self):
        """Process the incoming update."""

    @with_voca_lang
    def get_songs(self, *args, **kwargs):
        self.songs, self.total = voca_db.songs(*args, lang=self.voca_lang, **kwargs)

    @with_voca_lang
    def get_song(self, *args, **kwargs):
        return voca_db.song(*args, lang=self.voca_lang, **kwargs)

    @with_voca_lang
    def get_artists(self, *args, **kwargs):
        self.artists, self.total = voca_db.artists(*args, lang=self.voca_lang, **kwargs)

    @with_voca_lang
    def get_artist(self, *args, **kwargs):
        return voca_db.artist(*args, lang=self.voca_lang, **kwargs)

    @with_voca_lang
    def get_derived(self, *args, **kwargs):
        self.songs, self.total = voca_db.derived(*args, lang=self.voca_lang, **kwargs)

    def send_message(self, text=None, **kwargs):
        return self.bot.sendMessage(chat_id=self.id, text=text, parse_mode=ParseMode.HTML, **kwargs)

    def edit_message(self, text, reply_markup=None):
        try:

            if self.inline:
                return self.bot.editMessageText(inline_message_id=self.inline_id,
                                                text=text,
                                                reply_markup=reply_markup,
                                                parse_mode=ParseMode.HTML)
            else:
                return self.bot.editMessageText(chat_id=self.chat_id,
                                                message_id=self.msg_id,
                                                text=text,
                                                reply_markup=reply_markup,
                                                parse_mode=ParseMode.HTML)

        except AttributeError:  # Sometimes it derps
            pass

    def send_audio(self, title, performer, audio):
        # bot.sendMessage(chat_id=chat_id, text="{}\n{}\n{}".format(title, performer, audio))
        logger.debug(self.bot.sendAudio(audio=audio, chat_id=self.id, title=title, performer=performer))

    @staticmethod
    def base_content_song(song):
        # noinspection SpellCheckingInspection
        return _('<b>{name}</b>\n{artist}\n{type} song with {num} favourites.').format(name=song['name'],
                                                                                       artist=song['artistString'],
                                                                                       type=song['songType'],
                                                                                       num=song['favoritedTimes'])

    @staticmethod
    def base_content_artist(artist):
        return _('<b>{artist_name}</b>\n{type}').format(artist_name=artist['name'], type=artist['artistType'])

    @staticmethod
    def names_text(song):
        if len(song['names']) > 1:
            names = _('<b>Additional names:</b>\n')
            for name in song['names']:
                if name['value'] != song['name']:
                    names += name['value'] + '\n'
            return names

        return _('No additional names found.\n')

    def artists_text(self, song):
        if len(song['artists']) > 0:
            artists = _('<b>Artists:</b>\n')
            for artist in song['artists']:
                roles = []
                for role in artist['effectiveRoles'].split(', '):
                    if role == 'Default':
                        roles.append(artist['categories'][:1])
                    else:
                        roles.append(role[:1])

                artists += _('[<code>{roles}</code>] '
                             '{artist_name}').format(roles=','.join(roles), artist_name=artist['name'])

                if not self.inline:
                    try:
                        artists += ' /a_{}'.format(artist['artist']['id'])
                    except KeyError:
                        pass

                artists += '\n'

            return artists

        return _('No artists found.\n')

    # noinspection PyTypeChecker
    def keyboard(self, thing, artist=False):
        keyboard = [[]]
        if artist:
            share = (_('Share artist'), '##a#{}')
            if self.inline:
                keyboard[-1].append(
                    InlineKeyboardButton(text=Emoji.TOP_WITH_UPWARDS_ARROW_ABOVE + _('Share popular songs'),
                                         switch_inline_query='##ap#{}'.format(thing['id'])))
                keyboard[-1].append(InlineKeyboardButton(text=Emoji.CLOCK_FACE_THREE_OCLOCK + _('Share latest songs'),
                                                         switch_inline_query='##al#{}'.format(thing['id'])))
            else:
                keyboard[-1].append(InlineKeyboardButton(text=Emoji.TOP_WITH_UPWARDS_ARROW_ABOVE + _('Popular songs'),
                                                         callback_data='alist|p|{}'.format(thing['id'])))
                keyboard[-1].append(InlineKeyboardButton(text=Emoji.CLOCK_FACE_THREE_OCLOCK + _('Latest songs'),
                                                         callback_data='alist|l|{}'.format(thing['id'])))
        else:
            share = (_('Share song'), '##{}')

            keyboard[-1].append(InlineKeyboardButton(text=Emoji.SCROLL + _('Lyrics'),
                                                     callback_data='ly|{}'.format(thing['id'])))
            if self.inline:
                keyboard[-1].append(InlineKeyboardButton(text=Emoji.MICROPHONE + _('Artist info'),
                                                         callback_data='ainfo|{}'.format(thing['id'])))

            if not thing['pvServices'] == 'Nothing':
                keyboard.append([])
                for service in PV_SERVICES:
                    if service in thing['pvServices']:
                        data = 'pv|{}|{}'.format(service, thing['id'])
                        keyboard[-1].append(InlineKeyboardButton(text=Emoji.MOVIE_CAMERA + service,
                                                                 callback_data=data))

        keyboard.append([])
        keyboard[-1].append(InlineKeyboardButton(text=share[0], switch_inline_query=share[1].format(thing['id'])))

        return InlineKeyboardMarkup(keyboard)

    # noinspection PyTypeChecker
    def content(self, info=False, artist=False, err='search', things=None, pagination=True):
        text = ''
        status = 0
        if not things:
            if artist:
                things = self.artists
            else:
                things = self.songs

        if len(things) > 0:
            for thing in things:
                text += '\n\n'

                if artist:
                    text += '{} {}'.format(Emoji.MICROPHONE, self.base_content_artist(thing))
                else:
                    text += '{} {}'.format(Emoji.MUSICAL_NOTE, self.base_content_song(thing))

                if info:
                    text += '\n\n'
                    text += self.names_text(thing)
                    text += '\n'
                    if artist:
                        if not self.inline:
                            if 'baseVoicebank' in thing:
                                text += _('<b>Base voicebank:</b>') + ' /a_{}\n\n'.format(thing['baseVoicebank']['id'])
                    else:
                        if not self.inline:
                            text += _('<b>Derived songs:</b>') + ' /dev_{}\n'.format(thing['id'])
                            text += '\n'
                            text += self.artists_text(thing)

                            if 'originalVersionId' in thing:
                                text += '\n'
                                text += _('<b>Original song:</b>') + ' /info_{}\n'.format(thing['originalVersionId'])

                        if thing['pvServices'] == 'Nothing':
                            text += _('\nNo promotional videos found')

                else:
                    if not self.inline:
                        if artist:
                            text += _('\nInfo: ') + ' /a_{}'.format(thing['id'])
                        else:
                            text += _('\nInfo and lyrics:') + ' /info_{}'.format(thing['id'])
        else:
            if err == 'search':
                text = _("I couldn't find what you were looking for. Did you misspell it?")
            elif err == 'derived':
                text = _("No derived songs found.")
            status = -1

        if info:
            return text, status, self.keyboard(things[0], artist)
        else:
            return text, status, None

    def paged(self, operation, edit=False, extra=None):
        if operation == 'search':
            self.get_songs(self.text, max_results=3, offset=self.offset)
        elif operation == 'artist':
            self.get_artists(self.text, max_results=3, offset=self.offset)
        elif operation == 'top':
            self.get_songs('', max_results=3, offset=self.offset)
        elif operation == 'new':
            self.get_songs('', max_results=3, offset=self.offset, sort='AdditionDate')
        elif operation == 'artist_RatingScore':
            self.get_songs('', artist_id=self.text, max_results=3, offset=self.offset, sort='RatingScore')
        elif operation == 'artist_PublishDate':
            self.get_songs('', artist_id=self.text, max_results=3, offset=self.offset, sort='PublishDate')
        elif operation == 'derived':
            self.get_derived(song_id=self.text, max_results=3, offset=self.offset)

        # We might have to use floor and then +1 here.. not sure
        page = math.ceil(self.offset / 3)
        base_data = 'paged|{}|{}|{}'.format(operation, '{}', extra)
        # And then simply floor here.
        last_page = math.ceil(self.total / 3) - 1
        keyboard = [InlineKeyboardButton('⪡ 1',
                                         callback_data=base_data.format(0) if page > 0 else 'paged'),
                    InlineKeyboardButton('< {}'.format(page if page > 0 else 1),
                                         callback_data=base_data.format((page - 1)) if page > 0 else 'paged'),
                    InlineKeyboardButton('•{}•'.format(page + 1),
                                         callback_data='paged'),
                    InlineKeyboardButton('{} >'.format(page + 2),
                                         callback_data=base_data.format(page + 1) if page < last_page else 'paged'),
                    InlineKeyboardButton('{} ⪢'.format(last_page + 1),
                                         callback_data=base_data.format(last_page) if page < last_page else 'paged')]
        keyboard = InlineKeyboardMarkup([keyboard])

        if operation == 'artist':
            content = self.content(artist=True)[0]
        else:
            content = self.content(err=operation)[0]

        if edit:
            msg = self.edit_message(text=content, reply_markup=keyboard)
        else:
            msg = self.send_message(text=content, reply_markup=keyboard)

        return str(msg.chat_id) + '|' + str(msg.message_id)


class MessageHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.message.chat_id
        self.chat_id = update.message.chat_id
        self.text = update.message.text
        self.from_id = update.message.from_user.id
        self.type = update.message.chat.type

        if update.message.chat.title != '':
            self.name = update.message.chat.title
        else:
            self.name = update.message.chat.first_name

        super().process()

    def _process(self):
        # Strip '/' and split on '@' and ' '
        cmd = self.text.lower()[1:].split('@')[0].split(' ')[0]
        # call self.cmd_THE_CMD_THEY_WANT
        try:
            cmd = getattr(self, 'cmd_' + cmd)
            cmd()
        except AttributeError:
            # Okay so not a command. perhaps we were already interacting with the user?
            state = db.get_state(self.id)
            if state:
                self.step(state)

            self.other()

    def step(self, state):
        if state[0].startswith('set_') and state[0].endswith('_lang'):
            if state[0] == 'set_lang':
                if self.text in LANGS:
                    if self.type == 'private':
                        db.set_lang(self.from_id, self.text)
                    else:
                        db.set_lang(self.id, self.text)
                else:
                    self.send_message(text=_("Language not found. Try again."))
                    return

            elif state[0] == 'set_voca_lang':
                if self.text in VOCA_LANGS:
                    if self.type == 'private':
                        db.set_voca_lang(self.from_id, self.text)
                    else:
                        db.set_voca_lang(self.id, self.text)
                else:
                    self.send_message(text=_("Language not found. Try again."))
                    return
            else:
                self.unknown_cmd()

            self.send_message(text=_("{type} language set to {lang}").format(
                type=_('User') if self.type == 'private' else _('Chat'),
                lang=self.text),
                reply_markup=ReplyKeyboardHide())
            db.remove_state(self.id)

        if (state[0] == 'search' or state[0] == 'artist') and not self.text.startswith('/'):
            msg_id = self.paged(state[0])

            db.update_state(msg_id, state[0], base64.b64encode(self.text.encode('utf-8')))
            db.remove_state(self.id)

    def other(self):
        search = re.search(r'.*/.*_(\d+)', self.text)
        if search:
            search_id = search.group(1)

            if self.text.startswith('/info_'):
                self.songs = [self.get_song(search_id, fields='Names, Lyrics, Artists')]
                content = self.content(info=True)
                self.send_message(text=content[0], reply_markup=content[2])

            elif self.text.startswith('/ly_'):
                song = self.get_song(search_id, fields='Names, Lyrics, Artists')
                reply_keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(lyric['language'],
                                           callback_data='ly_{}_{}'.format(song['id'], lyric)['language']) for
                      lyric in song['lyrics']]])
                self.send_message(text=_("What language would you like the lyrics "
                                         "for {name} by {artist} in?").format(name=song['name'],
                                                                              artist=song['artistString']),
                                  reply_markup=reply_keyboard)

            elif self.text.startswith('/a_'):
                self.artists = [self.get_artist(search_id, fields='Names')]
                content = self.content(info=True, artist=True)
                self.send_message(text=content[0], reply_markup=content[2])

            elif self.text.startswith('/dev_'):
                self.text = search_id
                msg_id = self.paged('derived')

                db.update_state(msg_id, 'derived',
                                base64.b64encode(search_id.encode('utf-8')))
            else:
                self.unknown_cmd()
        else:
            if self.text.startswith('/'):
                # It didn't match any cmd_ and nothing here either, so it must be something wrong.
                self.unknown_cmd()

    def unknown_cmd(self):
        self.send_message(text=_("Command not recognized. Did you misspell it?"))

    def cmd_start(self):
        bot_name = self.bot.first_name + ' ' + self.bot.last_name
        if self.text == '/start help_inline':
            self.cmd_help_inline()
        else:
            self.send_message(text=START_TEXT.format(user_name=self.name, bot_name=bot_name),
                              disable_web_page_preview=True)

    def cmd_help(self):
        self.send_message(text=HELP_TEXT.format(bot_name=self.bot.name), disable_web_page_preview=True)

    def cmd_help_inline(self):
        bot_name = self.bot.first_name + ' ' + self.bot.last_name
        self.send_message(text=INLINE_HELP_TEXT.format(bot_user_name=self.bot.name,
                                                       bot_name=bot_name, user_name=self.name),
                          disable_web_page_preview=True)

    def cmd_about(self):
        # noinspection SpellCheckingInspection
        self.send_message(ABOUT_TEXT.format(bot_name=self.bot.name), disable_web_page_preview=True)

    def cmd_kill(self):
        logger.debug("Got /kill from %s" % self.update.message.from_user.id)
        if self.update.message.from_user.id == OWNER_ID:
            # noinspection SpellCheckingInspection
            self.send_message(text=_("NOOOOO!!!"))
            logger.debug("Sending SIGTERM to self.")
            import signal
            import os
            import time
            time.sleep(2)
            db.close()
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            self.send_message(text=_("You are not authorised to do that."))

    def cmd_cancel(self):
        state = db.get_state(self.id)
        db.remove_state(self.id)
        if state:
            self.send_message(text=_("Operation cancelled."), reply_markup=ReplyKeyboardHide())
        else:
            self.send_message(text=_("I am currently idle."), reply_markup=ReplyKeyboardHide())

    def cmd_top(self):
        self.paged('top')

    def cmd_new(self):
        self.paged('new')

    def cmd_search(self):
        query = ' '.join(self.text.split(' ')[1:])

        if query != '':
            self.text = query

            msg_id = self.paged('search')

            db.update_state(msg_id, 'search', base64.b64encode(query.encode('utf-8')))
        else:
            db.update_state(self.id, 'search', '')
            self.send_message(text=_("What would you like to search for?"),
                              reply_markup=ForceReply())

    def cmd_artist(self):
        query = ' '.join(self.text.split(' ')[1:])

        if query != '':
            self.text = query

            msg_id = self.paged('artist')

            db.update_state(msg_id, 'artist', base64.b64encode(query.encode('utf-8')))
        else:
            db.update_state(self.id, 'artist', '')
            self.send_message(text=_("What would you like to search for?"),
                              reply_markup=ForceReply())

    def cmd_set_voca_lang(self):
        db.update_state(self.id, 'set_voca_lang')
        reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton(lang) for lang in VOCA_LANGS]],
                                             resize_keyboard=True)
        self.send_message(text=_("What language would you like titles and artist names to be written in?"),
                          reply_markup=reply_keyboard)

    def cmd_set_lang(self):
        db.update_state(self.id, 'set_lang')
        reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton(lang) for lang in LANGS]],
                                             resize_keyboard=True)
        self.send_message(text=_("What language or personality module would you like?"),
                          reply_markup=reply_keyboard)

    def cmd_settings(self):
        if self.type == 'private':
            lang = db.get_lang(self.from_id)
            voca_lang = db.get_voca_lang(self.from_id)
        else:
            lang = db.get_lang(self.id)
            voca_lang = db.get_voca_lang(self.id)
        self.send_message(text=SETTINGS_TEXT.format(bot_name=self.bot.name, lang=lang, voca_lang=voca_lang,
                                                    type=_('User') if self.type == 'private' else _('Chat')))


class InlineQueryHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.inline_query.from_user.id
        self.query = update.inline_query.query
        self.offset = update.inline_query.offset
        self.inline = True

        super().process()

    def _process(self):
        results = []

        if self.query.startswith('##a#'):
            self.artists = [self.get_artist(artist_id=self.query[4:], fields='MainPicture, Names')]
        elif self.query.startswith('##ap#'):
            self.get_songs('', artist_id=self.query[5:], offset=self.offset, max_results=20, sort='RatingScore')
        elif self.query.startswith('##al#'):
            self.get_songs('', artist_id=self.query[5:], offset=self.offset, max_results=20, sort='PublishDate')
        elif self.query.startswith('##'):
            self.songs = [self.get_song(song_id=self.query[2:], fields='MainPicture, Names, Artists')]
        else:
            self.get_songs(self.query, offset=self.offset, max_results=20)
            self.get_artists(self.query, max_results=1)

        if len(self.songs) < 1 and not self.artists:
            self.bot.answerInlineQuery(self.update.inline_query.id, results=[],
                                       switch_pm_text='Nothing found. Click for help.',
                                       switch_pm_parameter='help_inline')
            return

        if self.artists:
            artist = self.artists[0]
            try:
                thumb = artist['mainPicture']['urlThumb']
            except KeyError:
                thumb = ''

            content = self.content(things=[artist], artist=True, info=True, pagination=False)
            # noinspection SpellCheckingInspection
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=Emoji.MICROPHONE + ' ' + artist['name'],
                description=_('{artist_type}').format(artist_type=artist['artistType']),
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(content[0],
                                                              parse_mode=ParseMode.HTML),
                reply_markup=content[2]
            ))

        for song in self.songs:
            try:
                thumb = song['mainPicture']['urlThumb']
            except KeyError:
                thumb = ''

            content = self.content(things=[song], info=True, pagination=False)
            # noinspection SpellCheckingInspection
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=Emoji.MUSICAL_NOTE + ' ' + song['name'],
                description=_('{artist}\n{song_type} with {num} favourites.').format(artist=song['artistString'],
                                                                                     song_type=song['songType'],
                                                                                     num=song['favoritedTimes']),
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(content[0],
                                                              parse_mode=ParseMode.HTML),
                reply_markup=content[2]
            ))

        if len(self.songs) < 20 or self.offset == '':
            next_offset = ''
        else:
            next_offset = int(self.offset) + len(self.songs)

        self.bot.answerInlineQuery(self.update.inline_query.id,
                                   results=results,
                                   cache_time=30,
                                   is_personal=True,
                                   next_offset=next_offset,
                                   switch_pm_text='Click for help.',
                                   switch_pm_parameter='help_inline')


class ChosenInlineResultHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.chosen_inline_result.from_user.id

        # TODO: Do statistics of chosen inline results?

        super().process()

    def _process(self):
        pass


class CallbackQueryHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.callback_query.from_user.id
        self.inline_id = update.callback_query.inline_message_id
        self.query_id = update.callback_query.id
        self.data = update.callback_query.data.split('|')
        if update.callback_query.message:
            self.msg_id = update.callback_query.message.message_id
            self.chat_id = update.callback_query.message.chat_id
        else:
            self.inline = True

        super().process()

    def _process(self):
        if self.data[0] == 'paged':
            if len(self.data) == 1:
                self.bot.answerCallbackQuery(self.query_id, text="")
                return
            extra = None
            state = db.get_state(str(self.chat_id) + '|' + str(self.msg_id))
            if state:
                db.remove_state(str(self.chat_id) + '|' + str(self.msg_id))
                self.text = base64.b64decode(state[1]).decode('utf-8')
            elif self.data[2]:
                self.text = self.data[3]
                extra = self.data[3]
            self.offset = int(self.data[2]) * 3
            self.paged(self.data[1], edit=True, extra=extra)
            self.bot.answerCallbackQuery(self.query_id, text="")
        elif self.data[0] == 'ly':
            self.lyrics()
        elif self.data[0] == 'ly2':
            self.lyrics2()
        elif self.data[0] == 'pv':
            self.pv()
        elif self.data[0] == 'alist':
            self.alist()
        elif self.data[0] == 'ainfo':
            self.ainfo()
        elif self.data[0] == 's':
            self.song()
        elif self.data[0] == 'a':
            self.artist()
        else:
            self.bot.answerCallbackQuery(self.query_id, text=_("Feature not supported."), show_alert=True)

    def lyrics(self):
        song = self.get_song(self.data[1], 'Names, Lyrics, Artists')
        if len(song['lyrics']) < 1:
            self.bot.answerCallbackQuery(self.query_id, text=_("No lyrics found."))
        else:
            lang_buttons = [InlineKeyboardButton(lyrics['language'],
                                                 callback_data='ly2|{}|{}'.format(lyrics['language'],
                                                                                  song['id']))
                            for lyrics in song['lyrics']]

            if self.inline:
                if self.edit_message(
                        text=_('{base}\n\nWhat language would you like the lyrics in?').format(
                            base=self.base_content_song(song)),
                        reply_markup=InlineKeyboardMarkup([lang_buttons])):
                    self.bot.answerCallbackQuery(self.query_id, text="")
                else:
                    self.bot.answerCallbackQuery(self.query_id, text="Failed...")
            else:
                if self.send_message(text=_('What language would you like the lyrics '
                                            'for {song} by {artist} in?').format(song=song['name'],
                                                                                 artist=song['artistString']),
                                     reply_markup=InlineKeyboardMarkup([lang_buttons])):
                    self.bot.answerCallbackQuery(self.query_id, text="")
                else:
                    self.bot.answerCallbackQuery(self.query_id, text="Failed...")

    def lyrics2(self):
        song = self.get_song(self.data[2], 'Names, Lyrics, Artists')
        for lyric in song['lyrics']:
            if lyric['language'] == self.data[1]:
                if self.inline:
                    content = self.content(info=True, things=[song], pagination=False)
                    if self.edit_message(text=_('{base}{lang} lyrics:\n'
                                                '{lyrics}').format(base=content[0],
                                                                   lang=lyric['language'],
                                                                   lyrics=lyric['value']),
                                         reply_markup=content[2]):
                        self.bot.answerCallbackQuery(self.query_id, text="Success!")
                    else:
                        self.bot.answerCallbackQuery(self.query_id, text="Failed...")
                else:
                    if self.edit_message(text=_('<b>{lang} lyrics for {song} by {artist}:</b>\n'
                                                '{lyrics}').format(song=song['name'],
                                                                   artist=song['artistString'],
                                                                   lang=lyric['language'],
                                                                   lyrics=lyric['value'])):
                        self.bot.answerCallbackQuery(self.query_id, text="Success!")
                    else:
                        self.bot.answerCallbackQuery(self.query_id, text="Failed...")

    def pv(self):
        # TODO: If there's several from the same service... do something... about it...
        song = self.get_song(self.data[2], 'Names, Artists, PVs')
        for pv in song['pVs']:
            if pv['service'] == self.data[1]:
                if self.inline:
                    content = self.content(info=True, things=[song], pagination=False)
                    if self.edit_message(text=_('{base}{service} PV Title:\n{name}\n'
                                                '{url}').format(base=content[0],
                                                                service=pv['service'],
                                                                name=pv['name'],
                                                                url=pv['url']),
                                         reply_markup=content[2]):
                        self.bot.answerCallbackQuery(self.query_id, text=_("Success!"))
                    else:
                        self.bot.answerCallbackQuery(self.query_id, text="Failed...")
                else:
                    if self.send_message(text=_('<b>{service} PV for {song} by {artist}</b>\nPV Title:\n{name}\n'
                                                '{url}').format(song=song['name'],
                                                                artist=song['artistString'],
                                                                service=pv['service'],
                                                                name=pv['name'],
                                                                url=pv['url'])):
                        self.bot.answerCallbackQuery(self.query_id, text="Success!")
                    else:
                        self.bot.answerCallbackQuery(self.query_id, text="Failed...")
                return  # We only want the first match

    def alist(self):
        if self.data[1] == 'p':
            sort = 'RatingScore'
        else:
            sort = 'PublishDate'
        self.text = self.data[2]
        self.paged('artist_' + sort, extra=self.data[2])
        self.bot.answerCallbackQuery(self.query_id, text="")

    def ainfo(self):
        song = self.get_song(self.data[1], fields='Names, Lyrics, Artists')
        content = self.content(info=True, things=[song], pagination=False)

        artist_buttons = []
        for artist in song['artists']:
            try:
                artist_buttons.append(InlineKeyboardButton(text=artist['name'],
                                                           callback_data='a|{}|{}'.format(artist['artist']['id'],
                                                                                          song['id'])))
            except KeyError:
                pass
        artist_buttons = partition(artist_buttons)
        artist_buttons.append([InlineKeyboardButton(text=Emoji.BACK_WITH_LEFTWARDS_ARROW_ABOVE + _('Back'),
                                                    callback_data='s|{}'.format(self.data[1]))])

        self.edit_message(text=_('{base}{artist_text}\n'
                                 'Choose an artist.').format(base=content[0],
                                                             artist_text=self.artists_text(song)),
                          reply_markup=InlineKeyboardMarkup(artist_buttons))
        self.bot.answerCallbackQuery(self.query_id, text="")

    def song(self):
        song = self.get_song(song_id=self.data[1], fields='MainPicture, Names, Artists')
        content = self.content(things=[song], info=True, pagination=False)
        self.edit_message(text=content[0], reply_markup=content[2])
        self.bot.answerCallbackQuery(self.query_id, text="")

    def artist(self):
        artist = self.get_artist(artist_id=self.data[1], fields='MainPicture, Names')
        content = self.content(things=[artist], artist=True, info=True, pagination=False)
        content[2].inline_keyboard.append([InlineKeyboardButton(text=Emoji.BACK_WITH_LEFTWARDS_ARROW_ABOVE + _('Back'),
                                                                callback_data='ainfo|{}'.format(self.data[2]))])
        self.edit_message(text=content[0], reply_markup=content[2])
        self.bot.answerCallbackQuery(self.query_id, text="")

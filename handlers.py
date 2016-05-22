import abc
import base64
import logging
import math
import re
from functools import partial, wraps
from uuid import uuid4

from telegram import (ParseMode, Emoji, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle,
                      InputTextMessageContent, ReplyKeyboardHide, ReplyKeyboardMarkup, KeyboardButton, ForceReply,
                      ChatAction)

from constants import OWNER_ID, START_TEXT, HELP_TEXT, ABOUT_TEXT, PV_SERVICES, INLINE_HELP_TEXT
from db import db, VOCA_LANGS, LANGS
from dl import Downloader
from inter import underscore as _
from voca_db import voca_db


def with_voca_lang(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        return method(self, *args, **kwargs)

    return wrapper


class BaseHandler(object):
    def __init__(self, bot, update):
        self.id = 0
        self.bot = bot
        self.update = update
        self.voca_lang = None
        self.songs = []
        self.artists = []
        self.total = 0
        self.offset = 0
        self.inline = False
        self.inline_id = 0

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
        self.bot.sendMessage(chat_id=self.id, text=text, parse_mode=ParseMode.HTML, **kwargs)

    def edit_message(self, text, reply_markup):
        try:
            return self.bot.editMessageText(inline_message_id=self.inline_id,
                                            text=text,
                                            reply_markup=reply_markup,
                                            parse_mode=ParseMode.HTML)
        except AttributeError:  # Sometimes it derps
            pass

    def send_audio(self, title, performer, audio):
        # bot.sendMessage(chat_id=chat_id, text="{}\n{}\n{}".format(title, performer, audio))
        logging.debug(self.bot.sendAudio(audio=audio, chat_id=self.id, title=title, performer=performer))

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
            names = _('Additional names:\n')
            for name in song['names']:
                if name['value'] != song['name']:
                    names += name['value'] + '\n'
            return names

        return _('No additional names found.\n')

    def artists_text(self, song):
        if len(song['artists']) > 0:
            artists = _('Artists:\n')
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


class MessageHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.message.chat_id
        self.text = update.message.text
        self.from_id = update.message.from_user.id
        self.type = update.message.chat.type

        if update.message.chat.title != '':
            self.name = update.message.chat.title
        else:
            self.name = update.message.chat.first_name

        logging.debug(self.name)

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
            current = db.get_current(self.id)
            if current:
                self.operation_step(current)

            self.other()

    def operation_step(self, current):
        if current[0] == 'lyrics':
            db.remove_current(self.id)
            song_id = current[1]
            song = self.get_song(song_id, fields='Names, Lyrics, Artists')

            for lyric in song['lyrics']:
                if lyric['language'] == self.text:
                    self.send_message(text=_('<b>Lyrics for {name} by {artist}.</b>\n'
                                             '{lyrics}').format(name=song['name'],
                                                                artist=song['artistString'],
                                                                lyrics=lyric['value']),
                                      reply_markup=ReplyKeyboardHide())

        elif current[0].startswith('set_') and current[0].endswith('_lang'):
            if current[0] == 'set_lang':
                if self.text in LANGS:
                    if self.type == 'private':
                        db.set_lang(self.from_id, self.text)
                    else:
                        db.set_lang(self.id, self.text)
                else:
                    self.send_message(text=_("Language not found. Try again."))
                    return

            elif current[0] == 'set_voca_lang':
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
            db.remove_current(self.id)

        elif current[0] in ['search', 'top', 'new', 'artist', 'artist_RatingScore', 'artist_PublishDate', 'derived']:
            if self.text.startswith('/page'):
                self.paged(current)

        if (current[0] == 'search' or current[0] == 'artist') and not self.text.startswith('/'):
            content, status = None, -1
            if current[0] == 'search':
                self.get_songs(self.text, max_results=3, offset=self.offset)
                (content, status) = self.content()
            elif current[0] == 'artist':
                self.get_artists(self.text, max_results=3, offset=self.offset)
                (content, status) = self.content(artist=True)

            if status != -1:
                db.update_current(self.id, current[0], base64.b64encode(self.text.encode('utf-8')))
                self.send_message(text=content, reply_markup=ReplyKeyboardHide())
            else:
                if current[1] == '' and not self.text.startswith('/'):
                    self.send_message(text=content, reply_markup=ForceReply())

    def paged(self, current):
        search = re.search(r'/page_(\d*)@?', self.text)
        try:
            self.offset = (int(search.group(1)) - 1) * 3
            self.text = base64.b64decode(current[1]).decode('utf-8')
        except AttributeError:
            return

        if current[0] == 'top':
            self.get_songs('', max_results=3, offset=self.offset)
            self.send_message(text=self.content()[0], reply_markup=ReplyKeyboardHide())
        elif current[0] == 'new':
            self.get_songs('', max_results=3, offset=self.offset, sort='AdditionDate')
            self.send_message(text=self.content()[0], reply_markup=ReplyKeyboardHide())
        elif current[0] == 'artist_RatingScore':
            self.get_songs('', artist_id=self.text, max_results=3, offset=self.offset, sort='RatingScore')
            self.send_message(text=self.content()[0], reply_markup=ReplyKeyboardHide())
        elif current[0] == 'artist_PublishDate':
            self.get_songs('', artist_id=self.text, max_results=3, offset=self.offset, sort='PublishDate')
            self.send_message(text=self.content()[0], reply_markup=ReplyKeyboardHide())
        elif current[0] == 'derived':
            self.get_derived(song_id=self.text, max_results=3, offset=self.offset)
            self.send_message(text=self.content(err='derived')[0], reply_markup=ReplyKeyboardHide())
        else:
            self.send_message(text="I am not currently processing any pages.", reply_markup=ReplyKeyboardHide())

    def other(self):
        search = re.search(r'.*/.*_(\d+)', self.text)
        if search:
            search_id = search.group(1)
            if self.pv(search_id):
                return

            if self.text.startswith('/info_'):
                self.songs = [self.get_song(search_id, fields='Names, Lyrics, Artists')]
                self.send_message(text=self.content(info=True, pagination=False)[0])

            elif self.text.startswith('/ly_'):
                song = self.get_song(search_id, fields='Names, Lyrics, Artists')
                reply_keyboard = ReplyKeyboardMarkup(
                    [[KeyboardButton(lyric['language']) for lyric in song['lyrics']]],
                    resize_keyboard=True)
                db.update_current(self.id, 'lyrics', song['id'])
                self.send_message(text=_("What language would you like the lyrics "
                                         "for {name} by {artist} in?").format(name=song['name'],
                                                                              artist=song['artistString']),
                                  reply_markup=reply_keyboard)

            elif self.text.startswith('/a_'):
                logging.debug(search_id)
                if '_p' in self.text or '_l' in self.text:
                    if '_p' in self.text:
                        sort = 'RatingScore'
                    else:
                        sort = 'PublishDate'
                    self.get_songs('', artist_id=search_id, max_results=3, sort=sort)

                    db.update_current(self.id, 'artist_' + sort,
                                      base64.b64encode(search_id.encode('utf-8')))

                    self.send_message(text=self.content()[0])
                else:
                    self.artists = [self.get_artist(search_id, fields='Names')]
                    self.send_message(text=self.content(info=True, artist=True, pagination=False)[0])

            elif self.text.startswith('/dev_'):
                self.get_derived(song_id=search_id, max_results=3)

                db.update_current(self.id, 'derived',
                                  base64.b64encode(search_id.encode('utf-8')))

                self.send_message(text=self.content(err='derived')[0])
            else:
                self.unknown_cmd()
        else:
            if self.text.startswith('/'):
                # It didn't match any cmd_ and nothing here either, so it must be something wrong.
                self.unknown_cmd()

    def pv(self, search_id):
        for service in PV_SERVICES:
            if self.text.startswith('/{}_'.format(service)):
                song = self.get_song(search_id, fields='PVs')
                if song:
                    for pv in song['pVs']:
                        # TODO: Unify weather it sends audio or just a link.
                        if pv['service'] == service:
                            if service == 'SoundCloud':
                                self.bot.sendChatAction(chat_id=self.id, action=ChatAction.UPLOAD_AUDIO)
                                send_audio_partial = partial(self.send_audio, title=song['name'],
                                                             performer=song['artistString'])
                                dl = Downloader(callback=send_audio_partial)
                                dl.get_link(pv['url'])
                                return
                            else:
                                self.bot.sendChatAction(chat_id=self.id, action=ChatAction.TYPING)
                                # For returning PVs
                                self.send_message(text=_("<b>{name}</b>\n"
                                                         "{artists}\n{url}").format(name=song['name'],
                                                                                    artists=song['artistString'],
                                                                                    url=pv['url']))
                                return

    def content(self, info=False, artist=False, pagination=True, err='search'):
        text = ''
        status = 0
        if artist:
            things = self.artists
        else:
            things = self.songs

        if len(things) > 0:
            for thing in things:
                if artist:
                    text += '{} {}'.format(Emoji.MICROPHONE, self.base_content_artist(thing))
                else:
                    text += '{} {}'.format(Emoji.MUSICAL_NOTE, self.base_content_song(thing))

                if info:
                    text += '\n\n'
                    text += self.names_text(thing)
                    text += '\n'
                    if artist:
                        text += _('Popular songs:') + ' /a_{}_p\n'.format(thing['id'])
                        text += _('Latest songs:') + ' /a_{}_l'.format(thing['id'])
                    else:
                        text += self.artists_text(thing)
                        if len(thing['lyrics']) > 0:
                            text += _('\nLyrics:') + ' /ly_{}\n'.format(thing['id'])
                        else:
                            text += _('\nNo lyrics found.\n')

                        text += _('\nDerived songs:') + ' /dev_{}\n'.format(thing['id'])

                        if 'originalVersionId' in thing:
                            text += _('Original song:') + ' /info_{}\n'.format(thing['originalVersionId'])

                        if not thing['pvServices'] == 'Nothing':
                            text += _('\nPromotional videos:\n')
                            for service in PV_SERVICES:
                                if service in thing['pvServices']:
                                    text += '/{}_{}\n'.format(service, thing['id'])
                        else:
                            text += _('\nNo promotional videos found')

                else:
                    if artist:
                        text += _('\nInfo: ') + ' /a_{}'.format(thing['id'])
                    else:
                        text += _('\nInfo and lyrics:') + ' /info_{}'.format(thing['id'])

                text += '\n\n'

            if pagination:
                if self.total > 0:
                    text += _('Page:') + ' {}/{}\n'.format(math.ceil(self.offset / 3) + 1, math.ceil(self.total / 3))
                    if self.offset + 3 < self.total:
                        # As in 'next page'
                        text += _('Next:') + ' /page_{}\n\n'.format(math.ceil(self.offset / 3) + 2)
                    else:
                        text += _('End of results.\n\n')
        else:
            if err == 'search':
                text = _("I couldn't find what you were looking for. Did you misspell it?")
            elif err == 'derived':
                text = _("No derived songs found.")
            status = -1

        return text, status

    def unknown_cmd(self):
        self.send_message(text=_("Command not recognized. Did you misspell it?"))

    def cmd_start(self):
        bot_name = self.bot.first_name + ' ' + self.bot.last_name
        logging.debug(START_TEXT)
        if self.text == '/start help_inline':
            self.cmd_help_inline()
        else:
            self.send_message(text=START_TEXT.format(user_name=self.name, bot_name=bot_name),
                              disable_web_page_preview=True)

    def cmd_kill(self):
        logging.debug("Got /kill from %s" % self.update.message.from_user.id)
        if self.update.message.from_user.id == OWNER_ID:
            # noinspection SpellCheckingInspection
            self.send_message(text=_("NOOOOO!!!"))
            logging.debug("Sending SIGTERM to self.")
            import signal
            import os
            import time
            time.sleep(2)
            db.close()
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            self.send_message(text=_("You are not authorised to do that."))

    def cmd_cancel(self):
        current = db.get_current(self.id)
        if current:
            self.send_message(text=_("Operation cancelled."), reply_markup=ReplyKeyboardHide())
            db.remove_current(self.id)
        else:
            self.send_message(text=_("I am currently idle."), reply_markup=ReplyKeyboardHide())

    def cmd_help(self):
        self.send_message(text=HELP_TEXT.format(username=self.bot.name), disable_web_page_preview=True)

    def cmd_help_inline(self):
        self.send_message(text=INLINE_HELP_TEXT.format(self.bot.name), disable_web_page_preview=True)

    def cmd_about(self):
        # noinspection SpellCheckingInspection
        self.send_message(ABOUT_TEXT.format(bot_name=self.bot.name), disable_web_page_preview=True)

    def cmd_set_voca_lang(self):
        db.update_current(self.id, 'set_voca_lang')
        reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton(lang) for lang in VOCA_LANGS]],
                                             resize_keyboard=True)
        self.send_message(text=_("What language would you like titles and artist names to be written in?"),
                          reply_markup=reply_keyboard)

    def cmd_set_lang(self):
        db.update_current(self.id, 'set_lang')
        reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton(lang) for lang in LANGS]],
                                             resize_keyboard=True)
        self.send_message(text=_("What language or personality module would you like?"),
                          reply_markup=reply_keyboard)

    def cmd_search(self):
        query = ' '.join(self.text.split(' ')[1:])

        if query != '':
            self.get_songs(query, max_results=3)

            db.update_current(self.id, 'search', base64.b64encode(query.encode('utf-8')))

            self.send_message(text=self.content()[0])
        else:
            db.update_current(self.id, 'search', '')
            self.send_message(text=_("What would you like to search for?"),
                              reply_markup=ForceReply())

    def cmd_top(self):
        self.get_songs('', max_results=3, offset=0)
        db.update_current(self.id, 'top')
        self.send_message(text=self.content()[0])

    def cmd_new(self):
        self.get_songs('', max_results=3, offset=0, sort='AdditionDate')
        db.update_current(self.id, 'new')
        self.send_message(text=self.content()[0])

    def cmd_artist(self):
        query = ' '.join(self.text.split(' ')[1:])

        if query != '':
            self.get_artists(query, max_results=3)

            db.update_current(self.id, 'artist', base64.b64encode(query.encode('utf-8')))

            self.send_message(text=self.content(artist=True)[0])
        else:
            db.update_current(self.id, 'artist', '')
            self.send_message(text=_("What would you like to search for?"),
                              reply_markup=ForceReply())


class InlineBaseHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

    @abc.abstractmethod
    def _process(self):
        """Process the incoming update."""

    def keyboard(self, song, info=False):
        # TODO: Somehow make buttons the same width if there's 3 on each row.
        info_button = InlineKeyboardButton(_('More Info'), callback_data='info|{}'.format(song['id']))
        lyrics_button = InlineKeyboardButton(_('Lyrics'), callback_data='lyrics|{}'.format(song['id']))
        share_button = InlineKeyboardButton(_('Share'),
                                            switch_inline_query='##{song_id}'.format(username=self.bot.name,
                                                                                     song_id=song['id']))

        if info:
            first_row = [lyrics_button, share_button]
        else:
            first_row = [info_button, lyrics_button, share_button]

        pv_row = [InlineKeyboardButton('{}'.format(service), callback_data='pv|{}|{}'.format(service, song['id']))
                  for service in song['pvServices'].split(', ')]

        inline_keyboard = InlineKeyboardMarkup([first_row, pv_row])
        return inline_keyboard


class InlineQueryHandler(InlineBaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.inline_query.from_user.id
        self.query = update.inline_query.query
        self.offset = update.inline_query.offset

        super().process()

    def _process(self):
        results = []

        if self.query.startswith('##'):
            self.songs = [self.get_song(song_id=self.query[2:], fields='MainPicture')]
        else:
            self.get_songs(self.query, offset=self.offset, max_results=20)

        if len(self.songs) < 1:
            self.bot.answerInlineQuery(self.update.inline_query.id, results=[],
                                       switch_pm_text='Nothing found. Tap for help.',
                                       switch_pm_parameter='help_inline')
            return

        for song in self.songs:
            try:
                thumb = song['mainPicture']['urlThumb']
            except KeyError:
                thumb = ''

            # noinspection SpellCheckingInspection
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=song['name'],
                description=_('{artist}\n{song_type} with {num} favourites.').format(artist=song['artistString'],
                                                                                     song_type=song['songType'],
                                                                                     num=song['favoritedTimes']),
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(self.base_content_song(song), parse_mode=ParseMode.HTML),
                reply_markup=self.keyboard(song)
            ))

        if len(self.songs) < 20 or self.offset == '':
            next_offset = ''
        else:
            next_offset = int(self.offset) + len(self.songs)

        self.bot.answerInlineQuery(self.update.inline_query.id,
                                   results=results,
                                   cache_time=30,
                                   is_personal=True,
                                   next_offset=next_offset)


class ChosenInlineResultHandler(BaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.chosen_inline_result.from_user.id

        # TODO: Do statistics of chosen inline results?

        super().process()

    def _process(self):
        pass


class CallbackQueryHandler(InlineBaseHandler):
    def __init__(self, bot, update):
        super().__init__(bot, update)

        self.id = update.callback_query.from_user.id
        self.inline_id = update.callback_query.inline_message_id
        self.query_id = update.callback_query.id
        self.data = update.callback_query.data.split('|')

        super().process()

    def _process(self):
        if self.data[0] == 'info':
            self.info()
        elif self.data[0] == 'lyrics':
            self.lyrics()
        elif self.data[0] == 'lyrics2':
            self.lyrics2()
        elif self.data[0] == 'pv':
            self.pv()
        else:
            self.bot.answerCallbackQuery(self.query_id, text=_("Feature not supported."), show_alert=True)

    def info(self):
        song = self.get_song(self.data[-1], 'Names')
        names = self.names_text(song)
        if self.edit_message(
                text=_('{base}\n\n{names}').format(base=self.base_content_song(song), names=names),
                reply_markup=self.keyboard(song, info=True)):
            self.bot.answerCallbackQuery(self.query_id, text="Success!")

    def lyrics(self):
        song = self.get_song(self.data[-1], 'Lyrics')
        if len(song['lyrics']) < 1:
            self.bot.answerCallbackQuery(self.query_id, text=_("No lyrics found."))
        else:
            lang_buttons = [InlineKeyboardButton(lyrics['language'],
                                                 callback_data='lyrics2|{}|{}'.format(lyrics['language'],
                                                                                      song['id']))
                            for lyrics in song['lyrics']]

            self.edit_message(
                text=_('{base}\n\nWhat language would you like the lyrics in?').format(
                    base=self.base_content_song(song)),
                reply_markup=InlineKeyboardMarkup([lang_buttons]))

    def lyrics2(self):
        song = self.get_song(self.data[-1], 'Lyrics')
        for lyric in song['lyrics']:
            if lyric['language'] == self.data[1]:
                if self.edit_message(
                        text=_('{base}\n\n{lang} lyrics:\n{lyrics}').format(base=self.base_content_song(song),
                                                                            lang=lyric['language'],
                                                                            lyrics=lyric['value']),
                        reply_markup=self.keyboard(song)):
                    self.bot.answerCallbackQuery(self.query_id, text="Success!")

    def pv(self):
        song = self.get_song(self.data[-1], 'PVs')
        for pv in song['pVs']:
            if pv['service'] == self.data[1]:
                if self.edit_message(text=_('{base}\n\nPV Title: {name}\n'
                                            'Link: {url}').format(base=self.base_content_song(song),
                                                                  name=pv['name'],
                                                                  url=pv['url']),
                                     reply_markup=self.keyboard(song)):
                    self.bot.answerCallbackQuery(self.query_id, text=_("Success!"))

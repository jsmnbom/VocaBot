import base64
import logging
import math
import re
from functools import partial
from uuid import uuid4

from telegram import (ParseMode, Emoji, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle,
                      InputTextMessageContent, ReplyKeyboardHide, ReplyKeyboardMarkup, KeyboardButton, ForceReply,
                      ChatAction)

from constants import OWNER_ID, pvServices
from db import db, VOCA_LANG, LANGS
from dl import Downloader
from inter import underscore as _
from voca_db import voca_db


# noinspection PyMethodMayBeStatic
class Handler(object):
    def __init__(self, bot, update):
        self.id = 0
        self.bot = bot
        self.update = update
        self.lang = None
        self.voca_lang = None
        self.songs = []
        self.artists = []
        self.total = 0
        self.offset = 0

        if update.message:
            self.id = update.message.chat_id
            self.text = update.message.text
            if hasattr(update.message.chat, 'title'):
                self.name = update.message.chat.title
            else:
                self.name = update.message.chat.first_name
            self.from_id = update.message.from_user.id
            self.type = update.message.chat.type
        elif update.inline_query:
            self.id = update.inline_query.from_user.id
            self.query = update.inline_query.query
            self.offset = update.inline_query.offset
        elif update.chosen_inline_result:
            self.id = update.chosen_inline_result.from_user.id
        elif update.callback_query:
            self.id = update.callback_query.from_user.id
            self.inline_id = update.callback_query.inline_message_id
            self.query_id = update.callback_query.id
            self.data = update.callback_query.data.split('|')
        else:
            logging.debug('Got weird request!')
            return

        with _.using(db.get_lang(self.id)):
            if self.update.message:
                self.message()
            elif self.update.inline_query:
                self.inline_query()
            elif self.update.chosen_inline_result:
                self.chosen_inline_result()
            elif self.update.callback_query:
                self.callback_query()

    def message(self):
        # Strip '/' and split on '@' and ' '
        cmd = self.text.lower()[1:].split('@')[0].split(' ')[0]
        # call self.cmd_THE_CMD_THEY_WANT
        try:
            cmd = getattr(self, 'cmd_' + cmd)
            cmd()
        except AttributeError:
            current = db.get_current(self.id)
            if current:
                self.operation_step(current)
            self.cmd_other()

    def inline_query(self):
        results = []

        self.get_songs(self.query, offset=self.offset)

        for song in self.songs:
            try:
                thumb = song['mainPicture']['urlThumb'] or ''
            except KeyError:
                thumb = ''

            # noinspection SpellCheckingInspection
            results.append(InlineQueryResultArticle(
                id=uuid4(),
                title=song['name'],
                description=song['artistString'] + '\n' + song['songType'],
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(self.base_content(song), parse_mode=ParseMode.HTML),
                reply_markup=self.inline_keyboard(song)
            ))

        if len(self.songs) < 10 or self.offset == '':
            next_offset = ''
        else:
            next_offset = int(self.offset) + len(self.songs)

        self.bot.answerInlineQuery(self.update.inline_query.id,
                                   results=results,
                                   cache_time=10,
                                   is_personal=True,
                                   next_offset=next_offset)

    def chosen_inline_result(self):
        pass

    def callback_query(self):
        if self.data[0] == 'info':
            song = self.get_song(self.data[-1], 'Names')
            names = self.additional_names(song)
            if self.edit_message(
                    text=_('{base}\n\n{names}').format(base=self.base_content(song), names=names),
                    reply_markup=self.inline_keyboard(song)):
                self.bot.answerCallbackQuery(self.query_id, text="Success!")
        elif self.data[0] == 'lyrics':
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
                        base=self.base_content(song)),
                    reply_markup=InlineKeyboardMarkup([lang_buttons]))
        elif self.data[0] == 'lyrics2':
            song = self.get_song(self.data[-1], 'Lyrics')
            for lyric in song['lyrics']:
                if lyric['language'] == self.data[1]:
                    if self.edit_message(
                            text=_('{base}\n\n{lang} lyrics:\n{lyrics}').format(base=self.base_content(song),
                                                                                lang=lyric['language'],
                                                                                lyrics=lyric['value']),
                            reply_markup=self.inline_keyboard(song)):
                        self.bot.answerCallbackQuery(self.query_id, text="Success!")
        elif self.data[0] == 'pv':
            song = self.get_song(self.data[-1], 'PVs')
            for pv in song['pVs']:
                if pv['service'] == self.data[1]:
                    if self.edit_message(text=_('{base}\n\nPV Title: {name}\n'
                                                'Link: {url}').format(base=self.base_content(song),
                                                                      name=pv['name'],
                                                                      url=pv['url']),
                                         reply_markup=self.inline_keyboard(song)):
                        self.bot.answerCallbackQuery(self.query_id, text=_("Success!"))
        else:
            self.bot.answerCallbackQuery(self.query_id, text=_("Feature not supported."), show_alert=True)

    def get_songs(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        self.songs, self.total = voca_db.songs(*args, lang=self.voca_lang, **kwargs)

    def get_song(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        return voca_db.song(*args, lang=self.voca_lang, **kwargs)

    def get_artists(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        self.artists, self.total = voca_db.artists(*args, lang=self.voca_lang, **kwargs)

    def get_artist(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        return voca_db.artist(*args, lang=self.voca_lang, **kwargs)

    def get_derived(self, *args, **kwargs):
        if self.voca_lang is None:
            self.voca_lang = db.get_voca_lang(self.id)
        self.songs, self.total = voca_db.derived(*args, lang=self.voca_lang, **kwargs)

    def send_message(self, text=None, **kwargs):
        self.bot.sendMessage(chat_id=self.id, text=text, parse_mode=ParseMode.HTML, **kwargs)

    def edit_message(self, text, reply_markup):
        try:
            return self.bot.editMessageText(inline_message_id=self.inline_id, text=text,
                                            reply_markup=reply_markup,
                                            parse_mode=ParseMode.HTML)
        except AttributeError:
            pass

    def send_audio(self, title, performer, audio):
        # bot.sendMessage(chat_id=chat_id, text="{}\n{}\n{}".format(title, performer, audio))
        logging.debug(self.bot.sendAudio(audio=audio, chat_id=self.id, title=title, performer=performer))

    def additional_names(self, song):
        if len(song['names']) > 1:
            names = _('Additional names:\n')
            for name in song['names']:
                if name['value'] != song['name']:
                    names += name['value'] + '\n'
            return names
        return _('No additional names found.\n')

    def artists_text(self, song, inline=False):
        if len(song['artists']) > 0:
            artists = _('Artists:\n')
            for artist in song['artists']:
                roles = ''
                for role in artist['effectiveRoles'].split(', '):
                    if role == 'Default':
                        roles += artist['categories'][:1]
                    else:
                        roles += role[:1] + ','
                if roles[-1:] == ',':
                    roles = roles[:-1]
                if inline:
                    # Inline
                    artists += _('[<code>{roles}</code>] {artist_name}\n').format(roles=roles,
                                                                                  artist_name=artist['name'])
                else:
                    # Not inline (has commands appended)
                    artists += _('[<code>{roles}</code>] {artist_name}').format(roles=roles,
                                                                                artist_name=artist['name'])
                    artists += ' /a_{}\n'.format(artist['artist']['id'])

            return artists
        return _('No artists found.\n')

    # noinspection SpellCheckingInspection
    def base_content(self, song):
        return _('<b>{name}</b>\n{artist}\n{type} song with {num} favourites.').format(name=song['name'],
                                                                                       artist=song['artistString'],
                                                                                       type=song['songType'],
                                                                                       num=song['favoritedTimes'])

    # noinspection SpellCheckingInspection
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
                    text += '{} {}'.format(Emoji.MICROPHONE, self.artist_base_content(thing))
                else:
                    text += '{} {}'.format(Emoji.MUSICAL_NOTE, self.base_content(thing))

                if info:
                    text += '\n\n'
                    text += self.additional_names(thing)
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
                            for service in pvServices:
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

    def artist_base_content(self, artist):
        return _('<b>{artist_name}</b>\n{type}').format(artist_name=artist['name'], type=artist['artistType'])

    def inline_keyboard(self, song):
        pv_buttons = [InlineKeyboardButton('{}'.format(service), callback_data='pv|{}|{}'.format(service, song['id']))
                      for service in song['pvServices'].split(', ')]

        first_button = InlineKeyboardButton(_('More Info'), callback_data='info|{}'.format(song['id']))

        inline_keyboard = InlineKeyboardMarkup([
            [first_button,
             InlineKeyboardButton(_('Lyrics'), callback_data='lyrics|{}'.format(song['id']))],
            pv_buttons
        ])
        return inline_keyboard

    def cmd_start(self):
        bot_name = self.bot.first_name + ' ' + self.bot.last_name
        self.send_message(text=_("Hello {user_name}! I'm {bot_name}. "
                                 "I use VocaDB.net to find all your favourite Vocaloid songs and artists. "
                                 "Write /help to see a list of commands.").format(user_name=self.name,
                                                                                  bot_name=bot_name))

    def cmd_kill(self):
        logging.debug("Got /kill from %s" % self.update.message.from_user.id)
        if self.update.message.from_user.id == OWNER_ID:
            # noinspection SpellCheckingInspection
            self.send_message(text=_("NOOOOO!!!"))
            logging.debug("Sending SIGINT to self.")
            import signal
            import os
            import time
            time.sleep(2)
            db.close()
            os.kill(os.getpid(), signal.SIGINT)
        else:
            self.send_message(text=_("You are not authorised to do that."))

    def cmd_cancel(self):
        current = db.get_current(self.id)
        if current:
            # The weird list comprehension is just getting key based on value in dict
            self.send_message(text=_("Operation cancelled."),
                              reply_markup=ReplyKeyboardHide())
            db.remove_current(self.id)
        else:
            self.send_message(text=_("I am currently idle."), reply_markup=ReplyKeyboardHide())

    def cmd_help(self):
        self.send_message(text=_("""/search - search for a vocaloid song in Romaji, English or Japanese
/artist - search for an artist
/top - browse the most popular vocaloid songs
/new - browse the newest additions to my database
/set_lang - set the general language, or change my personality module
/set_voca_lang - change what language titles and artists are displayed in
/cancel - cancel current operation
/about - display information about my creators and VocaDB
/help - display this message

You can also use my inline version outside of group chats by using {username}""").format(username=self.bot.name))

    def cmd_about(self):
        # noinspection SpellCheckingInspection
        self.send_message(_("Created by @bomjacob.\nI use data from VocaDB.net. "
                            "Click <a href=\"http://wiki.vocadb.net/wiki/29/license\">here</a> "
                            "for licensing information.\n"
                            "Dialogue and profile picture by @Awthornecay\n"
                            "My code is open-source and available at "
                            "<a href=\"https://github.com/bomjacob/VocaBot\">github</a>.\n"
                            "Telegram bot privacy mode is enabled so I can only see commands and direct replies."),
                          disable_web_page_preview=True)

    def cmd_set_voca_lang(self):
        db.update_current(self.id, 'set_voca_lang')
        reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton(lang) for lang in VOCA_LANG]],
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

    def operation_step(self, current):
        paged_operations = ['search', 'top', 'new', 'artist', 'artist_RatingScore', 'artist_PublishDate', 'derived']
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
        elif current[0] == 'set_lang':
            if self.text in LANGS:
                if self.type == 'private':
                    db.set_lang(self.from_id, self.text)
                else:
                    db.set_lang(self.id, self.text)
                self.send_message(text=_("{type} language set to {lang}").format(
                    type=_('User') if self.type == 'private' else _('Chat'),
                    lang=self.text),
                    reply_markup=ReplyKeyboardHide())
                db.remove_current(self.id)
            else:
                self.send_message(text=_("Language not found. Try again."))
        elif current[0] == 'set_voca_lang':
            try:
                if self.type == 'private':
                    db.set_voca_lang(self.from_id, self.text)
                else:
                    db.set_voca_lang(self.id, self.text)
                self.send_message(text=_("{type} language set to {lang}").format(
                    type=_('User') if self.type == 'private' else _('Chat'),
                    lang=self.text),
                    reply_markup=ReplyKeyboardHide())
                db.remove_current(self.id)
            except ValueError:
                self.send_message(text=_("Language not found. Try again."))
        elif current[0] in paged_operations:
            if self.text.startswith('/page'):
                search = re.search(r'/page_(\d*)@?', self.text)
                try:
                    self.offset = (int(search.group(1)) - 1) * 3
                    self.text = base64.b64decode(current[1]).decode('utf-8')
                except AttributeError:
                    return

                if current[0] == 'top':
                    self.get_songs('', max_results=3, offset=self.offset)
                    self.send_message(text=self.content()[0],
                                      reply_markup=ReplyKeyboardHide())
                elif current[0] == 'new':
                    self.get_songs('', max_results=3, offset=self.offset, sort='AdditionDate')
                    self.send_message(text=self.content()[0],
                                      reply_markup=ReplyKeyboardHide())
                elif current[0] == 'artist_RatingScore':
                    self.get_songs('', artist_id=self.text, max_results=3, offset=self.offset, sort='RatingScore')
                    self.send_message(text=self.content()[0],
                                      reply_markup=ReplyKeyboardHide())
                elif current[0] == 'artist_PublishDate':
                    self.get_songs('', artist_id=self.text, max_results=3, offset=self.offset, sort='PublishDate')
                    self.send_message(text=self.content()[0],
                                      reply_markup=ReplyKeyboardHide())
                elif current[0] == 'derived':
                    self.get_derived(song_id=self.text, max_results=3, offset=self.offset)
                    self.send_message(text=self.content(err='derived')[0])

            if current[0] == 'search' and not self.text.startswith('/'):
                self.get_songs(self.text, max_results=3, offset=self.offset)
                (content, status) = self.content()
                if status != -1:
                    db.update_current(self.id, 'search', base64.b64encode(self.text.encode('utf-8')))
                    self.send_message(text=content, reply_markup=ReplyKeyboardHide())
                else:
                    if current[1] == '' and not self.text.startswith('/'):
                        self.send_message(text=content, reply_markup=ForceReply())

            elif current[0] == 'artist' and not self.text.startswith('/'):
                self.get_artists(self.text, max_results=3, offset=self.offset)
                (content, status) = self.content(artist=True)
                if status != -1:
                    db.update_current(self.id, 'artist', base64.b64encode(self.text.encode('utf-8')))
                    self.send_message(text=content, reply_markup=ReplyKeyboardHide())
                else:
                    if current[1] == '' and not self.text.startswith('/'):
                        self.send_message(text=content, reply_markup=ForceReply())

    def cmd_other(self):
        logging.debug(self.text)

        # noinspection SpellCheckingInspection
        search = re.search(r'.*/.*_(\d+)', self.text)
        if search:
            search_id = search.group(1)
            for service in pvServices:
                if self.text.startswith('/{}_'.format(service)):
                    song = self.get_song(search_id, fields='PVs')
                    if song:
                        for pv in song['pVs']:
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
            elif self.text.startswith('/rel_'):
                self.send_message(_("Feature not yet supported."))
                # self.get_related_songs(search_id, fields='Names, Lyrics, Artists')
                # self.send_message(text=self.get_content()[0])
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
                self.send_message(text=_("Command not recognized. Did you misspell it?"))
        else:
            self.send_message(text=_("Command not recognized. Did you misspell it?"))

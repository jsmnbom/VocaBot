from functools import wraps

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler
from tinydb import TinyDB, Query

from constants import DB_FILE, SettingState
from i18n import _
from util import id_from_update

SETTINGS_TEXT = _("""<b>Settings for {bot_name}</b>
<i>{type}</i>&#8201;&#8201;interface language: <code>{lang}</code>

<i>{type}</i>&#8201;&#8201;VocaDB language: <code>{voca_lang}</code>

VocaDB language is the language used for song and artist titles.
<i>User</i>&#8201;&#8201;language is used for private messages and inline requests whereas <i>chat</i>&#8201;&#8201;language is the language used in the current group chat.""")

db = TinyDB(str(DB_FILE))
User = Query()

INTERFACE_LANGUAGES = {'en_us': 'English'}
VOCADB_LANGUAGES = [_('Default'), _('Japanese'), _('Romaji'), _('English')]

default_settings = {'interface': 'en_us', 'VocaDB': 'English'}


# TODO: Do /something/ with this mess
def insert_or_update(lang_type, bot, update):
    new_lang = update.callback_query.data
    iden = id_from_update(update)
    user = db.get(User.id == iden)
    if user is None:
        user = default_settings.copy()
        user.update({'id': iden})
        db.insert(user)

    if lang_type == 'interface':
        old = INTERFACE_LANGUAGES[user[lang_type]]
        new = INTERFACE_LANGUAGES[new_lang]
    else:
        old = user[lang_type]
        new = new_lang

    db.update({lang_type: new_lang}, User.id == iden)

    msg_type = _('User') if update.callback_query.message.chat.type == 'private' else _('Chat')
    text = _("<i>{type}</i>&#8201;&#8201;{lang_type} language changed from <code>{old}</code> to "
             "<code>{new}</code>.").format(type=msg_type, lang_type=lang_type, old=old, new=new)
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          message_id=update.callback_query.message.message_id,
                          text=text,
                          parse_mode=ParseMode.HTML)


def interface(bot, update):
    insert_or_update('interface', bot, update)
    return ConversationHandler.END


def voca(bot, update):
    insert_or_update('VocaDB', bot, update)
    return ConversationHandler.END


def get_voca_lang(iden):
    settings = db.get(User.id == iden)
    if settings is None:
        settings = default_settings.copy()
    return settings['VocaDB']


def get_interface_lang(iden):
    settings = db.get(User.id == iden)
    if settings is None:
        settings = default_settings.copy()
    return settings['interface']


def with_voca_lang(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        iden = id_from_update(update)
        return f(bot, update, *args, lang=get_voca_lang(iden), **kwargs)

    return wrapper


def translate(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        iden = id_from_update(update)
        with _.using(get_interface_lang(iden)):
            return f(bot, update, *args, **kwargs)

    return wrapper


@translate
def start(bot, update):
    iden = id_from_update(update)
    user = db.get(User.id == iden)
    if user is None:
        user = default_settings
    bot.send_message(chat_id=update.message.chat.id,
                     text=SETTINGS_TEXT.format(bot_name=bot.name,
                                               type=_('User') if update.message.chat.type == 'private' else _('Chat'),
                                               lang=INTERFACE_LANGUAGES[user['interface']],
                                               voca_lang=user['VocaDB']),
                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(_('Change interface language'),
                                                                              callback_data='interface'),
                                                         InlineKeyboardButton(_('Change VocaDB language'),
                                                                              callback_data='VocaDB')]]),
                     parse_mode=ParseMode.HTML)

    return SettingState.settings


@translate
def change(bot, update):
    if update.callback_query.data == 'interface':
        keyboard = [InlineKeyboardButton(lang_text, callback_data=lang_id) for lang_id, lang_text in
                    INTERFACE_LANGUAGES.items()]
        keyboard = InlineKeyboardMarkup([keyboard])
        bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                              message_id=update.callback_query.message.message_id,
                              text=_('Please choose preferred interface language.'),
                              reply_markup=keyboard,
                              parse_mode=ParseMode.HTML)

        return SettingState.interface
    elif update.callback_query.data == 'VocaDB':
        keyboard = [InlineKeyboardButton(lang_text, callback_data=lang_text) for lang_text in VOCADB_LANGUAGES]
        keyboard = InlineKeyboardMarkup([keyboard])
        bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                              message_id=update.callback_query.message.message_id,
                              text=_('Please choose preferred VocaDB language.\n'
                                     '<code>Default</code> refers to the language the artist indented.'),
                              reply_markup=keyboard,
                              parse_mode=ParseMode.HTML)
        return SettingState.voca
    else:
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text=_('Unknown setting, try again.'))

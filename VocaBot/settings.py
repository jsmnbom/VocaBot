from collections import OrderedDict
from functools import wraps

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler
from telegram.ext import ConversationHandler
from tinydb import TinyDB, Query

from constants import DB_FILE
from i18n import _
from util import id_from_update

SETTINGS_TEXT = _("""<b>Settings for {bot_name}</b>
<i>{type}</i>&#8201;&#8201;interface language: <code>{interface}</code>

<i>{type}</i>&#8201;&#8201;VocaDB language: <code>{voca}</code>

<i>{type}</i>&#8201;&#8201;originals only: <code>{originals}</code>
(If enabled will only return original songs when searching using <code>!s</code> (inline) or <code>/song</code>)

VocaDB language is the language used for song and artist titles.
<i>User</i>&#8201;&#8201;language is used for private messages and inline requests whereas <i>chat</i>&#8201;&#8201;language is the language used in the current group chat.""")

db = TinyDB(str(DB_FILE))
User = Query()

INTERFACE_LANGUAGES = OrderedDict((('en_us', 'English'),))
VOCADB_LANGUAGES = OrderedDict((('Default', _('Default')),
                                ('Japanese', _('Japanese')),
                                ('Romaji', _('Romaji')),
                                ('English', _('English'))))
ON_OFF = OrderedDict((('True', _('Enabled')),
                      ('False', _('Disabled'))))

settings_state = 42
default_settings = {}
settings = OrderedDict()


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def add_setting(name, nice_name, msg, button_text, trans, default):
    global settings, default_settings
    settings[name] = dict(nice_name=nice_name, msg=msg, button_text=button_text, trans=trans, default=default)
    default_settings[name] = default


def get_user(bot, update):
    global settings, default_settings
    iden = id_from_update(update)
    user = db.get(User.id == iden)
    if user is None:
        user = {'id': iden}
        db.insert(user)
    # Merge with default without overwriting
    for key, val in default_settings.items():
        if key not in user:
            user[key] = val
    db.update(user, User.id == iden)
    return user


def get_setting(name, bot, update):
    iden = id_from_update(update)
    user = get_user(bot, update)
    return user[name]


def with_voca_lang(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        return f(bot, update, *args, lang=get_setting('voca', bot, update), **kwargs)

    return wrapper


def translate(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        with _.using(get_setting('interface', bot, update)):
            return f(bot, update, *args, **kwargs)

    return wrapper


@translate
def start(bot, update):
    global settings
    user = get_user(bot, update)
    # noinspection PyTypeChecker
    buttons = [InlineKeyboardButton(setting['button_text'], callback_data=name) for name, setting in settings.items()]
    replace = {}
    for name, setting in settings.items():
        # noinspection PyTypeChecker
        try:
            replace[name] = setting['trans'][user[name]]
        except KeyError:
            replace[name] = _('Corrupted data...')
    replace.update({'bot_name': bot.name,
                    'type': _('User') if update.message.chat.type == 'private' else _('Chat')})
    text = SETTINGS_TEXT.format(**replace)
    bot.send_message(chat_id=update.message.chat.id,
                     text=text,
                     reply_markup=InlineKeyboardMarkup(list(chunks(buttons, 2))),
                     parse_mode=ParseMode.HTML)

    return settings_state


def change_setting(name):
    @translate
    def changer(bot, update):
        user = get_user(bot, update)
        iden = id_from_update(update)

        if update.callback_query.data not in settings[name]['trans']:
            bot.answer_callback_query(callback_query_id=update.callback_query.id, text=_('Unknown setting, try again.'))
            return name

        old = settings[name]['trans'][user[name]]
        db.update({name: update.callback_query.data}, User.id == iden)
        new = settings[name]['trans'][update.callback_query.data]

        msg_type = _('User') if update.callback_query.message.chat.type == 'private' else _('Chat')
        text = _("<i>{type}</i>&#8201;&#8201;{nice_name} changed from <code>{old}</code> to "
                 "<code>{new}</code>. Please wait up to 5 minutes for all changes to take effect.")
        text = text.format(type=msg_type, nice_name=settings[name]['nice_name'], old=old, new=new)
        bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                              message_id=update.callback_query.message.message_id,
                              text=text,
                              parse_mode=ParseMode.HTML)

        return ConversationHandler.END

    return changer


@translate
def send_changer(bot, update):
    user = get_user(bot, update)
    if update.callback_query.data in user:
        global settings
        keyboard = [InlineKeyboardButton(button_text, callback_data=button_id) for button_id, button_text in
                    settings[update.callback_query.data]['trans'].items()]
        keyboard = InlineKeyboardMarkup([keyboard])
        bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                              message_id=update.callback_query.message.message_id,
                              text=settings[update.callback_query.data]['msg'],
                              reply_markup=keyboard,
                              parse_mode=ParseMode.HTML)

        return update.callback_query.data
    else:
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text=_('Unknown setting, try again.'))


def get_states():
    global settings
    states = {name: [CallbackQueryHandler(change_setting(name))] for name, setting in settings.items()}
    states[settings_state] = [CallbackQueryHandler(send_changer)]
    return states


add_setting('interface', _('interface language'),
            _('Please choose preferred interface language.'),
            _('Change interface language'), INTERFACE_LANGUAGES, 'en_us')
add_setting('voca', _('VocaDB'),
            _('Please choose preferred VocaDB language.\n'
              '<code>Default</code> refers to the language the artist indented.'),
            _('Change VocaDB language'), VOCADB_LANGUAGES, 'English')
# TODO:: Change msg
add_setting('originals', _('originals only'),
            _('Would you like to only show original songs when searching via <code>!s</code> or <code>/song</code>?'),
            _('Change originals only'), ON_OFF, 'False')

from collections import OrderedDict
from functools import wraps

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Job
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
<i>User</i>&#8201;&#8201;settings are used for private messages and inline requests whereas <i>chat</i>&#8201;&#8201;settings are used in the current group chat.""")

db = TinyDB(str(DB_FILE))
User = Query()

INTERFACE_LANGUAGES = OrderedDict((('en_us', 'English'),))
VOCADB_LANGUAGES = OrderedDict((('Default', _('Default')),
                                ('Japanese', _('Japanese')),
                                ('Romaji', _('Romaji')),
                                ('English', _('English'))))
ON_OFF = OrderedDict((('True', _('Enabled')),
                      ('False', _('Disabled'))))

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
def start(bot, update, edit=False, chat_id=None, message_id=None):
    global settings
    user = get_user(bot, update)
    # noinspection PyTypeChecker
    buttons = [InlineKeyboardButton(setting['button_text'], callback_data='set|{}'.format(name)) for
               name, setting in settings.items()]
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
    if edit:
        bot.edit_message_text(chat_id=chat_id,
                              message_id=message_id,
                              text=text,
                              reply_markup=InlineKeyboardMarkup(list(chunks(buttons, 2))),
                              parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text(text,
                                  reply_markup=InlineKeyboardMarkup(list(chunks(buttons, 2))),
                                  parse_mode=ParseMode.HTML)


@translate
def change_setting(bot, update, setting, data, job_queue):
    user = get_user(bot, update)
    iden = id_from_update(update)

    if data not in settings[setting]['trans']:
        update.callback_query.answer(_('Unknown setting, try again.'))
        return setting

    try:
        old = settings[setting]['trans'][user[setting]]
    except KeyError:
        old = _('Corrupted data...')
    db.update({setting: data}, User.id == iden)
    new = settings[setting]['trans'][data]

    msg_type = _('User') if update.callback_query.message.chat.type == 'private' else _('Chat')
    text = _("<i>{type}</i>&#8201;&#8201;{nice_name} changed from <code>{old}</code> to "
             "<code>{new}</code>. Please wait up to 5 minutes for all changes to take effect.")
    text = text.format(type=msg_type, nice_name=settings[setting]['nice_name'], old=old, new=new)
    message = bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                                    message_id=update.callback_query.message.message_id,
                                    text=text,
                                    parse_mode=ParseMode.HTML)

    def callback(b, j):
        update.message = update.callback_query.message
        update.message.chat, update.message.from_user = update.message.from_user, update.message.chat
        start(bot, update, edit=True, chat_id=message.chat_id, message_id=message.message_id)

    job = Job(callback=callback, interval=5, repeat=False)
    job_queue.put(job)


@translate
def send_changer(bot, update, setting):
    user = get_user(bot, update)
    if setting in user:
        global settings
        keyboard = [InlineKeyboardButton(button_text, callback_data='set|{}|{}'.format(setting, button_id)) for
                    button_id, button_text in settings[setting]['trans'].items()]
        keyboard = InlineKeyboardMarkup([keyboard])
        bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                              message_id=update.callback_query.message.message_id,
                              text=settings[setting]['msg'],
                              reply_markup=keyboard,
                              parse_mode=ParseMode.HTML)
    else:
        update.callback_query.answer(_('Unknown setting, try again.'))


def delegate(bot, update, groups, job_queue):
    if groups[1]:
        change_setting(bot, update, groups[0], groups[1], job_queue)
    elif groups[0]:
        send_changer(bot, update, groups[0])
    else:
        start(bot, update)


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

import re

from telegram.constants import MAX_MESSAGE_LENGTH

from VocaBot.i18n import _


def cancel_callback_query(bot, update):
    bot.answer_callback_query(callback_query_id=update.callback_query.id)


# From ConversationHandler
def extract_user_and_chat(update):
    chat = None

    if update.message:
        user = update.message.from_user
        chat = update.message.chat
    elif update.edited_message:
        user = update.edited_message.from_user
        chat = update.edited_message.chat
    elif update.inline_query:
        user = update.inline_query.from_user
    elif update.chosen_inline_result:
        user = update.chosen_inline_result.from_user
    elif update.callback_query:
        user = update.callback_query.from_user
        chat = update.callback_query.message.chat if update.callback_query.message else None
    else:
        return False

    return user, chat


def id_from_update(update):
    user, chat = extract_user_and_chat(update)
    if update.message or update.edited_message:
        if chat.type == 'private':
            return user.id
        else:
            return chat.id
    else:
        return user.id


# By @bomjacob
# Still not 100% foolproof... fx. doesn't work properly if formatting tags are multiline i don't think
# If anyone wants to improve go ahead!
# TODO: Filter out tags for len()s?
def split(text, max_length, seps, max_formatting=99):
    """Splits text into pieces of max_lengths, but only on specified separators.
    :param max_formatting: Maximum count of formatting entities in a piece.
    :param seps: A tuple of separators, from most desired to least desired.
    :param max_length: Maximum length of pieces
    :param text: The text to split
    """
    pieces, i = [], 0
    while i < len(text):
        piece = text[i:i + max_length]
        if piece.count('<code>') + piece.count('<b>') + piece.count('<a>') > max_formatting:
            # Find place of nth occurrence in string
            for l, match in enumerate(re.finditer(r'(<code>|<b>|<a>)', piece)):
                if l == max_formatting:
                    piece = piece[0:match.end(1)]
        if i + len(piece) >= len(text):
            pieces.append(piece)
            break
        for j, sep in enumerate(seps):
            before, __, after = piece.rpartition(sep)
            if before == '':
                # Last separator?
                if j == len(seps) - 1:
                    pieces.append(after)
                    i += len(after) + len(sep)
                    break
            else:
                pieces.append(before)
                i += len(before) + len(sep)
                break
    return pieces


def edit_message_text(bot, update, *args, send_if_possible=False, text='', **kwargs):
    if update.callback_query.message:
        pieces = split(text, MAX_MESSAGE_LENGTH - 1, seps=('\n\n', '\n', ' '))
        if len(pieces) > 1:
            bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                      text=_('Message too long to send. Attempting to send in pieces.'),
                                      show_alert=True)
        for piece in pieces:
            if send_if_possible:
                bot.send_message(chat_id=update.callback_query.message.chat.id, *args, text=piece, **kwargs)
            else:
                bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                                      message_id=update.callback_query.message.message_id,
                                      text=piece,
                                      *args, **kwargs)
                # If several pieces we want to send the next piece... probably
                send_if_possible = True
    elif update.callback_query.inline_message_id:
        if len(text) > 4095:
            bot.answer_callback_query(callback_query_id=update.callback_query.id,
                                      text=_('Message too long for inline mode! Please use non-inline mode '
                                             'by sending a message directly to {bot_name}.').format(bot_name=bot.name),
                                      show_alert=True)
        else:
            bot.edit_message_text(inline_message_id=update.callback_query.inline_message_id, *args, text=text, **kwargs)

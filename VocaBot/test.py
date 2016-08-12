import logging
import os
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Updater, ConversationHandler, CallbackQueryHandler, CommandHandler)
from telegram.ext.dispatcher import run_async


def error(bot, update, err):
    logging.warning('Update "%s" caused error "%s"' % (update, err))


def start(bot, update):
    buttons = [[InlineKeyboardButton(text='Click me!', callback_data='Something')]]
    bot.send_message(chat_id=update.message.chat.id,
                     text='Click the button below and look at log.',
                     reply_markup=InlineKeyboardMarkup(buttons))


@run_async
def test(bot, update):
    # Doesn't matter what's in this func
    return ConversationHandler.END


def something(bot, update):
    return ConversationHandler.END


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

token = os.getenv('TEST-TOKEN')
if not token:
    logging.critical('NO TOKEN FOUND!')
    sys.exit()

updater = Updater(token)

dp = updater.dispatcher

test_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(test)
    ],
    states={1: CommandHandler('something', something)},
    fallbacks=[]
)

start_handler = CommandHandler('start', start)

dp.add_handler(test_handler)
dp.add_handler(start_handler)

dp.add_error_handler(error)

updater.start_polling()

updater.idle()

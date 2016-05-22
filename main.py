#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import logging.config

from telegram.ext import Updater, InlineQueryHandler, CallbackQueryHandler, MessageHandler

import handlers
import logger
from bot_api_token import TELEGRAM_BOT_API_TOKEN
from db import db

logger.start()


# noinspection PyUnusedLocal
def error(bot, update, err):
    logging.warning('Update "%s" caused error "%s"' % (update, err))


# noinspection PyUnusedLocal,PyIncorrectDocstring
def all_msg_filter(update):
    """We want them all!"""
    return True


def main():
    dp.addHandler(MessageHandler([all_msg_filter], handlers.MessageHandler))

    dp.addHandler(InlineQueryHandler(handlers.InlineQueryHandler))

    dp.addHandler(CallbackQueryHandler(handlers.CallbackQueryHandler))

    dp.addErrorHandler(error)

    # Add DB saving to job queue
    queue.put(db.commit, interval=5 * 60, repeat=True)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    # noinspection SpellCheckingInspection
    updater = Updater(token=TELEGRAM_BOT_API_TOKEN, workers=8, job_queue_tick_interval=60)
    dp = updater.dispatcher
    queue = updater.job_queue

    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import logging.config
import os

from telegram.ext import Updater, InlineQueryHandler, CallbackQueryHandler, MessageHandler

import handlers
import logconf
from db import db
from voca_db import voca_db

logconf.start()
logger = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def error(bot, update, err):
    logger.warning('Update "%s" caused error "%s"' % (update, err))


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
    updater = Updater(token=os.environ.get('VOCABOT_API_KEY'), workers=8, job_queue_tick_interval=60)
    dp = updater.dispatcher
    queue = updater.job_queue

    voca_db.set_name(updater.bot.name)

    main()

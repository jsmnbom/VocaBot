#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import logging.config

from telegram.ext import Updater, InlineQueryHandler, CallbackQueryHandler, RegexHandler

import logger
from bot_api_token import TELEGRAM_BOT_API_TOKEN
from db import db
from handler import Handler

logger.start()


# noinspection PyUnusedLocal
def error(bot, update, err):
    logging.warning('Update "%s" caused error "%s"' % (update, err))


def main():
    dp.addHandler(RegexHandler(r'.*', Handler))

    dp.addHandler(InlineQueryHandler(Handler))

    dp.addHandler(CallbackQueryHandler(Handler))

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

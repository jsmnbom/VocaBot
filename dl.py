import logging
import re

import youtube_dl

logger = logging.getLogger(__name__)


def my_hook(d):
    if d['status'] == 'finished':
        logger.debug('Done downloading, now converting ...')


# noinspection PyMethodMayBeStatic
class Downloader(object):
    def __init__(self, callback):
        # noinspection SpellCheckingInspection
        self.opts = {
            'simulate': True,
            'forceurl': True,
            'logger': self,
            'progress_hooks': [my_hook]
        }

        self.dl = youtube_dl.YoutubeDL(self.opts)
        self.callback = callback

    def get_link(self, url):
        self.dl.download([url])

    def debug(self, msg):
        search = re.search(r"^.*(http(s)?://.*)$", msg)
        if search:
            url = search.group(1)
            self.callback(audio=url)
        logger.debug(msg)

    def warning(self, msg):
        logger.warning(msg)

    def error(self, msg):
        logger.error(msg)

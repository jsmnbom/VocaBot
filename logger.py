import logging
import logging.config

import sys

# noinspection SpellCheckingInspection
logDict = {'formatters': {'breif': {'format': '%(levelname)s: %(message)s'},
                          'precise': {'format': '%(asctime)s %(levelname)s: %(message)s'}},
           'handlers': {'console': {'class': 'logging.StreamHandler',
                                    'formatter': 'breif',
                                    'level': 'INFO',
                                    'stream': 'ext://sys.stdout'},
                        'file': {'class': 'logging.FileHandler',
                                 'encoding': 'utf-8',
                                 'filename': 'log.log',
                                 'formatter': 'precise',
                                 'level': 'DEBUG'}},
           'loggers': {'': {'handlers': ['console', 'file'], 'level': 'DEBUG'}},
           'version': 1}


def start():
    try:
        if sys.argv[1] == 'deploy':
            logging.config.dictConfig(logDict)
    except IndexError:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

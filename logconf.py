import logging
import logging.config
import sys


# TODO: Better logging. With better config, filter out repeated stuff etc.
def start():
    deploy = False
    try:
        if sys.argv[1] == 'deploy':
            deploy = True
    except IndexError:
        pass

    if deploy:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

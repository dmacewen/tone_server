import logging
import logging.handlers
import os

def getLogger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    LOG_FILE = '/opt/python/log/tone-server-app.log' #For Prod
    isFile = os.path.isfile(LOG_FILE)

    if not isFile:
        LOG_FILE = 'tone-server-app.log'

    handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1048576, backupCount=5)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

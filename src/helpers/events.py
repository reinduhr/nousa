import logging

logger = logging.getLogger(__name__)


def error_listener(event):

    logger.info("LISTENER TRIGGERED!") # Add a loud print here for testing

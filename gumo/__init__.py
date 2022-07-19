import logging
import os

# Logger setup
log_pattern = logging.Formatter('%(asctime)s:%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('GUMO_LOG_LEVEL') or logging.INFO)

# write in the console
steam_handler = logging.StreamHandler()
steam_handler.setFormatter(log_pattern)
steam_handler.setLevel(logging.DEBUG)
logger.addHandler(steam_handler)

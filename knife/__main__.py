import os
import sys
import logging
from flask import Flask
from flask_cors import CORS
from knife.routes import setup_routes
from knife.drivers import DRIVERS, get_driver

level = logging.INFO
if os.environ.get('KNIFE_DEBUG'):
    level = logging.DEBUG

logging.basicConfig(stream=sys.stderr, level=level)

try:
    database_type = os.environ['DATABASE_TYPE']
    database_location = os.environ['DATABASE_URL']
except KeyError as e:
    logging.error("Missing environment variable: %s", str(e))
    sys.exit(4)

driver = get_driver(database_type, database_location)
if not driver:
    logging.error("Available backends: %s", ", ".join(DRIVERS.keys()))
    sys.exit(4)

APP = Flask(__name__)
setup_routes(APP, driver)
CORS(APP)

if __name__ == '__main__':
    APP.run()

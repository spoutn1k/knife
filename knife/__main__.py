import os
import logging
from flask import Flask, request
from knife.routes import setup_routes

if os.environ.get('KNIFE_DEBUG'):
    logging.basicConfig(filename="knife.%d.log" % os.getpid(),
                        level=logging.DEBUG)

APP = Flask(__name__)
setup_routes(APP)

if __name__ == '__main__':
    APP.run()

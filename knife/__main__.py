import os
import logging
from flask import Flask
from flask_cors import CORS
from knife.routes import setup_routes

if os.environ.get('KNIFE_DEBUG'):
    logging.basicConfig(filename="knife.%d.log" % os.getpid(),
                        level=logging.DEBUG)

if os.environ.get('KNIFE_COVERAGE'):
    import coverage
    import atexit

    cov = coverage.Coverage(branch=True)
    cov.start()

    def save_coverage():
        logging.info("Saving coverage")
        cov.stop()
        cov.save()

    atexit.register(save_coverage)

APP = Flask(__name__)
setup_routes(APP)
CORS(APP)

if __name__ == '__main__':
    APP.run()

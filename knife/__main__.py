import os
import logging

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

from flask import Flask, request
from knife.routes import setup_routes

APP = Flask(__name__)
setup_routes(APP)

if __name__ == '__main__':
    APP.run()

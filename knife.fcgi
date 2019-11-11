#!/usr/bin/python3

from flup.server.fcgi import WSGIServer
from api import APP

if __name__ == '__main__':
    WSGIServer(APP).run()

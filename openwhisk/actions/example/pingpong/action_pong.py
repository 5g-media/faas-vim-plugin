#!/usr/bin/env python

import os
import sys
from gevent.wsgi import WSGIServer

import flask


proxy = flask.Flask(__name__)
proxy.debug = False


@proxy.route('/hello', methods=['GET'])
def hello():
    return ("Greetings from pong action! "
            "Initialized with Arguments: %s" % str(sys.argv))


@proxy.route('/pong/<num>', methods=['GET'])
def pong(num):
    sys.stdout.write('Received /pong/%s request\n' % num)
    return ('pong'*int(num), 200)


port = int(os.getenv('LISTENING_PORT'))
server = WSGIServer(('', port), proxy, log=None)
server.serve_forever()

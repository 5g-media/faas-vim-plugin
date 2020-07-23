#!/usr/bin/env python

import os
import requests
import subprocess
import sys
from gevent.wsgi import WSGIServer

import flask


proxy = flask.Flask(__name__)
proxy.debug = False


def _get_conf(param_name):
    p = subprocess.Popen(
        ['/get-conf', param_name],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
        # run the process and wait until it completes.
        # stdout/stderr will always be set because we passed PIPEs to Popen
    (o, e) = p.communicate(input=param_name)
    return o


@proxy.route('/hello', methods=['GET'])
def hello():
    return ("Greetings from ping action! "
            "Initialized with Arguments: %s" % str(sys.argv))


@proxy.route('/getParam/<param_name>', methods=['GET'])
def getParam(param_name):
    return ("%s" % _get_conf(param_name))


@proxy.route('/ping/<num>', methods=['GET'])
def ping(num):
    sys.stdout.write('Received /ping/%s request \n' % num)
    target_ip = _get_conf('target_ip')
    if not target_ip:
        return ("I don't know the target I should ping to :( ")

    r = requests.get('http://%s:5001/pong/%s' % (target_ip.strip(), num),
                     verify=False)
    r.raise_for_status()
    sys.stdout.write('Received /pong answer %s \n' % r.text)
    return ("%s" % r.text)


port = int(os.getenv('LISTENING_PORT'))
server = WSGIServer(('', port), proxy, log=None)
server.serve_forever()

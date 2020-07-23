import os
import sys

from gevent.wsgi import WSGIServer

import flask


proxy = flask.Flask(__name__)
proxy.debug = False


@proxy.route('/conf/<param_name>', methods=['POST'])
def conf(param_name):
    def error():
        response = flask.jsonify({'error': '/conf did not receive a dictionary as an argument.'})
        response.status_code = 404
        return response

    sys.stdout.write('Enter: /conf '+ param_name +'\n')
    message = flask.request.get_json(force=True, silent=True)
    if message and not isinstance(message, dict):
        return error()
    else:
        value = message.get('value', '') if message else ''
        sys.stdout.write('value: ' + str(value) +'\n')
        if value:
            filename = '/conf/%s' % param_name
            try:
                sys.stdout.write('delete file: ' + filename +'\n')
                os.remove(filename)
            except:
                pass
            try:
                with open(filename, 'w+') as f:
                    f.write(str(value))
                return ('OK', 200)
            except Exception as e:
                sys.stdout.write('Error: ' + str(e) +'\n')
                response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
                response.status_code = 500
                return response


def main():
    port = int(os.getenv('CONF_PROXY_PORT', 8081))
    server = WSGIServer(('0.0.0.0', port), proxy, log=None)
    server.serve_forever()

if __name__ == '__main__':
    main()

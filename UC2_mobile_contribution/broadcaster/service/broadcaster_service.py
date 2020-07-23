import collections
import json
import os
import re
from requests.exceptions import HTTPError
import uuid
import sys
from gevent.wsgi import WSGIServer


import thread
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError


import flask

proxy = flask.Flask(__name__)
proxy.debug = False


conf_port = os.getenv('CONF_PORT', "5001")
# mode to enable ss_cno i.e connect to kafka bus
# note that even though service is enabled, it will use cno only
# if function is passed to edge-selection API
SS_CNO = os.getenv('SS_CNO', False)


GPS_REGEX = re.compile('(\d+\.\d+) (N|S), (\d+\.\d+) (E|W)')

KAFKA_SERVER = "{}:{}".format(os.environ.get("KAFKA_HOST", "192.158.1.175"),
                              os.environ.get("KAFKA_PORT", "9092"))
KAFKA_TOPIC = 'cno'
KAFKA_CLIENT_ID = 'edge-selector'
KAFKA_API_VERSION = (0, 10, 1)

SENDER_RECEIVER_EDGE = 'edge-selector'
SENDER_RECEIVER_SSCNO = 'SS-CNO-UC2-MC'


broadcasters = {}
contribution_pops = {}


GpsCoords = collections.namedtuple("GpsCoords",
                                   ["latitude", "n_s",
                                    "longitude",
                                    "e_w"]
                                   )

# Contains per session response from ss-cno
# Populated by consumer thread
# Read by rest endpoint
session_uuid_sscno = {}


def _is_near(g_input, g_pop):
    return abs(g_input.latitude - g_pop.latitude) < 1 and \
        abs(g_input.longitude - g_pop.longitude) < 1


def _from_selected_pop_to_result(selected_pop):
    return {
        'description': selected_pop['description'],
        'gps': selected_pop['gps'],
        'name': selected_pop['name'],
        'url': selected_pop['url']
    }


def find(l, predicate):
    """
    Utility function to find element in given list
    """
    results = [x for x in l if predicate(x)]
    return results[0] if len(results) > 0 else None


def getMessagePayload():
    message = flask.request.get_json(force=True, silent=True)
    if message and not isinstance(message, dict):
        flask.abort(400, 'message payload is not a dictionary')
    else:
        value = message.get('value', {}) if message else {}
    if not isinstance(value, dict):
        flask.abort(400, 'message payload did not provide binding for "value"')
    return value;


def _get_pop_list_broadcaster(br_id):
    """
    Utility method to return list of pops related to the given
    broadcaster id
    """
    pops = []
    for pop_id in contribution_pops:
        pop = contribution_pops[pop_id]
        if find(pop.get('broadcasters', []), lambda e: e == br_id):
            pops.append(pop)

    return pops


@proxy.route('/broadcaster-management/broadcasters/<br_id>', methods=['POST'])
def create_broadcaster_entry(br_id):
    try:
        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')

        values = dict(message)
        global broadcasters
        broadcasters[br_id] = values

        print(broadcasters)
        return ('OK', 200)

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500
        print(response)
        return response


@proxy.route('/broadcaster-management/broadcasters/<br_id>/endpoints', methods=['POST'])
def create_broadcaster_endpoint(br_id):
    # NOTE: endpoints do not include safe environments. These are stored separately
    try:
        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')

        values = dict(message)
        gps = values['gps']
        if not GPS_REGEX.match(gps):
            raise Exception('Wrong GPS format. Example format: "37.987 N, 23.750 E"')

        global broadcasters
        endpoints = broadcasters[br_id].setdefault('endpoints', [])
        endpoints.append(values)
        print(broadcasters)
        return ('OK', 200)
 
    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response



@proxy.route('/broadcaster-management/broadcasters/<br_id>/edge-selection/<session_uuid>', methods=['GET'])
def get_edge_response(br_id, session_uuid):
    try:
        val = session_uuid_sscno.get(session_uuid, {})
        if not val:
            response = flask.jsonify({'status': 'NOT_READY'})
        else:
            pop_id = val['resource']['nfvi_uuid']
            pop = contribution_pops[pop_id]
            values = _from_selected_pop_to_result(pop)
            # include edge resource to be used
            # so that ow gw api translate these to vnfs/placements
            values['resource'] = val['resource']
            values['status'] = 'READY'
            response = flask.jsonify(values)

        response.status_code = 200

    except KeyError as e:
        print ('[error] missing key: %s' % str(e))
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        print ('[error] %s' % str(e))
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response



@proxy.route('/broadcaster-management/broadcasters/<br_id>/edge-selection', methods=['POST'])
def broadcaster_edge_selection(br_id):
    try:
        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')

        message = dict(message)
        gps = message['gps']
        if not GPS_REGEX.match(gps):
            raise Exception('Wrong GPS format. Example format: "37.987 N, 23.750 E"')
        function = message.get('function')
        '''
        function --> SS_CNO
        '''
        if function:
            session_uuid = str(uuid.uuid4()).replace('-','')
            print ('** session_uuid: %s' % session_uuid)
    
            # function/mode aligned with OW GW actions
            mode = message['mode']

        latitude = float(GPS_REGEX.match(gps).group(1))
        n_s = GPS_REGEX.match(gps).group(2)
        longitude = float(GPS_REGEX.match(gps).group(3))
        e_w = GPS_REGEX.match(gps).group(4)
        g_input = GpsCoords(latitude=latitude, n_s=n_s, longitude=longitude, e_w=e_w)

        pops = _get_pop_list_broadcaster(br_id)
        if not pops:
            raise Exception('No edges found for broadcaster_id %s' % br_id)

        selected_pop = None
        for p in pops:
            g_pop = GpsCoords(latitude=float(GPS_REGEX.match(p['gps']).group(1)),
                              n_s=GPS_REGEX.match(p['gps']).group(2),
                              longitude=float(GPS_REGEX.match(p['gps']).group(3)),
                              e_w=GPS_REGEX.match(p['gps']).group(4))
            if _is_near(g_input, g_pop):
                selected_pop = p
                break

        if not selected_pop:
            raise Exception('No near edge found for coordinates: %s' % gps)
        '''
        no function --> no SS_CNO
        '''
        if not function:
            response = flask.jsonify(_from_selected_pop_to_result(selected_pop))
            response.status_code = 200

        else:
            # TODO: automatic sort
            edges = [selected_pop['id']]
            if selected_pop['id'] == 'tid':
                edges = edges + ['ncsrd']#, 'ote']
            elif selected_pop['id'] == 'ncsrd':
                edges = edges + ['tid'] # ote
            #elif selected_pop['id'] == 'ote':
            #    edges = edges + ['ncsrd', 'tid']
            '''
            Send to SS-CNO - begin
            '''
            print ('[kafka] Instantiating producer..')
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_SERVER,
                api_version=KAFKA_API_VERSION,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda v: json.dumps(v).encode('utf-8'))
            print ('[kafka] Instantiating producer. Done')
            p = {
                'sender': SENDER_RECEIVER_EDGE,
                'receiver': SENDER_RECEIVER_SSCNO,
                'session_uuid': session_uuid,
                'payload': {
                    'function': function,
                    'mode': mode,
                    'nfvi_uuid_list': edges
                }
            }
            print ('[kafka] About to send message on Kafka..')
            t = producer.send(KAFKA_TOPIC, value=p)
            print ('[kafka] Message sent!')
            try:
                t.get(timeout=5)
            except KafkaError as e:
                logger.error(e)
                pass
            producer.close()
            '''
            Send to SS-CNO - end
            '''

            response = flask.jsonify(dict(session_uuid=session_uuid))
            response.status_code = 200

    except KeyError as e:
        print ('[error] missing key: %s' % str(e))
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        print ('[error] %s' % str(e))
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


def _add_pops(broadcaster, br_id):
    """
    Utility method to populate broadcaster with safe-local-environment
    endpoint of the pops it belongs to
    """
    endoints = broadcaster.setdefault('endpoints', [])
    sl_endpoint = find(endoints, lambda e: e['name'] == 'safe-local-environments')
    # always 're-build'
    if sl_endpoint:
        endoints.remove(sl_endpoint)
    sl_endpoint = dict(name='safe-local-environments',
                        description='Safe local environments (edge) used by this broadcaster',
                        safe_local=_get_pop_list_broadcaster(br_id))
    endoints.append(sl_endpoint)


@proxy.route('/broadcaster-management/broadcasters', methods=['GET'])
def get_broadcasters():
    try:
        values = broadcasters
        for br_id in values:
            _add_pops(values[br_id], br_id)
        response = flask.jsonify(values)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/broadcaster-management/broadcasters/<br_id>', methods=['GET'])
def get_broadcaster_entry(br_id):
    try:
        values = broadcasters[br_id]
        #_add_pops(values, br_id)
        response = flask.jsonify(values)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/broadcaster-management/broadcasters/<br_id>/contributions/<cont_id>', methods=['POST'])
def create_broadcaster_contribution_entry(br_id, cont_id):
    try:
        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')

        values = dict(message)
        global broadcasters
        contributions = broadcasters[br_id].setdefault('contributions', {})
        contributions[cont_id] = values
        print(broadcasters)
        return ('OK', 200)
 
    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/broadcaster-management/broadcasters/<br_id>/contributions/<cont_id>', methods=['GET'])
def get_broadcaster_contribution_entry(br_id, cont_id):
    try:
        values = broadcasters[br_id]
        contribution_entry = values['contributions'][cont_id]
        response = flask.jsonify(contribution_entry)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/broadcaster-management/broadcasters', methods=['DELETE'])
def delete_broadcasters():
    try:
        global broadcasters
        broadcasters = {}
        return ('OK', 200)

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/broadcaster-management/broadcasters/<br_id>', methods=['DELETE'])
def delete_broadcaster_entry(br_id):
    try:
        global broadcasters
        del broadcasters[br_id]
        return ('OK', 200)

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/mc-pop-management/cognitive-pops/<pop_id>', methods=['POST'])
def create_mc_pop(pop_id):
    try:
        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')

        values = dict(message)
        values['id'] = pop_id
        gps = values['gps']
        if not GPS_REGEX.match(gps):
            raise Exception('Wrong GPS format. Example format: "37.987 N, 23.750 E"')

        global contribution_pops
        contribution_pops[pop_id] = values
        print(contribution_pops)
        return ('OK', 200)

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/mc-pop-management/cognitive-pops', methods=['GET'])
def get_mc_pops():
    try:
        response = flask.jsonify(contribution_pops)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/mc-pop-management/cognitive-pops/<pop_id>', methods=['GET'])
def get_mc_pop_entry(pop_id):
    try:
        values = contribution_pops[pop_id]
        response = flask.jsonify(values)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/mc-pop-management/cognitive-pops/<pop_id>', methods=['DELETE'])
def delete_mc_pop(pop_id):
    try:
        global contribution_pops
        del contribution_pops[pop_id]
        return ('OK', 200)

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/mc-pop-management/cognitive-pops', methods=['DELETE'])
def delete_mc_pops():
    try:
        global contribution_pops
        contribution_pops = {}
        return ('OK', 200)

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


def _consume_cno():
    """
    Separate consumer thread.
    """
    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_SERVER,
        client_id=KAFKA_CLIENT_ID,
        enable_auto_commit=True,
        api_version=KAFKA_API_VERSION)

    consumer.subscribe(pattern=KAFKA_TOPIC)
    print ('\n\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-')
    print ("Starting Kafka thread..\n\n"
           "KAFKA_CLIENT_ID: '%s' \n"
           "KAFKA_SERVER '%s' "
           "KAFKA_API_VERSION '%s' " %
           (KAFKA_CLIENT_ID, KAFKA_SERVER, KAFKA_API_VERSION))
    print ('-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n')

    for msg in consumer:
        try:
            message = json.loads(msg.value.decode('utf-8'))
            print('[kafka] Received message: {}'.format(message))
            if message['sender'] == SENDER_RECEIVER_SSCNO and \
                message['receiver'] == SENDER_RECEIVER_EDGE:
                session_uuid = message['session_uuid']
                global session_uuid_sscno
                session_uuid_sscno[session_uuid] = message
                print ('Stored session_uuid [%s] <-> message [%s]'
                       % (session_uuid, message))
        except Exception as e:
            print ('Exception: %s' % str(e))


if __name__=="__main__":
    if SS_CNO:
        print ('** Start _consume_cno thread..')
        thread.start_new_thread(_consume_cno, ())
    print ('starting tiny micro-service. '
           '\nlistening on port %s...' % conf_port)
    server = WSGIServer(('', int(conf_port)), proxy, log=None, keyfile='/server.key', certfile='/server.crt')
    server.serve_forever()

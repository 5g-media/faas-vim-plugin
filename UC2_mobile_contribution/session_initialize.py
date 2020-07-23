"""
Openwhisk action deployed at the gateway edge to serve as a contribution endpoint.

This action should get called *AFTER* network service IngressUrl verified to be exist.

Triggers event based instantiation for the cognitive services as denoted by
the function parameter.

:param session_uuid: UUID for this contribution session.

:param mode: The mode of where to stream the contribution result.
             Valid values: live-remote, safe-remote, safe-local.

:param broadcaster-endpoint-ip: The IP to stream contribution content. Only relevant for modes:
                                 live-remote, safe-remote.
                                 Note: for safe-local, an internal edge url is being used

:param function: The function(s) to start for this session. Valid values: vspeech, vspeech_vdetection, vdetection, none

:param resource: GPU/CPU to be used for cognitive services.(Optional)

                  Below is an example format:
                  "resource": {
                   "GPU": ["vdetection", "vspeech"],
                   "CPU": []
                }

:return session-uuid: uuid of the session being created
:return event-uuid: uuid of the event being invoked for 'function'

Note: error key with proper error message returned in case of failure
"""
import json
import requests
import time
import uuid


osm_ip = '10.100.176.66'
osm_vim_account_name = 'FaaS_VIM-NCSRD'
osm_nsd_name = 'mobile_contribution_bootstrap_nsd'

rtmp_ip = '10.30.2.54'

mode_values = ['safe-remote', 'live-remote', 'safe-local']
remote_values = ['safe-remote', 'live-remote']
safe_values = ['safe-local', 'safe-remote']

function_values = ['vspeech', 'vspeech_vdetection', 'vdetection', 'none']


INTERVAL=1
TIMEOUT=45


def find(l, predicate):
    """
    Utility function to find element in given list
    """
    results = [x for x in l if predicate(x)]
    return results[0] if len(results) > 0 else None


def raise_for_status(r):
    http_error_msg = ''

    if 400 <= r.status_code < 500:
        http_error_msg = '%s Client Error: %s' % (r.status_code, r.reason)

    elif 500 <= r.status_code < 600:
        http_error_msg = '%s Server Error: %s' % (r.status_code, r.reason)

    return http_error_msg


def main(args):
    osm_token = ''

    web_result = {
      'body': {},
      'statusCode': 200,
      'headers':{'Content-Type': 'application/json'}
    }

    try:
        '''
        ~~~~~~~~~~~~~~~~~~~~
        Optional parameters
        ~~~~~~~~~~~~~~~~~~~~
        '''
        session_uuid = args.get('session-uuid')
        if not session_uuid:
            web_result['body'] = {'error' : 'Did not provide required "session-uuid" parameter' }
            return web_result

        mode = args.get('mode')
        if mode is None:
            web_result['body'] = {'error' : 'Did not provide required "mode" parameter' }
            return web_result

        if mode not in mode_values:
            web_result['body'] = {'error' : 'Illegal "mode" value: %s. Values: %s' % (mode, mode_values)}
            return web_result
        if mode == 'live-remote':
            web_result['body'] = {'error' : 'Live-remote not currently supported :(' }
            return web_result

        function = args.get('function')
        if function is None:
            web_result['body'] = {'error' : 'Did not provide required "function" parameter' }
            return web_result

        if function not in function_values:
            web_result['body'] = {'error' : 'Illegal "function" value: %s. Values: %s' % (function, function_values)}
            return web_result

        broadcaster_ip = args.get('broadcaster-endpoint-ip', 'na')
        if broadcaster_ip == 'na' and (mode in remote_values):
            web_result['body'] = {'error': 'Did not provide required "broadcaster-endpoint-ip" parameter for mode: %s' % mode}
            return web_result

        resource = args.get('resource', {})
        print('***** resource: %s' % resource)

        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}

        enable_vspeech = 'true' if function in ['vspeech', 'vspeech_vdetection'] else 'false'
        enable_vdetection = 'true' if function in ['vdetection', 'vspeech_vdetection'] else 'false'

        stream_output_url = 'rtmp://%s:1935/detection/%s' % (rtmp_ip, session_uuid)\
            if mode in ['safe-local'] else 'rtmp://%s:1935/detection/%s' % (broadcaster_ip, session_uuid)

        req_url_speech = 'http://%s:8080/%s.speech.vtt' % (rtmp_ip, session_uuid)\
            if mode in ['safe-local'] else 'http://%s:8080/%s.speech.vtt' % (broadcaster_ip, session_uuid)

        req_url_detection = 'http://%s:8080/%s.objects.ass' % (rtmp_ip, session_uuid)\
            if mode in ['safe-local'] else 'http://%s:8080/%s.objects.ass' % (broadcaster_ip, session_uuid)

        # support 'POST' in live?
        req_method_speech = 'PUT' if mode in ['safe-local'] else 'PUT'

        # support 'POST' in live?
        req_method_detection = 'PUT' if mode in ['safe-local'] else 'PUT'

        # support 'mpegts' in live?
        stream_output_format = 'flv' if mode in ['safe-local'] else 'flv'

        vdetection_gpu = True if find(resource.get('GPU', []),
                                      lambda e: e == 'vdetection') else False
        vspeech_gpu = True if find(resource.get('GPU', []),
                                      lambda e: e == 'vspeech') else False

        speech_extra = {
            'vnfd_name_speech': 'vspeech_gpu_vnfd' if vspeech_gpu else 'vspeech_cpu_vnfd',
            'vnfd_index_speech': '3' if vspeech_gpu else '4'
        }
        detection_extra = {
            'vnfd_name_detection': 'vdetection_gpu_vnfd' if vdetection_gpu else 'vdetection_cpu_vnfd',
            'vnfd_index_detection': '5' if vdetection_gpu else '6',
            'use_gpu': 'true' if vdetection_gpu else 'false'
        }

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Poll Network Service
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        ingress = None
        r = requests.get(
            'http://%s:5001/osm/%s' % (osm_ip, session_uuid))

        error_msg = raise_for_status(r)
        if not error_msg:
            r_json = r.json()
            bootstrap_vnf = r_json['vnfs'][0]
            ingress = bootstrap_vnf.get('vim_info', {}).get('IngressUrl')
            if ingress:
                print ('** Ingress: %s' % ingress)
            else:
                web_result['body'] = {
                    'session-uuid': session_uuid,
                    'message': 'NOT_FOUND'
                }
                return web_result

        else:
            web_result['body'] = {'error': '%s. Details: %s' % (error_msg, r.text)}
            return web_result

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Trigger event based cognitive deployment
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
        event_uuid = str(uuid.uuid4()).replace('-','')
        print ('** event_uuid: %s' % event_uuid)
        payload = {
            # -=-= common
            'event_uuid': event_uuid,
            'osm_ip': osm_ip,
            'osm_ns': session_uuid,
            'operation': function,
            # -=-= speech
            'req_url_speech': req_url_speech,
            'req_method_speech': req_method_speech,
            'decode_metadata': 'true',

            # -=-= detection
            'req_url_detection': req_url_detection,
            'req_method_detection': req_method_detection,
            'cnn_model': 'TinyYoloV2',
            'use_recognition': 'false',
            'use_age_gender_expressions': 'true',

            # these used for persistency
            'mode': mode,
            'broadcaster_ip': broadcaster_ip
        }
        payload.update(speech_extra)
        payload.update(detection_extra)

        while True:
            try:
                r = requests.post('%s/handlerequest' % ingress, headers=headers, json=payload)
                break
            except:
                print ('** Exception occurred while trying to send an event. Retrying...')
                continue
        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': 'Failed triggering event: %s. Details: %s' % (error_msg, r.text)}
            return web_result

        web_result['body'] = {
            'session-uuid': session_uuid,
            'event-uuid': event_uuid
        }
        return web_result


    except Exception as e:
        web_result['body'] = {'error': 'General Error. Details: %s' % str(e)}
        return web_result
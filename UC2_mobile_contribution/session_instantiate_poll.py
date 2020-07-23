"""
Openwhisk action deployed at the gateway edge to serve as a contribution endpoint.

The action checks to see if IngressUrl exists in VNFR[0]. If no,
returns {'session-uuid': <session_uuid>, 'status': 'INGRESS_NOT_FOUND'}

If yes, returns {'session-uuid': <session_uuid>, 'status': 'INGRESS_FOUND'}

:param session_uuid: UUID for this contribution session. If not provided, new one is generated. (Optional)

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
        if session_uuid is None:
          web_result['body'] = { 'error' : 'Did not provide required \"session-uuid\" parameter' }
          return web_result
        
        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}

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
                web_result['body'] = {
                    'session-uuid': session_uuid,
                    'status': 'INGRESS_FOUND'
                }
                return web_result
            else:
                web_result['body'] = {
                    'session-uuid': session_uuid,
                    'status': 'INGRESS_NOT_FOUND'
                }
                return web_result

        else:
            web_result['body'] = {'error': '%s. Details: %s' % (error_msg, r.text)}
            return web_result

    except Exception as e:
        web_result['body'] = {'error': 'General Error. Details: %s' % str(e)}
        return web_result
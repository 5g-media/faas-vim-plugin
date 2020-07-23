"""
Openwhisk action deployed at the gateway edge to serve as a contribution endpoint.

The action instantiates mobile contribution network service

:param session-uuid: UUID for this contribution session. If not provided, new one is generated. (Optional)

:param mode: The mode of where to stream the contribution result.
             Valid values: live-remote, safe-remote, safe-local.

:param broadcaster-endpoint-ip: The IP to stream contribution content. Only relevant for modes:
                                 live-remote, safe-remote.
                                 Note: for safe-local, an internal edge url is being used

:param function: The function(s) to start for this session. Valid values: vspeech, vspeech_vdetection, vdetection, none

:param osm_username: OSM username to be used when accessing OSM.(Optional)

:param osm_password: OSM password be used when accessing OSM.(Optional)

:param osm_project: OSM project Id to be used when accessing OSM.(Optional)

:return session-uuid: uuid of the session being created

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
            session_uuid = str(uuid.uuid4()).replace('-','')
        print ('** session_uuid: %s' % session_uuid)
        
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

        osm_username = args.get('osm-username', 'admin')
        osm_password = args.get('osm-password', 'admin')
        osm_project = args.get('osm-project', 'admin')

        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}

        '''
        ~~~~~~~~~~~
        OSM Token
        ~~~~~~~~~~~
        '''
        payload = {
            'username': osm_username,
            'password': osm_password,
            'project_id': osm_project
        }
        r = requests.post(
            'https://%s:9999/osm/admin/v1/tokens' % osm_ip,
            headers=headers,
            json=payload, verify=False)

        error_msg = raise_for_status(r)
        if not error_msg:
            r_json = r.json()
            osm_token = r_json['id']
            print ('** osm_token: %s' % osm_token)
        else:
            web_result['body'] = {'error': '%s. Details: %s' % (error_msg, r.text)}
            return web_result

        '''
        ~~~~~~~~~~~
        Get NSD
        ~~~~~~~~~~~
        '''
        headers.update({'Authorization': 'Bearer %s' % osm_token})
        r = requests.get(
            'https://%s:9999/osm/nsd/v1/ns_descriptors_content' % osm_ip,
            headers=headers,
            verify=False)

        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': '%s. Details: %s' % (error_msg, r.text)}
            return web_result
        r_json = r.json()
        nsd = find(r_json, lambda e: e['name'] == osm_nsd_name)
        if not nsd:
            web_result['body'] = {'error': 'Failed to find NSD "%s"' % osm_nsd_name}
            return web_result

        osm_nsd = nsd['_id']

        '''
        ~~~~~~~~~~~~~~~~~~~~
        Get vim_account
        ~~~~~~~~~~~~~~~~~~~~
        '''
        r = requests.get(
            'https://%s:9999/osm/admin/v1/vim_accounts' % osm_ip,
            headers=headers,
            verify=False)

        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': '%s. Details: %s' % (error_msg, r.text)}
            return web_result
        r_json = r.json()
        vim_account = find(r_json, lambda e: e['name'] == osm_vim_account_name)
        if not vim_account:
            web_result['body'] = {'error': 'Failed to find vim_account "%s"' % osm_vim_account_name}
            return web_result

        osm_vim_account = vim_account['_id']

        enable_vspeech = 'true' if function in ['vspeech', 'vspeech_vdetection'] else 'false'
        enable_vdetection = 'true' if function in ['vdetection', 'vspeech_vdetection'] else 'false'

        stream_output_url = 'rtmp://%s:1935/detection/%s' % (rtmp_ip, session_uuid)\
            if mode in ['safe-local'] else 'rtmp://%s:1935/detection/%s' % (broadcaster_ip, session_uuid)

        # support 'mpegts' in live?
        stream_output_format = 'flv' if mode in ['safe-local'] else 'flv'

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Splitter (index 2) - day 0 Parameters
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        payload = {
            'action_params': {
                'stream_output_url': stream_output_url,
                'stream_output_format': stream_output_format, 
                'enable_vspeech': enable_vspeech,
                'enable_vdetection': enable_vdetection,
                'debug': 'true'
            },
            'service_ports': ['9998/udp']
        }
        r = requests.post(
            'http://%s:5001/conf/%s/splitter_vnfd/2' % (osm_ip, session_uuid)
            , json=payload)
        print ('** day 0 splitter result: %s' % r.text)

        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': '%s. Details: %s' % (error_msg, r.text)}
            return web_result

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Instantiate Network Service
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        payload = {
            'nsName': session_uuid,
            'nsdId': osm_nsd,
            'vimAccountId': osm_vim_account
        }
        r = requests.post(
            'https://%s:9999/osm/nslcm/v1/ns_instances_content' % osm_ip,
            headers=headers,
            json=payload, verify=False)

        web_result['body'] = {
            'session-uuid': session_uuid,
            'phase': 'BUILD'
        }
        return web_result

    except Exception as e:
        web_result['body'] = {'error': 'General Error. Details: %s' % str(e)}
        return web_result
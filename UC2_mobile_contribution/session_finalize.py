"""
Openwhisk action deployed at the gateway edge to serve as a contribution endpoint.

This action should get called *AFTER* the stream had been terminated.

It checks the status of the session to be finalized by checking whether the metadata
file(s) exist on the endpoint. If not, returns with tuple session-uuid, event-uuid, message

If yes, it continues to persists media file URLs in the broadcaster service at SVP then asynch
deletes the required network service by sending DELETE request to OSM north-bound REST API returning their location

:param br-edge-ip: ipaddress of broadcaster_edge service

:param br-id: The id of the broadcaster

:param session-uuid: The uuid of the session to be deleted

:param event-uuid: The uuid of the event (orchestrator flow instance)

:param osm_username: OSM username to be used when accessing OSM.(Optional)

:param osm_password: OSM password be used when accessing OSM.(Optional)

:param osm_project: OSM project Id to be used when accessing OSM.(Optional)

:return session-uuid: The uuid of the session to be deleted
:return url: location of recorded file/stream

OR

:return session-uuid: The uuid of the session to be deleted
:return event-uuid: event uuid
:return message: detailed message


Note: error key with proper error message returned in case of failure
"""
import json
import re
import requests
import time


osm_ip = '10.100.176.66'
osm_vim_account_name = 'FaaS_VIM-HRL'
rtmp_ip = '10.30.2.54'

broadcaster_service_port = '5003'


URL_NOPORT_REGEX = re.compile('https?:\/\/[^:\/]+')


TERMINATION_GRACETIME = 30
mode_values = ['safe-remote', 'live-remote', 'safe-local']
remote_values = ['safe-remote', 'live-remote']
safe_values = ['safe-local', 'safe-remote']


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


def _exists(url):
    r = requests.head(url, verify=False)
    return r.status_code == requests.codes.ok, r.status_code


def main(args):
    osm_token = ''

    web_result = {
      'body': {},
      'statusCode': 200,
      'headers':{'Content-Type': 'application/json'}
    }

    try:
        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~
        Parameter validation
        ~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        br_edge_ip = args.get('br-edge-ip')
        if br_edge_ip is None:
          web_result['body'] = { 'error' : 'Did not provide required \"br-edge-ip\" parameter' }
          return web_result

        br_id = args.get('br-id')
        if br_id is None:
          web_result['body'] = { 'error' : 'Did not provide required \"br-id\" parameter' }
          return web_result

        session_uuid = args.get('session-uuid')
        if session_uuid is None:
          web_result['body'] = { 'error' : 'Did not provide required \"session-uuid\" parameter' }
          return web_result

        event_uuid = args.get('event-uuid')
        if event_uuid is None:
          web_result['body'] = { 'error' : 'Did not provide required \"event-uuid\" parameter' }
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
        ~~~~~~~~~~~~~~~~~~~~
        Get vim_account
        ~~~~~~~~~~~~~~~~~~~~
        '''
        headers.update({'Authorization': 'Bearer %s' % osm_token})
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
        offload_host = vim_account['config']['offload-service-url']
        proxierPort = vim_account['config']['proxierPort']
        if not URL_NOPORT_REGEX.match(offload_host):
            raise Exception("Error in processing offload-service-url")
        # append to base url (k8s master) the port
        proxierUrl = URL_NOPORT_REGEX.match(offload_host).group(0)+':'+str(proxierPort)
        print ('** proxierUrl: %s' % proxierUrl)


        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Get Workflow parameters
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        headers = {'Content-Type': 'application/json', 'accept': 'application/json'}
        r = requests.get(proxierUrl+'/getWorkflow/'+event_uuid, headers=headers)
        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': 'Error retrieving workflow: %s. Details: %s' % (event_uuid, r.text)}
            return web_result

        r_json = r.json()
        workflow_parameters = r_json['workflow_parameters']
        '''
        ~~~~~~~~~~~~~~~
        mode parameter
        ~~~~~~~~~~~~~~~
        '''
        u = find(workflow_parameters, lambda p: p['name'] == 'mode')
        if not u:
            web_result['body'] = {'error': 'Error retrieving "mode" parameter from workflow: %s. Details: not found' % event_uuid}
            return web_result
        mode = u['value']

        '''
        ~~~~~~~~~~~~~~~~~~~~
        operation parameter
        ~~~~~~~~~~~~~~~~~~~~
        '''
        u = find(workflow_parameters, lambda p: p['name'] == 'operation')
        if not u:
            web_result['body'] = {'error': 'Error retrieving "operation" parameter from workflow: %s. Details: not found' % event_uuid}
            return web_result
        function = u['value']

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~
        broadcaster_ip parameter
        ~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        u = find(workflow_parameters, lambda p: p['name'] == 'broadcaster_ip')
        if not u:
            web_result['body'] = {'error': 'Error retrieving "broadcaster_ip" parameter from workflow: %s. Details: not found' % event_uuid}
            return web_result
        broadcaster_ip = u['value']

        if mode == 'safe-local':
            ip = rtmp_ip
        else:
            ip = broadcaster_ip
        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Build urls for safe-local, safe-remote
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        url = 'http://%s:8080/%s.flv' % (ip, session_uuid)
        payload = {
            'url-media': url
        }
        if function in ['vspeech', 'vspeech_vdetection']:
            payload['req_url_vspeech'] = 'http://%s:8080/%s.speech.vtt' % (ip, session_uuid)
            exists, status = _exists(payload['req_url_vspeech'])
            if not exists:
                web_result['body'] = {
                    'session-uuid': session_uuid,
                    'event-uuid': event_uuid,
                    'status': 'METADATA_NOT_FOUND'
                }
                return web_result
        if function in ['vdetection', 'vspeech_vdetection']:
            payload['req_url_vdetection'] = 'http://%s:8080/%s.objects.ass' % (ip, session_uuid)
            exists, status = _exists(payload['req_url_vdetection'])
            if not exists:
                web_result['body'] = {
                    'session-uuid': session_uuid,
                    'event-uuid': event_uuid,
                    'status': 'METADATA_NOT_FOUND'
                }
                return web_result

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Needed metadata files exist on the endpoint
        Add the URLs to broadcasting model
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        cotribute_url = 'https://%(ip)s:%(port)s/broadcaster-management/broadcasters/%(br_id)s/contributions/%(session_id)s' % \
            {
                'ip': br_edge_ip,
                'port': broadcaster_service_port,
                'br_id': br_id,
                'session_id': session_uuid
            }
        r = requests.post(cotribute_url, json=payload, headers=headers, verify=False)

        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': 'Error adding contribution to broadcasting service: %s. Details: %s' % (error_msg, r.text)}
            return web_result

        #TODO: revise this wait
        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Wait grace time for metadata to get flushed
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        time.sleep(TERMINATION_GRACETIME)

        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Delete the network service instance
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        payload = {
            'username': 'admin',
            'password': 'admin',
            'project_id': 'admin'
        }
        r = requests.post(
            'https://%s:9999/osm/admin/v1/tokens' % osm_ip,
            headers=headers, json=payload, verify=False)

        error_msg = raise_for_status(r)
        if not error_msg:
            r_json = r.json()
            osm_token = r_json['id']
        else:
            web_result['body'] = {'error': 'Error retrieving OSM token: %s. Details: %s' % (error_msg, r.text)}
            return web_result

        headers['Authorization'] = 'Bearer %s' % osm_token
        r = requests.get(
            'https://%s:9999/osm/nslcm/v1/ns_instances_content' % osm_ip,
            headers=headers, verify=False)

        error_msg = raise_for_status(r)
        if not error_msg:
            r_json = r.json()
        else:
            web_result['body'] = {'error': 'Error retrieving NS instances: %s. Details: %s' % (error_msg, r.text)}
            return web_result

        n = find(r_json, lambda n: n['name'] == session_uuid)
        if not n:
            web_result['body'] = {'error': 'Could not find NS instance name [%s] to delete' % session_uuid}
            return web_result

        # send and forget
        requests.delete(
            'https://%s:9999/osm/nslcm/v1/ns_instances_content/%s' % (osm_ip, n['id']),
            headers=headers, verify=False)

        web_result['body'] = {
            'session-uuid': session_uuid,
            'cotribute-url': cotribute_url,
            'status': 'OK'
        }
        return web_result
    except Exception as e:
        web_result['body'] = {'error': 'General Error. Details: %s' % str(e)}
        return web_result
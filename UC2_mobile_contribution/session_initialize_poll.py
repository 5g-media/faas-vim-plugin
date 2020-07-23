"""
Openwhisk action deployed at the gateway edge to serve as a contribution endpoint.

The action returns orchestration flow status. If status is Succeeded, then ingress ip and port
of the splitter are returned.

:param session-uuid: The uuid of the session (network service instance)

:param event-uuid: The uuid of the event (orchestrator flow instance)

:param osm_username: OSM username to be used when accessing OSM.(Optional)

:param osm_password: OSM password be used when accessing OSM.(Optional)

:param osm_project: OSM project Id to be used when accessing OSM.(Optional)

:return session-uuid: session-uuid that is being created
:return phase: session phase
:return ipaddress: ipaddress of the splitter VNF. Applicable only when phase = 'Succeeded'
:return port: port of the splitter VNF. Applicable only when phase = 'Succeeded'

Note: error key with proper error message returned in case of failure
"""
import json
import re
import requests
import time
import uuid


osm_ip = '10.100.176.66'
osm_vim_account_name = 'FaaS_VIM-NCSRD'


URL_NOPORT_REGEX = re.compile('https?:\/\/[^:\/]+')


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
        session_uuid = args.get('session-uuid')
        if session_uuid is None:
            web_result['body'] = {'error' : 'Did not provide required \"session-uuid\" parameter' }
            return web_result

        event_uuid = args.get('event-uuid')
        if event_uuid is None:
            web_result['body'] = {'error' : 'Did not provide required \"event-uuid\" parameter' }
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
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Event based cognitive deployment status
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        headers = {'Content-Type': 'application/json'}
        r = requests.get(proxierUrl+'/getWorkflow/'+event_uuid, headers=headers)

        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': 'Error retrieving workflow: %s. Details: %s' % (error_msg, r.text)}
            return web_result

        r_json = r.json()
        phase = r_json['phase']
        workflow_parameters = r_json['workflow_parameters']
        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        If not completed - return status
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        if phase != 'Succeeded':
            web_result['body'] = {
                'session-uuid': session_uuid,
                'event-uuid': event_uuid,
                'phase': phase
            }
            return web_result
        '''
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        Retrieve Ingress from splitter VNFR
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        '''
        r = requests.get(
            '%(configAPIHost)s/osm/%(ns_name)s' %
            {
                'configAPIHost': 'http://%s:5001' % osm_ip,
                'ns_name': session_uuid
            }, verify=False)
        error_msg = raise_for_status(r)
        if error_msg:
            web_result['body'] = {'error': 'Error retrieving VNFs: %s. Details: %s' % (error_msg, r.text)}
            return web_result

        r_json = r.json()
        vnfs = r_json['vnfs']
        if len(vnfs) == 0:
            web_result['body'] = {'error': 'No VNFs for service %s. Details: Empty "vnfs" list' % session_uuid}
            return web_result

        vnf = vnfs[1]
        vim_info = vnf['vim_info']
        pod_phase = vim_info.get('pod_phase', 'Unknown')
        if pod_phase != 'Running' or vnf['status'] != 'ACTIVE':
            web_result['body'] = {'error': 'Not running. Details: VNF "%s" pod not in running/active state. '
                                  'Its current state: "%s" "%s"' % (vnf['name'], vnf['status'], pod_phase)}
            return web_result

        try:
            ipaddress = vim_info['host_ip']
            port = vim_info['service']['service_ports']['9998']
        except Exception as e:
            web_result['body'] = {'error': 'Unable to retrieve ingress ip:port of splitter. Details: %s' % str(e)}
            return web_result

        web_result['body'] = {
            'session-uuid': session_uuid,
            'event-uuid': event_uuid,
            'ipaddress': ipaddress,
            'port': str(port),
            'phase': phase
        }
        return web_result
    except Exception as e:
        web_result['body'] = {'error': 'General Error. Details: %s' % str(e)}
        return web_result
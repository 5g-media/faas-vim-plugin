# Copyright 2020, Avi Weit (weit@il.ibm.com), David Breitgand (davidbr@il.ibm.com)

# Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

 #  Unless required by applicable law or agreed to in writing, software
 #  distributed under the License is distributed on an "AS IS" BASIS,
 #  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 #  See the License for the specific language governing permissions and
 #  limitations under the License.

    
import base64
import json
import os
import requests
from requests.exceptions import HTTPError
import sys
from gevent.wsgi import WSGIServer

import flask

proxy = flask.Flask(__name__)
proxy.debug = False


VNF_CONF_PORT = "8081"
# this is our FaaS VNF ID (needed for monitoring)
RO_LABEL_VIM_VM_ID = "vim_vm_id"


OSM_VERSION = "v5.0.5"
FAAS_VERSION = "v2.0.3"


mano_host = os.getenv('OSM_RO_HOSTNAME', None)
mano_port = os.getenv('OPENMANO_PORT',"9090")
conf_port = os.getenv('CONF_PORT', "5001")

"""
{
    'star_ball': {
        '5G MEDIA vTranscoder': {
            '1': {
                action_params: {// action params key/val dict},
                service_ports: [//service ports to expose]
            },
            '2': {
                action_params: {// action params key/val dict},
                service_ports: [//service ports to expose]
            }
        },
        '5G MEDIA vBuffer': {
            '1': {
                action_params: {// action params key/val dict},
                service_ports: [//service ports to expose]
            }
        }
    }
}
ns_name: the name of the ns to instantiate. (e.g. star_ball)
vnf_name: the name of the vnf. This is the equivalent to nsd:constituent-vnfd:vnf-name
          (e.g. 5G MEDIA vTranscoder)
index: the index of the vnf starting from 1 (e.g.
       '1', '2'). This is equivalent to nsd:constituent-vnfd:member-vnf-index-ref.
"""

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


def _from_nsr_to_result(r):
    nsr = r.json()
    result = {}
    result['uuid'] = nsr['uuid']
    result['name'] = nsr['name']
    vnfs = []
    for vnf in nsr['vnfs']:
        vm = vnf['vms'][0] if len(vnf['vms']) > 0 else {}
        # vim_info if exists, must be stringified json
        status = vm.get('status', 'UNKNOWN')
        #error_msg = vm.get('error_msg') if status == 'VIM_ERROR' else None
        vnf_name = vnf['vnf_name']
        ip_address = vnf.get('ip_address', '0.0.0.0')
        try:
            vim_info = json.loads("{}" if not vm.get('vim_info') else vm['vim_info'])
        except:
            # unable to parse as json, reset it
            vim_info = {}
        v = dict(ip_address=ip_address, vnf_name=vnf_name,
                 vim_info=vim_info, status=status)
#        if error_msg:
#            v.update(error_msg=error_msg)
        vnfs.append(v)
    result['vnfs'] = vnfs
    return result


ns_configuration = {}
c_ns_configuration = {}


def _tenants_get():
    """
    Common helper to retrieve tenants
    """
    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/tenants' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    return r


def _datacenter_get(tenant_id, datacenter_id):
    """
    Common helper to retrieve VIM account info from a given id
    """
    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/datacenters/%(datacenter_id)s' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
            'tenant_id': tenant_id,
            'datacenter_id': datacenter_id
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    return r


def _instances_get(tenant_id):
    """
    Common helper to retrieve network services
    """
    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/instances' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
            'tenant_id': tenant_id,
        }, verify=False)

    print("requestAction: Received: %s" % r.text)
 
    r.raise_for_status()
    return r


def _instance_get(tenant_id, instance_id):
    """
    Common helper to retrieve network service from a given id
    """
    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/instances/%(instance_id)s' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
            'tenant_id': tenant_id,
            'instance_id': instance_id
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    return r


@proxy.route('/ping', methods=['GET'])
def ping():
    sys.stdout.write('Ping called/n')
    return ("Greetings from faas-configuration-service! "
            "OSM Version: %s FaaS Version: %s\n" %
            (OSM_VERSION, FAAS_VERSION))


@proxy.route('/conf', methods=['GET'])
def get_config_all():
    response = flask.jsonify(ns_configuration)
    response.status_code = 200
 
    return response


def set_current_entry(ns, vnf, idx, params):
    """
    Creates or updates a "current" dynamic parameter entry for

    ns: network service
    vnf: vnf name
    idx: vnf index inside network service descriptor
    message: dict of key, value pair(s)
    """
    global c_ns_configuration
    vnfs = c_ns_configuration.setdefault(ns, {})
    idxes = vnfs.setdefault(vnf, {})
    # actual update
    e = idxes.setdefault(idx, {})
    e.setdefault('action_params', {}).update(params)


@proxy.route('/current_conf/<ns>/<vnf>/<idx>', methods=['DELETE'])
def delete_current_vnf_idx_entry(ns, vnf, idx):
    global c_ns_configuration
    try:
        del c_ns_configuration[ns][vnf][idx]
    except:
        pass

    print('c_ns_configuration *after* delete request '
          '(%(ns)s, %(vnf)s, %(idx)s): %(current_dict)s \n' %
          {
            'ns': ns,
            'vnf': vnf,
            'idx': idx,
            'current_dict': c_ns_configuration,
            })
    return ('OK', 200)


@proxy.route('/conf/<ns>/<vnf>/<idx>', methods=['POST'])
def create_config_entry(ns, vnf, idx):
    try:
        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')

        params = dict(message)
        vnf_params = {idx: params}
        global ns_configuration
        vnfs = ns_configuration.setdefault(ns, {})
        vnfs.setdefault(vnf, {}).update(vnf_params)
    
        print(ns_configuration)
        return ('OK', 200)

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/conf/<ns>/<vnf>/<idx>', methods=['GET'])
def get_config_entry(ns, vnf, idx):
    try:
        params = ns_configuration[ns][vnf][idx]
        response = flask.jsonify(params)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/conf/<ns>', methods=['GET'])
def get_config_ns(ns):
    try:
        data = ns_configuration[ns]
        response = flask.jsonify(data)
        response.status_code = 200

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/conf/<ns>', methods=['DELETE'])
def delete_config_ns(ns):
    global ns_configuration
    try:
        del ns_configuration[ns]
        return ('OK', 200)

    except KeyError as e:
        response = flask.jsonify({'error missing key': '%s' % str(e)})
        response.status_code = 404

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500

    print(response)
    return response


@proxy.route('/<tenant_name>/reconfigure/<instance_name>/<vnf_name>', methods=['POST'])
def reconfigure(tenant_name, instance_name, vnf_name):
    """
    Kick-off reconfigure orchestrator process.

    """
    try:
        parts = vnf_name.split('.')
        if len(parts) != 2:
            raise Exception(
                'Unable to determine vnf_name_base, index from '
                'provided vnf_name: %s. Aborting operation' % vnf_name)
        vnf_name_base = parts[0]
        idx = parts[1]

        message = flask.request.get_json(force=True, silent=True)
        if not message:
            raise Exception('Unable to parse data payload. Payload must be '
                            'passed as json')
        if message and not isinstance(message, dict):
            raise Exception('data payload is not a dictionary')
    
        value = dict(message)
        print ('reconfigure: received: %s' % value)
        coe_action_params = value.get('coe_action_params', {})

        def _error_response(msg, code=404):
            response = flask.jsonify({'error': msg})
            response.status_code = code
            return response

        r = _tenants_get()
        t = find(r.json()['tenants'], lambda t: t['name'] == tenant_name)
        if not t:
            return _error_response(
                'tenant_name %s does not exist' %
                str(tenant_name))

        r = _instances_get(t['uuid'])
        i = find(r.json()['instances'], lambda i: i['name'] == instance_name)
        if not i:
            return _error_response(
                'instance_name %s does not exist' % str(instance_name))            
        r = _instance_get(t['uuid'], i['uuid'])
        vnfr = find(r.json()['vnfs'], lambda v: v['vnf_name'] == vnf_name)

        if not vnfr:
            return _error_response(
                'vnf \'%s\' not found in network service \'%s\'' %
                (vnf_name, instance_name))

        if not vnfr.get('datacenter_id'):
            return _error_response(
                'Unable to determine datacenter_id from vnf \'%s\'. ' %
                vnf_name)
        datacenter_id = vnfr['datacenter_id']

        vnfr_vm = vnfr['vms'][0]
        if not vnfr_vm.get('vim_info'):
            return _error_response(
                'Unable to determine vim_info from vnf \'%s\'. ' %
                vnf_name)

        vim_info = json.loads(vnfr_vm['vim_info'])

        pod_phase = vim_info.get('pod_phase', 'Unknown')
        if pod_phase != 'Running' or vnfr_vm['status'] != 'ACTIVE':
            return _error_response(
                'FaaS VNF pod not in running/active state.'
                'Error: %s' % vnfr_vm.get('error_msg', 'Not reported'),
                code=500)
        flowId = vim_info['flowId']
        activationId = vnfr_vm[RO_LABEL_VIM_VM_ID]

        r = _datacenter_get(t['uuid'], datacenter_id)
        datacenter = r.json().get('datacenter', {})
        owAPIHost = datacenter.get('vim_url')
        if not owAPIHost:
            return _error_response(
                'Unable to determine vim_url from datacenter %s.' %
                datacenter['name'])

        auth_token = datacenter.get('config', {}).get('auth_token')
        if not auth_token:
            return _error_response(
                'Unable to determine auth_token from datacenter %s.' %
                datacenter['name'])
        #owb64APIKey = base64.b64encode(auth_token.encode()).decode()

        offloadService = datacenter.get('config', {}).get('offload-service-url')
        if not offloadService:
            return _error_response(
                'Unable to determine offload-service-url from datacenter %s.' %
                datacenter['name'])

        headers = {'Content-Type': 'application/json'}
        annotations = coe_action_params.get('annotations', [])
        if annotations:
            action = vim_info.get('action')
            if not action:
                return _error_response('action not found in vim_info')

            print('Applying VIM configuration...\n')
            try:
                p = ns_configuration[instance_name][vnf_name_base][idx]['action_params']
            except Exception as e:
                p = {}
                print('Unable to retrieve persisted day0 parameters for '
                      'vnf_name: \'%s\' :0( error: %s\n' % (vnf_name, str(e)))
            params = coe_action_params.setdefault('action_params', {})

            '''
            These params considered 'dynamic' params in a sense, thus update
            'current' with these
            '''
            set_current_entry(instance_name, vnf_name_base, idx, params)
            print ('Successfully update current entry: %s\n' %
                   c_ns_configuration[instance_name][vnf_name_base][idx])


            add_p = dict((k, p[k]) for k, v in p.iteritems() if k not in params)
            params.update(add_p)
            # update with current overriding any exiting key
            try:
                c_p = c_ns_configuration[instance_name][vnf_name_base][idx]['action_params']
            except Exception as e:
                c_p= {}
                print('Unable to retrieve current parameters for '
                      'vnf_name: \'%s\' :0( error: %s\n' % (vnf_name, str(e)))
            params.update(c_p)
            params.update(dict(_VNF_IDX=idx))
            print('Final parameters including current and persisted day0: %s \n' % params)

            payload = {
                'flowId': flowId,
                'activationId': activationId, 
                'action' : action,
                'coe_action_params': coe_action_params,
                'owAPIHost' : owAPIHost,
                'owAPIKey' : auth_token
            }
            # async
            r = requests.post(offloadService+'/reconfigure',
                              headers=headers, json={'value' : payload})
            if 400 <= r.status_code < 600:
                raise Exception(r.text)
            print('Applying Done\n')

        else:
            host_ip = vim_info['host_ip']
            port = vim_info['service']['service_ports'][VNF_CONF_PORT]
            url = 'http://'+host_ip+':'+str(port)+'/conf/'

            print('Applying day 1 configuration to url %s...' % url)
            params = coe_action_params.get('action_params', {})
            for k in params:
                print('Push: \'%s\', \'%s\'' % (k, params[k]))
                r = requests.post('%s%s' % (url, k),
                    headers=headers, json={'value' : params[k]})
                if 400 <= r.status_code < 600:
                    raise Exception(r.text)
            print('Applying Done\n')
            set_current_entry(instance_name, vnf_name_base, idx, params)
            print ('Successfully update current entry: %s\n' %
                   c_ns_configuration[instance_name][vnf_name_base][idx])

        return ('OK', 200)

    except Exception as e:
        response = flask.jsonify({'error': '%s' % str(e)})
        response.status_code = 500
        return response


#############  WORKAROUND FOR RETRIEVING FAAS VNFR DATA BEGIN ###############

@proxy.route('/tenants', methods=['GET'])
def tenants_get():
    r = _tenants_get()

    response = flask.jsonify(r.json())
    response.status_code = 200
    return response


@proxy.route('/<tenant_id>/vnfs', methods=['GET'])
def vnfs_get(tenant_id):
    try:
        r = requests.get(
            'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/vnfs' %
            {
                'mano_host': mano_host,
                'mano_port': mano_port,
                'tenant_id': tenant_id,
            }, verify=False)
    
        print("requestAction: Received: %s" % r.text)
    
        r.raise_for_status()
        response = flask.jsonify(r.json())
        response.status_code = 200

    except HTTPError as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e.response)})

    return response


@proxy.route('/<tenant_id>/vnfs/<vnf_id>', methods=['GET'])
def vnf_get(tenant_id, vnf_id):
    try:
        r = requests.get(
            'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/vnfs/%(vnf_id)s' %
            {
                'mano_host': mano_host,
                'mano_port': mano_port,
                'tenant_id': tenant_id,
                'vnf_id': vnf_id,
            }, verify=False)

        response = flask.jsonify(r.json())
        response.status_code = 200

    except HTTPError as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e.response)})

    return response


@proxy.route('/<tenant_id>/instances', methods=['GET'])
def instances_get(tenant_id):
    try:
        r = _instances_get(tenant_id)

        response = flask.jsonify(r.json())
        response.status_code = 200

    except HTTPError as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e.response)})

    return response


@proxy.route('/<tenant_id>/instances/<instance_id>', methods=['GET'])
def instance_get(tenant_id, instance_id):
    try:
        r = _instance_get(tenant_id, instance_id)
    
        response = flask.jsonify(r.json())
        response.status_code = 200

    except HTTPError as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e.response)})

    return response


@proxy.route('/<tenant_id>/datacenters', methods=['GET'])
def datacenters_get(tenant_id):
    try:
        r = requests.get(
            'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/datacenters' %
            {
                'mano_host': mano_host,
                'mano_port': mano_port,
                'tenant_id': tenant_id,
            }, verify=False)
    
        print("requestAction: Received: %s" % r.text)
    
        r.raise_for_status()
        response = flask.jsonify(r.json())
        response.status_code = 200

    except HTTPError as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e.response)})

    return response


@proxy.route('/<tenant_id>/datacenters/<datacenter_id>', methods=['GET'])
def datacenter_get(tenant_id, datacenter_id):
    try:
        r = _datacenter_get(tenant_id, datacenter_id)

        response = flask.jsonify(r.json())
        response.status_code = 200

    except HTTPError as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e.response)})

    return response


@proxy.route('/<tenant_name>/<instance_name>', methods=['GET'])
def instance_get_single(tenant_name, instance_name):
    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/tenants' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    t = find(r.json()['tenants'], lambda t: t['name'] == tenant_name)
    if not t:
        response = flask.jsonify({'error': 'tenant_name %s does not exist'
                                  % str(tenant_name)})
        response.status_code = 404
        return response

    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/instances' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
            'tenant_id': t['uuid'],
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    i = find(r.json()['instances'], lambda i: i['name'] == instance_name)
    if not i:
        response = flask.jsonify({'error': 'instance_name %s does not exist'
                                  % str(instance_name)})
        response.status_code = 404
        return response

    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/instances/%(instance_id)s' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
            'tenant_id': t['uuid'],
            'instance_id': i['uuid']
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    result = _from_nsr_to_result(r)

    response = flask.jsonify(result)
    response.status_code = 200
    return response


@proxy.route('/<tenant_name>/instances_all', methods=['GET'])
def vnf_instances_all(tenant_name):
    results = []
    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/tenants' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
        }, verify=False)

    print("requestAction: Received: %s" % r.text)

    r.raise_for_status()
    t = find(r.json()['tenants'], lambda t: t['name'] == tenant_name)
    if not t:
        response = flask.jsonify({'error': 'tenant_name %s does not exist'
                                  % str(tenant_name)})
        response.status_code = 404
        return response

    r = requests.get(
        'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/instances' %
        {
            'mano_host': mano_host,
            'mano_port': mano_port,
            'tenant_id': t['uuid'],
        }, verify=False)

    print("requestAction: Received: %s" % r.text)
    r.raise_for_status()

    for instance in r.json()['instances']:
        r = requests.get(
            'http://%(mano_host)s:%(mano_port)s/openmano/%(tenant_id)s/instances/%(instance_id)s' %
            {
                'mano_host': mano_host,
                'mano_port': mano_port,
                'tenant_id': t['uuid'],
                'instance_id': instance['uuid']
            }, verify=False)
        print("requestAction: Received: %s" % r.text)
        r.raise_for_status()
        result = _from_nsr_to_result(r)
        results.append(result)

    response = flask.jsonify(results)
    response.status_code = 200
    return response

#############  WORKAROUND FOR RETRIEVING FAAS VNFR DATA END ###############


if __name__=="__main__":
    if not mano_host:
       raise Exception ('OSM_RO_HOSTNAME not set!')

    print ('starting tiny micro-service with conf: '
           'osm host: %s, port: %s, tenant: %s, \nlistening on port %s...' %
           (mano_host, mano_port, 'osm', conf_port))

    server = WSGIServer(('', int(conf_port)), proxy, log=None)
    server.serve_forever()

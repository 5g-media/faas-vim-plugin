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
import logging
import os
import re
import requests
from requests.exceptions import HTTPError
import vimconn
import urllib
import uuid


OSM_VERSION = "v5.0.5_220e83e"
FAAS_VERSION = "v2.0.6"


ANNOTATION_LABELS = 'labels'
ANNOTATION_PLACEMENT = 'placement'


URL_NOPORT_REGEX = re.compile('https?:\/\/[^:\/]+')


actionStatus2manoFormat = {
    'not found': 'ACTIVE',
    'success': 'INACTIVE',
    'application error': 'ERROR',
    'developer error': 'ERROR',
    'whisk internal error': 'ERROR'
}


def _raise_if_api_exception(resp):
    if 400 <= resp.status_code < 500 or 500 <= resp.status_code < 600:
        try:
            error_data = resp.json()['response']['result']['error']
        except:
            error_data = resp.content
        # should be the same exception as in r.raise_for_status
        raise HTTPError('Error: %s . Status: %s' %
                        (error_data, str(resp.status_code)), response=resp)


def generate_unicode_uuid(seed=None):
    """
    Generate random uuid or else, if seed supplied then generate it from seed.

    :param seed: Seed (string) have the uuid to be generated from
    :type seed: ``str``
    """
    if not seed:
        return unicode(str(uuid.uuid4()))
    else:
        return unicode(str(uuid.uuid3(uuid.NAMESPACE_DNS, seed)))


vim_flavor_id = generate_unicode_uuid()
image_annotation_key = 'image_id'


LOG_PREFIX = ">>>>>>>>> " + OSM_VERSION + " " + FAAS_VERSION


def find(l, predicate):
    """
    Utility function to find element in given list
    """
    results = [x for x in l if predicate(x)]
    return results[0] if len(results) > 0 else None


def parseQName(qname, namespace):
    delimiter = '/'
    if len(qname) > 0 and qname[0] == delimiter:
        parts = qname.split(delimiter)
        namespace = parts[1]
        name = delimiter.join(parts[2:]) if len(parts) > 2 else ''
    else:
        name = qname
    return (namespace, name)


def validate_action_name(action_name):
    """
    Utility method to validate that action name comprises out from:
    namespace, package name and action name itself.
    """
    parts = action_name.split('/')
    if len(parts) != 4:
        raise Exception (
            "Action name '%s' in wrong format."
            " Should be fully qualified (i.e. /<namespace>/<package>/<action>)" %
            action_name)


def clearCurrentParameters(logger, configAPIHost, name):
    """
    Clear current dynamic parameters for vnf denoted by the name parameter

    :param configAPIHost: Url to configuration service
    :type configAPIHost: ``str``

    :param name: Fully qualified name of the vnf to invoke. OSM RO builds it
                 in the following format.
                 <ns_name>-<idx>-<vdu_name>-<idx_of_vm_in_vdu>

                 ns_name: The NS name as given as parameter in instantiate UI/CLI
                 (i.e. osm ns-create --ns_name)

                idx: The index of this VNFD in NS. This is the equivalent of
                     nsd:member-vnf-index of constituent-vnfd

                vdu_name: The VDU:name of the VNF

                idx_of_vm_in_vdu: ignored

                Example: star_balls-2-5G MEDIA vTranscoder VM-1
    :type name: ``str``

    """
    parts = name.split('-')
    if len(parts) != 4:
        raise Exception (
            "name '%s' in wrong format."
            " Should be in format (i.e. <ns_name>-<idx>-<vduname>-<idx of vm in vdu>)" %
            name)
    ns_name = parts[0]
    idx = parts[1]
    vdu_name = parts[2]
    logger.debug(LOG_PREFIX + "clearCurrentParameters: '%(configAPIHost)s '" 
                "'%(ns_name)s' '%(vdu_name)s' '%(idx)s'" %
                {
                    'configAPIHost': configAPIHost,
                    'ns_name': ns_name,
                    'vdu_name': vdu_name,
                    'idx': idx
                })
    r = requests.delete(
        '%(configAPIHost)s/current_conf/%(ns_name)s/%(vdu_name)s/%(idx)s' %
        {
            'configAPIHost': configAPIHost,
            'ns_name': ns_name,
            'vdu_name': urllib.quote(vdu_name),
            'idx': idx,
        }, verify=False)

    logger.info(LOG_PREFIX + "clearCurrentParameters: Received: %s" % r.text)
    _raise_if_api_exception(r)

    #r.raise_for_status()
    return r


def requestParameters(logger, configAPIHost, name):
    """
    Get parameters for vnf denoted by the name parameter

    :param configAPIHost: Url to configuration service
    :type configAPIHost: ``str``

    :param name: Fully qualified name of the vnf to invoke. OSM RO builds it
                 in the following format.
                 <ns_name>-<idx>-<vdu_name>-<idx_of_vm_in_vdu>

                 ns_name: The NS name as given as parameter in instantiate UI/CLI
                 (i.e. osm ns-create --ns_name)

                idx: The index of this VNFD in NS. This is the equivalent of
                     nsd:member-vnf-index of constituent-vnfd

                vdu_name: The VDU:name of the VNF

                idx_of_vm_in_vdu: ignored

                Example: star_balls-2-5G MEDIA vTranscoder VM-1
    :type name: ``str``

    """
    parts = name.split('-')
    if len(parts) != 4:
        raise Exception (
            "name '%s' in wrong format."
            " Should be in format (i.e. <ns_name>-<idx>-<vduname>-<idx of vm in vdu>)" %
            name)
    ns_name = parts[0]
    idx = parts[1]
    vdu_name = parts[2]
    logger.debug(LOG_PREFIX + "requestParameters: '%(configAPIHost)s '" 
                "'%(ns_name)s' '%(vdu_name)s' '%(idx)s'" %
                {
                    'configAPIHost': configAPIHost,
                    'ns_name': ns_name,
                    'vdu_name': vdu_name,
                    'idx': idx
                })
    r = requests.get(
        '%(configAPIHost)s/conf/%(ns_name)s/%(vdu_name)s/%(idx)s' %
        {
            'configAPIHost': configAPIHost,
            'ns_name': ns_name,
            'vdu_name': urllib.quote(vdu_name),
            'idx': idx,
        }, verify=False)

    logger.info(LOG_PREFIX + "requestParameters: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


def requestAction(logger, owAPIHost, owb64APIKey, action_name):
    """
    Get the given action from openwhisk service denoted by owAPIHost

    NOTE: It is assumed that action name already validated by the caller

    :param owAPIHost: Url to OpenWhisk API endpoint
    :type owAPIHost: ``str``

    :param owb64APIKey: Authentication key in base64 format
    :type owb64APIKey: ``str``

    :param action_name: Fully qualified action name (e.g. /namespace/pkg/action)
    :type action_name: ``str``

    """
    logger.debug(LOG_PREFIX + "requestAction: '%(owAPIHost)s' '%(owb64APIKey)s' "
                 "'%(action_name)s'" %
                {
                    'owAPIHost': owAPIHost,
                    'owb64APIKey': owb64APIKey,
                    'action_name': action_name
                })
    
    parts = action_name.split('/')
    if len(parts) != 4:
        raise Exception (
            "Action name '%s' in wrong format."
            " Should be fully qualified (i.e. /<namespace>/<package>/<action>)" %
            action_name)

    headers = {'Authorization' : 'Basic %s' % owb64APIKey}
    r = requests.get(
        '%(owAPIHost)s/api/v1/namespaces/%(namespace)s/actions/'
        '%(package)s/%(action)s' %
        {
            'owAPIHost': owAPIHost,
            'namespace': parts[1],
            'package': parts[2],
            'action': parts[3],
        }, headers=headers, verify=False)

    logger.info(LOG_PREFIX + "requestAction: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


def invokeAction(logger, owAPIHost, owb64APIKey, action_name, blocking=False,
                 payload=None):
    """
    Invoke the given action on openwhisk service denoted by owAPIHost.
    Invocation is done asynch

    :param owAPIHost: Url to OpenWhisk API endpoint
    :type owAPIHost: ``str``

    :param owb64APIKey: Authentication key in base64 format
    :type owb64APIKey: ``str``

    :param action_name: Fully qualified action name (i.e. in this
                        format /namespace/pkg/action)
    :type action_name: ``str``

    :param blocking: Whether to wait for the action to complete. Default: False
    :type blocking: ``bool``

    :param payload: Data payload for key value action parameters (optional)
    :type payload: ``dict``

    :return: Request result containing code and text in json format
    """
    logger.debug(LOG_PREFIX + "invokeAction: '%(owAPIHost)s' '%(owb64APIKey)s' "
                 "'%(action_name)s' '%(payload)s'" %
                {
                    'owAPIHost': owAPIHost,
                    'owb64APIKey': owb64APIKey,
                    'action_name': action_name,
                    'payload': payload
                })

    parts = action_name.split('/')
    if len(parts) != 4:
        raise Exception ("Action name in wrong format."
                         " Should be fully qualified [action_name: %s]" %
                         action_name)

    headers = {'Content-Type' : 'application/json',
               'Authorization' : 'Basic %s' % owb64APIKey }
    r = requests.post(
        '%(owAPIHost)s/api/v1/namespaces/%(namespace)s/actions/'
        '%(package)s/%(action)s?blocking=%(blocking)s&result=false' %
        {
            'owAPIHost': owAPIHost,
            'namespace': parts[1],
            'package': parts[2],
            'action': parts[3],
            'blocking': 'true' if blocking else 'false'
        }, headers=headers, json=payload, verify=False)

    logger.info(LOG_PREFIX + "invokeAction: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


COMPLETION_TRIGGER = 'offloadComplete'


def invokeOffloadAction(logger, owAPIHost, owb64APIKey, action_name, ro_vim_vm_name,
                        offload_host, action_name_offloaded, payload=None):
    """
    Invoke the given action on kubernetes by having openwhisk to offloaf it.
    Invocation is done asynch

    :param owAPIHost: Url to OpenWhisk API endpoint
    :type owAPIHost: ``str``

    :param owb64APIKey: Authentication key in base64 format
    :type owb64APIKey: ``str``

    :param action_name: Fully qualified action name (i.e. in this
                        format /namespace/pkg/action) that *is responsible* to
                        off-load the given action
    :type action_name: ``str``

    :param offload_host: Url to k8s off-loader service
    :type offload_host: ``str``

    :param action_name_offloaded: Url to OpenWhisk API endpoint
    :type action_name_offloaded: ``str``

    :param payload: Data payload for key value container service action parameters
                    which include the following keys:
                    service_type (optional) - COE specific service type
                    service_ports (optional) - list of ports
                    action_params (optional) - actual action parameters
    :type payload: ``dict``

    :return: Request result containing code and text in json format
    """
    logger.debug(LOG_PREFIX + "invokeOffloadAction: '%(owAPIHost)s' "
                 "'%(owb64APIKey)s' '%(action_name)s' %(offload-service-url)s "
                 " %(action_name_offloaded)s '%(payload)s'" %
                {
                    'owAPIHost': owAPIHost,
                    'owb64APIKey': owb64APIKey,
                    'action_name': action_name,
                    'offload-service-url': offload_host,
                    'action_name_offloaded': action_name_offloaded,
                    'payload': payload
                })

    validate_action_name(action_name)
    parts = action_name.split('/')
    if len(parts) != 4:
        raise Exception ("Action name in wrong format."
                         " Should be fully qualified [action_name: %s]" %
                         action_name)

    validate_action_name(action_name_offloaded)
    payload_full = {}
    payload_full['ro_vim_vm_name'] = ro_vim_vm_name
    payload_full['offload-service-url'] = offload_host
    payload_full['completionTrigger'] = COMPLETION_TRIGGER
    payload_full['action'] = action_name_offloaded
    payload_full['coe_action_params'] = dict(payload)
    payload_full['url'] = owAPIHost
    headers = {'Content-Type' : 'application/json',
               'Authorization' : 'Basic %s' % owb64APIKey }
    logger.debug(LOG_PREFIX + "invokeOffloadAction: payload_full:%s" %
                 payload_full)

    r = requests.post(
        '%(owAPIHost)s/api/v1/namespaces/%(namespace)s/actions/'
        '%(package)s/%(action)s?blocking=false&result=false' %
        {
            'owAPIHost': owAPIHost,
            'namespace': parts[1],
            'package': parts[2],
            'action': parts[3],
        }, headers=headers, json=payload_full, verify=False)

    logger.info(LOG_PREFIX + "invokeOffloadAction: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


def requestActivation(logger, owAPIHost, owb64APIKey, activation_id):
    logger.debug(LOG_PREFIX + "requestActivation: '%(owAPIHost)s' '%(owb64APIKey)s' "
                 "'%(activation_id)s'" %
                {
                    'owAPIHost': owAPIHost,
                    'owb64APIKey': owb64APIKey,
                    'activation_id': activation_id
                })

    headers = {'Authorization' : 'Basic %s' % owb64APIKey}

    r = requests.get(
        '%(owAPIHost)s/api/v1/namespaces/_/activations/%(activation_id)s' %
        {
            'owAPIHost': owAPIHost,
            'activation_id': activation_id
        }, headers=headers, verify=False)

    logger.info(LOG_PREFIX + "requestActivation: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


def requestAnnotatedAction(logger, owAPIHost, owb64APIKey, offload_action,
                           annotation_key):
    """
    Return the fully qualified action name as denoted by the annotation key
    (i.e. get_pod, delete_pod, ..) out from the internal offload action.

    :param owAPIHost: Url to OpenWhisk API endpoint
    :type owAPIHost: ``str``

    :param owb64APIKey: Authentication key in base64 format
    :type owb64APIKey: ``str``

    :param action_name: Fully qualified action name (i.e. in this
                        format /namespace/pkg/action)
    :type action_name: ``str``

    :param annotation_key: The annotation key to retrieve
    :type annotation_key: ``str``

    """
    logger.debug(LOG_PREFIX + "requestAnnotatedAction: '%s' '%s'" %
                      (offload_action, annotation_key))    

    r = requestAction(logger=logger, owAPIHost=owAPIHost,
                      owb64APIKey=owb64APIKey, action_name=offload_action)
    r_json = r.json()
    namespace = r_json['namespace']

    a = find(r_json['annotations'], lambda a: a['key'] == annotation_key)
    annotated_action = a['value'] if a else ''
    logger.info(LOG_PREFIX + "requestAnnotatedAction: annoted_action: %s" %
                annotated_action)
    if not a:
        raise Exception('Annotation %s not found' % annotation_key)

    # HACK (for some reason namespace includes package too):
    parts = namespace.split('/')
    if len(parts) > 1:
        namespace = parts[0]
    qn = parseQName(annotated_action, namespace)
    actionFQN = '/'+qn[0]+'/'+qn[1]
    logger.info(LOG_PREFIX + "Exit requestAnnotatedAction: %s" %
                actionFQN)

    return actionFQN


def requestActions(logger, owAPIHost, owb64APIKey):
    """
    List actions per given authentication key which implies namespace

    :param owAPIHost: Url to OpenWhisk API endpoint
    :type owAPIHost: ``str``

    :param owb64APIKey: Authentication key in base64 format
    :type owb64APIKey: ``str``

    """
    logger.debug(LOG_PREFIX + "requestActions: '%(owAPIHost)s' '%(owb64APIKey)s'"
                 %
                {
                    'owAPIHost': owAPIHost,
                    'owb64APIKey': owb64APIKey
                })

    headers = {'Authorization' : 'Basic %s' % owb64APIKey}

    r = requests.get(
        '%(owAPIHost)s/api/v1/namespaces/_/actions?limit=100&skip=0' %
        {
            'owAPIHost': owAPIHost
        }, headers=headers, verify=False)

    logger.info(LOG_PREFIX + "requestActions: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


def updateActionAnnotation(logger, owAPIHost, owb64APIKey, action_name,
                           annotation_key, annotation_value):
    """
    Updates a given action with provided annotation.

    :param owAPIHost: Url to OpenWhisk API endpoint
    :type owAPIHost: ``str``

    :param owb64APIKey: Authentication key in base64 format
    :type owb64APIKey: ``str``

    :param action_name: Fully qualified action name (i.e. in this
                        format /namespace/pkg/action)
    :type action_name: ``str``

    :param annotation_key: The annotation name
    :type annotation_key: ``str``

    :param annotation_value: The annotation value
    :type annotation_value: ``str``

    """
    logger.debug(LOG_PREFIX + "updateActionAnnotation: '%(owAPIHost)s' "
                 "'%(owb64APIKey)s' '%(action_name)s' '%(annotation_key)s' "
                 "'%(annotation_value)s'"
                 %
                {
                    'owAPIHost': owAPIHost,
                    'owb64APIKey': owb64APIKey,
                    'action_name': action_name,
                    'annotation_key': annotation_key,
                    'annotation_value': annotation_value
                })

    parts = action_name.split('/')
    if len(parts) != 4:
        raise Exception ("Action name in wrong format."
                         " Should be fully qualified [action_name: %s]" %
                         action_name)
    r = requestAction(logger, owAPIHost, owb64APIKey, action_name)
    r_json = r.json()
    annotations = [{
        'key': annotation_key,
        'value': annotation_value
    }]
    a = find(r_json['annotations'], lambda a: a['key'] == ANNOTATION_PLACEMENT)
    if a:
        annotations.append(a)
    namespace = parts[1]
    package = parts[2]
    action = parts[3]
    payload = {
        # e.g "namespace":"guest"
        'namespace': namespace,
        # e.g. "name":"5g-media/action_ping"
        'name': '/'.join([package, action]),
        # e.g. "annotations":[{"key":"image_id","value":"1234-abcd"}]
        'annotations': annotations
    }
    headers = {'Content-Type' : 'application/json',
               'Authorization' : 'Basic %s' % owb64APIKey }
    # REMOVE...
    # [PUT]   https://172.15.0.50/api/v1/namespaces/guest/actions/5g-media/action_ping?overwrite=true
    r = requests.put(
        '%(owAPIHost)s/api/v1/namespaces/%(namespace)s/actions/'
        '%(package)s/%(action)s?overwrite=true' %
        {
            'owAPIHost': owAPIHost,
            'namespace': namespace,
            'package': package,
            'action': action
        }, headers=headers, json=payload, verify=False)

    logger.info(LOG_PREFIX + "updateActionAnnotation: Received: %s" % r.text)
    _raise_if_api_exception(r)

    # r.raise_for_status()
    return r


def flannel_network_spec(network_id, network_name):
    """
    Returns hard coded specification of the flannel network specification
    """
    spec = {
        'port_security_enabled': True,
        'provider:network_type': u'vxlan',
        'id': network_id,
        'type': 'bridge',
        'status': 'ACTIVE',
        'description': 'Flannel network',
        'segmentation_id': 1,
        'encapsulation': 'vxlan',
        'provider:segmentation_id': 1,
        'name': network_name,
        'mtu': 1450,
        'subnets': []
    }
    return spec


class vimconnector(vimconn.vimconnector):
    def __init__(self, uuid, name, tenant_id, tenant_name, url, url_admin=None,
        user=None, passwd=None, log_level=None, config={}, persistent_info={}):
        """
        Instantiate FaaS VIM using given datacenter parameters

        :param name: Name of this VIM instance
        :param tenant_name: Openwhisk namespace
        :param url: Url to openwhisk API
        :param passwd: Just something not relevant. Openwhisk authentication
                       token can't fit here due to database row length limit.
                       config is used instead.
        :param config: Additional configuration for this VIM such as
                       url of k8s off-loader service, the off-load action and
                       authentication token.
        """
        self.logger = logging.getLogger('openmano.vim.faas')
        if log_level:
            self.logger.setLevel( getattr(logging, log_level))

        self.logger.debug(
            LOG_PREFIX + "Initializing faas VIM with: '%(uuid)s'  '%(name)s' "
            "'%(tenant_id)s' '%(tenant_name)s' '%(url)s' '%(url_admin)s' "
            "'%(user)s' '%(passwd)s' '%(log_level)s' '%(config)s' "
            "'%(persistent_info)s'" %
            {
                 'uuid': uuid, 'name': name,
                 'tenant_id': tenant_id,
                 'tenant_name': tenant_name,
                 'url': url, 'url_admin': url_admin,
                 'user': user, 'passwd': passwd,
                 'log_level': log_level,
                 'config': config,
                 'persistent_info': persistent_info
             })

        vimconn.vimconnector.__init__(self, uuid, name, tenant_id,
            tenant_name, url, url_admin, user, passwd, log_level, config)

        owAPIKey = self.config.get('auth_token')
        if not owAPIKey:
            raise vimconn.vimconnAuthException("auth_token is not specified")
        self.owb64APIKey = base64.b64encode(owAPIKey.encode()).decode()
        self.owAPIHost = url

        self.offload_host = self.config.get('offload-service-url')
        if not self.offload_host:
            raise vimconn.vimconnException("Offload-service is not specified")

        proxierPort = self.config.get('proxierPort')
        if not proxierPort:
            raise vimconn.vimconnException("proxierPort not specified")

        if not URL_NOPORT_REGEX.match(self.offload_host):
            raise vimconn.vimconnException("Error in processing offload-service-url")
        # append to base url (k8s master) the port
        self.proxierUrl = URL_NOPORT_REGEX.match(self.offload_host).group(0)+':'+str(proxierPort)
        self.logger.debug(LOG_PREFIX + "self.proxierUrl: %s" % self.proxierUrl)

        self.config_host = os.getenv("FAAS_CONF_CONNECT")
        if not self.config_host:
            raise vimconn.vimconnException("FAAS_CONF_CONNECT is not specified "
                                           "as env var")
        offload_action_name = self.config.get('offload-action')
        if not offload_action_name:
            raise vimconn.vimconnException("Offload action is not specified")

        try:
            validate_action_name(offload_action_name)
            delete_action = requestAnnotatedAction(
                self.logger, self.owAPIHost,
                self.owb64APIKey,
                offload_action_name,
                'delete_pod')
            delete_action_event = requestAnnotatedAction(
                self.logger, self.owAPIHost,
                self.owb64APIKey,
                offload_action_name,
                'delete_pod_event')
            get_action = requestAnnotatedAction(
                self.logger, self.owAPIHost,
                self.owb64APIKey,
                offload_action_name,
                'get_pod')
            nop_action = requestAnnotatedAction(
                self.logger, self.owAPIHost,
                self.owb64APIKey,
                offload_action_name,
                'nop')
            event_action = requestAnnotatedAction(
                self.logger, self.owAPIHost,
                self.owb64APIKey,
                offload_action_name,
                'get_pod_event')
        except Exception as e:
            raise vimconn.vimconnException("Error validating action %s: %s" %
                                           (offload_action_name, str(e)))
        self.offload = {
            'offload_action': offload_action_name,
            'get_action': get_action,
            'delete_action': delete_action,
            'delete_action_event': delete_action_event,
            'nop_action': nop_action,
            'get_action_event': event_action
        }

        self.persistent_info = persistent_info
        self.persistent_info.setdefault('actions', {})
        self.persistent_info.setdefault('network', {})

    def get_flavor(self, flavor_id):
        self.logger.debug(LOG_PREFIX + "Getting flavor from VIM id: '%s'",
                          str(flavor_id))
        # RO just checks whether this flavor exists in VIM. It is N/A in OW.
        # Just return same id here.
        return {'id': flavor_id, 'name': 'openwhisk_flavor'}

    def get_flavor_id_from_data(self, flavor_dict):
        self.logger.debug(LOG_PREFIX + "Getting flavor from VIM data: '%s'",
                          str(flavor_dict))
        # RO does not find flavor in its DB. Flavor is N/A in OW. Just
        # return a dummy ID.
        return vim_flavor_id

    def get_image_id_from_path(self, path):
        """
        For FaaS VIM, image name is the fully qualified name of the action.
        Because of that RO thinks image name is a pathname and calls this
        method.

        Note: In case action not found, vimconnException exception get thrown
        so that RO does not try to create it. Remember, FaaS does not manage
        images
        """
        self.logger.debug(LOG_PREFIX + "get_image_id_from_path: '%s'", path)
        action_name = path
        try:
            validate_action_name(action_name)
            r = requestAction(self.logger, self.owAPIHost, self.owb64APIKey,
                              action_name)
            r_json = r.json()
        except HTTPError as http_error:
            if http_error.response.status_code == 404:
                raise vimconn.vimconnException(
                    "Action name '{}' not found".format(action_name))
            else:
                raise vimconn.vimconnException(str(http_error))
        except Exception as e:
            raise vimconn.vimconnException(str(e))

        a = find(r_json['annotations'], lambda a: a['key'] == image_annotation_key)
        image_id = a['value'] if a else ''
        self.logger.info(LOG_PREFIX + "get_image_id_from_path: "
                    "'%(image_annotation_key)s': '%(image_id)s'" %
                    {
                        'image_annotation_key': image_annotation_key,
                        'image_id': image_id
                    })
        if not image_id:
            image_id = generate_unicode_uuid(seed=action_name)
            self.logger.debug(
                LOG_PREFIX + "get_image_id_from_path: No image_id found for action: "
                "%(action_name)s. Generated new uuid: %(image_id)s" %
                {
                    'action_name': action_name,
                    'image_id': image_id
                 }
            )
            updateActionAnnotation(
                self.logger, self.owAPIHost, self.owb64APIKey, action_name,
                image_annotation_key, image_id)

        return image_id

    def get_image_list(self, filter_dict={}):
        # TODO: Is it a dead code?
        """
        RO passes the name of the image set in vnfd:vdu
        For FaaS VIM, image name is the fully qualified name of the action.

        In OW we do not have the uuid of the action. Thus we fake such a one
        here (if does not exist) and store it under persistent_info dictionary
        managed by RO.

        That uuid will be passed in `new_vminstance` and we use the
        persistent_info mapping to retrieve back action name

        :param filter_dict: Filtering dictionary that contains the fully
                            qualified name of the action
        :type filter_dict: ``dict``

        :return: ``list`` of single action uuid, empty list if action not
                found
        """
        self.logger.debug(LOG_PREFIX + "get_image_list: filter_dict: '%s'",
                          filter_dict)

        action_name = filter_dict['name']
        try:
            validate_action_name(action_name)
        except Exception as e:
            raise vimconn.vimconnException("Error validating action: %s" %
                                           str(e))

        try:
            requestAction(self.logger, self.owAPIHost, self.owb64APIKey,
                          action_name)
        except Exception as e:
            self.logger.error(
                LOG_PREFIX + "Error occurred during action retrieval: %s" %
                str(e))
            image_list = []
        else:
            action_uuid = self.persistent_info['actions'].get(action_name)
            if not action_uuid:
                action_uuid = generate_unicode_uuid()
                self.persistent_info['actions'][action_name] = action_uuid
    
                self.logger.debug(
                    LOG_PREFIX + "get_image_list: No uuid found for action: "
                    "%(action_name)s. Generated new uuid: %(action_uuid)s" %
                    {
                        'action_name': action_name,
                        'action_uuid': action_uuid
                     }
                )

            image_list = [{'id': action_uuid}]

        self.logger.debug(
            LOG_PREFIX + "get_image_list: RETURN '%s'" % image_list)

        return image_list

    def new_network(self,net_name, net_type, ip_profile=None, shared=False,
                    vlan=None):
        self.logger.debug(LOG_PREFIX + "new_network: '%(name)s' "
                          "net_type: '%(net_type)s' "
                          "ip_profile: '%(ip_profile)s' shared: '%(shared)s'"
                          " vlan: '%(vlan)s'" %
            {
                'name': net_name,
                'net_name': net_name,
                'net_type': net_type,
                'ip_profile': ip_profile,
                'shared': shared,
                'vlan': vlan
            }
        )
        net_id = self.persistent_info['network'].setdefault(
            'vim_network_id', generate_unicode_uuid())
        return net_id

    def get_network_list(self, filter_dict={}):
        self.logger.debug(LOG_PREFIX + "get_network_list: %s" % filter_dict)

        net_id = self.persistent_info['network'].setdefault(
            'vim_network_id', generate_unicode_uuid())
        #TODO: if name supplied then take from filter_dict and generate uui out from
        # name
        n_l = [flannel_network_spec(net_id, 'default.network_test.vld-1')]
        return n_l

    def get_network(self, net_id):
        self.logger.debug(LOG_PREFIX + "get_network: %s" %
                          net_id)

        return flannel_network_spec(net_id, 'default.network_test.vld-1')

    def delete_network(self, net_id):
        self.logger.debug(LOG_PREFIX + "delete_network: %s" %
                          net_id)

        if self.persistent_info['network'].get('vim_network_id'):
            self.logger.debug(LOG_PREFIX + "delete_network: "
                              "Deleted network from FaaS VIM. net_id: %s" %
                              net_id)
            del self.persistent_info['network']['vim_network_id']

        return net_id

    def refresh_nets_status(self, net_list):
        self.logger.debug(LOG_PREFIX + "refresh_nets_status: %s" % net_list)
        network_id = net_list[0]
        net_dict = {
            network_id: flannel_network_spec(network_id,
                'default.network_test.vld-1')
        }
        self.logger.debug(LOG_PREFIX + "EXIT. refresh_nets_status: %s" %
                          net_dict)

        return net_dict

    def new_vminstance(self, name, description, start, image_id, flavor_id,
                       net_list, cloud_config=None, disk_list=None,
                       availability_zone_index=None,
                       availability_zone_list=None):
        """
        Parameters relevant for us:

        :param name: automatically generated by RO.
        :param image_id: uuid to be used to retrieve the fully qualified action
                         name to invoke.
        :param net_list: TBD
        :param cloud_config: contains user-data in json format containing
                             key/val parameter list (Optional)
        
        :return: activation_id of the invoked action. This is the activation
                 id of the `offload` action invocation. It contains the relation
                 to the flowId, the handle to the k8s action. For OSM this is
                 the vm_id.
                 created_items also returned. It includes key-value mapping
                 of application ports and the ones exposed via kubernetes service.
                 Note that according to OSM documenration it should not use
                 nested dictionaries.
        """
        self.logger.debug(
            LOG_PREFIX + "new_vminstance: name: %(name)s, "
            "description : %(description)s, "
            "start: %(start)s, image_id: %(image_id)s, "
            "flavor_id: %(flavor_id)s, net_list: %(net_list)s, "
            "cloud_config: %(cloud_config)s, "
            "disk_list=%(disk_list)s, "
            "availability_zone_index: %(availability_zone_index)s, "
            "availability_zone_list: %(availability_zone_list)s " %
            {
                'name': name,
                'description': description,
                'start': start,
                'image_id': image_id,
                'flavor_id': flavor_id,
                'net_list': net_list,
                'cloud_config': cloud_config,
                'disk_list': disk_list,
                'availability_zone_index': availability_zone_index,
                'availability_zone_list': availability_zone_list,
             }
        )
        # required for upper layer
        try:
            for net in net_list:
                net['vim_id'] = self.persistent_info['network']['vim_network_id']
                net['mac_address'] = None
                net["ip"] = '1.2.3.4'

            r = requestActions(self.logger, self.owAPIHost, self.owb64APIKey)
            r_json = r.json()
            found_id = False
            for ac in r_json:
                a = find(ac['annotations'], lambda e: e['value'] == image_id)
                if a:
                    found_id = True
                    my_ac = ac
                    break
            if not found_id:
                raise Exception("Unable to find action_name out from "
                                "image_id %s" % image_id)
            
            action_name = '/' + my_ac['namespace'] + '/' + my_ac['name']
            validate_action_name(action_name)
            self.logger.debug(
                LOG_PREFIX + "Found action name %s. We are happy :-)" %
                action_name)

            ud = {}
            user_data = None if cloud_config is None else \
                cloud_config.get('user-data')

            if user_data and len(user_data) == 1:
                ud = json.loads(user_data[0])

            params = {}
            try:
                r = requestParameters(logger=self.logger, configAPIHost=self.config_host,
                                      name=name)
                params = r.json()
            except Exception as e:
                self.logger.error("Failed to retireve action parameters for %s. "
                                  "Exception: %s. SENDING EMPTY PARAMS" %
                                  (name, str(e)))

            clearCurrentParameters(
                logger=self.logger, configAPIHost=self.config_host, name=name)
            ud['action_params'] = params.get('action_params', {})
            ud['service_ports'] = params.get('service_ports', [])

            # should work due to upper path validation
            ud['action_params'].update(dict(_VNF_IDX=name.split('-')[1]))
            try:
                '''
                Examine cloud-init of vnfd.
                Explicit start=false means event-based vnf. nop action is called with
                the full ro name. Full ro name is used to correlate the pod by `refresh_vms_status`
                If explicit bootstrap=true then call the bootstrap action to deploy VNFM
                Otherwise normal offload is being invoked
                '''
                if ud.get('start', 'True').lower() in ['true']:
                    if ud.get('start'):
                        del ud['start']
                    if ud.get('bootstrap', 'False').lower() in ['true']:
                        if ud.get('bootstrap'):
                            del ud['bootstrap']
                        r = invokeAction(self.logger, self.owAPIHost, self.owb64APIKey,
                            action_name=action_name, blocking=False,
                            # ok to split. Validation occurd before
                            payload={'ns_name': name.split('-')[0],
                                     'operation': 'create',
                                     'proxierUrl': self.proxierUrl})
                    else:
                        r = invokeOffloadAction(
                            logger=self.logger, owAPIHost=self.owAPIHost,
                            owb64APIKey=self.owb64APIKey,
                            action_name=self.offload['offload_action'],
                            ro_vim_vm_name=name,
                            offload_host=self.offload_host,
                            action_name_offloaded=action_name,
                            payload=ud)
                else:
                    r = invokeAction(self.logger, self.owAPIHost, self.owb64APIKey,
                        action_name=self.offload['nop_action'],
                        blocking=False, payload={'ro_vim_vm_name': name, '_start': 'false'})

                r_json = r.json()
                activation_id = r_json['activationId']
                self.logger.debug(LOG_PREFIX + "Activation ID: '%s'" %
                                  activation_id)
                return activation_id, {'Foo': 'Bar'}

            except Exception as e:
                self.logger.error("Failed to invoke action %s. Exception: %s" %
                                  (action_name, str(e)))
                raise e

        except Exception as e:
            raise vimconn.vimconnException(
                'Error occurred during action invocation. %s: ' % str(e))

    def refresh_vms_status(self, vm_list):
        self.logger.debug(LOG_PREFIX + "refresh_vms status: %s" % vm_list)
        net_id = self.persistent_info['network'].setdefault(
            'vim_network_id', generate_unicode_uuid())

        vm_dict={}

        # TODO: currently its all or nothing
        for vm_id in vm_list:
            vm = {}
            activation_id = vm_id
            status = 'not found' # mapped to active
            mac_address = '00:00:00:00:00:00' # see if pod has mac
            pod_ip = '0.0.0.0'
            vim_info = dict()
            ports = {}
            try:
                try:
                    r = requestActivation(self.logger, self.owAPIHost,
                                          self.owb64APIKey, activation_id)
                except HTTPError as http_error:
                    if http_error.response.status_code == 404:
                        self.logger.debug("Activation id '%s' not found. "
                                          "Assuming action is running"
                                          % activation_id)
                        # no activation found means action still running
                        vm['status'] = actionStatus2manoFormat[status]
                # we have r in hand, proceed..
                else:
                    r_json = r.json()
                    if not r_json.get('response', {}).get('status'):
                        raise Exception("Malformed activation result %s. Missing "
                                        "'response' and/or 'status' key" %
                                        r_json)

                    result = r_json['response']['result']
                    '''
                    In case of bootstrap activation record, retrieve ingress
                    URL of its gateway/sensor subsystem
                    '''
                    if result.get('_bootstrap', 'False').lower() in ['true'] and \
                        result.get('IngressPort'):

                        ingressPort = result.get('IngressPort')
                        vim_info['IngressUrl'] = '%s:%s' % (
                            URL_NOPORT_REGEX.match(self.offload_host).group(0),
                            str(ingressPort))
                    else:
                        '''
                        It can either be normal activation record or event-based
                        nop activation record with (start=false).
                        In case of normal, retrieve flowId and pass it to get_pod action
                        In case of event-based, retrieve full ro name and pass it
                        to get_pod_event action
                        '''
                        flowId = None
                        if result.get('detail', {}).get('flowId'):
                            flowId = result['detail']['flowId']

                            r = invokeAction(
                                    self.logger, self.owAPIHost,
                                    self.owb64APIKey,
                                    action_name=self.offload['get_action'],
                                    blocking=True,
                                    payload={
                                        'offload-service-url': self.offload_host,
                                        'flowId': flowId
                                    }
                                )
                        elif result.get('_start', 'True').lower() in ['false']:
                            ro_vim_vm_name = result.get('ro_vim_vm_name')
                            vim_info['_start'] = result.get('_start')
                            r = invokeAction(
                                    self.logger, self.owAPIHost,
                                    self.owb64APIKey,
                                    action_name=self.offload['get_action_event'],
                                    blocking=True,
                                    payload={
                                        'offload-service-url': self.offload_host,
                                        'ro_vim_vm_name': ro_vim_vm_name
                                    }
                                )

                        r_json = r.json()
                        if not r_json.get('response', {}).get('status'):
                            raise Exception("Malformed activation result %s. Missing "
                                            "'response' and/or 'status' key" %
                                            r_json)
                        '''
                        Common part for both record types
                        '''
                        result = r_json['response']['result']
                        # add or to overcome none values
                        if result.get('_exists', 'true') == 'true':
                            if result.get('records'):
                                vim_info['records'] = result['records']
                            else:
                                pod_ip = result.get('pod_ip', '0.0.0.0') or '0.0.0.0'
                                vim_info['host_ip'] = result.get('host_ip', '0.0.0.0') \
                                    or '0.0.0.0'
                                vim_info['pod_phase'] = result.get('phase', 'unknown') \
                                    or 'unknown'
                                # flowId may not be set if we deal with nop activation, thus
                                # take it from the get_action_event result
                                vim_info['flowId'] = flowId if flowId else result.get('flowId', '')
                                vim_info['vim-id'] = result.get('vim-id')
                                vim_info['action'] = result.get('action', '')
                                vim_info['service'] = result.get('service', {}) or {}
                                ro_vim_vm_name = result.get('ro_vim_vm_name')
                                if ro_vim_vm_name:
                                    vim_info['ro_vim_vm_name'] = ro_vim_vm_name

                vim_info['pod_ip'] = pod_ip
                vm['vim_info'] = json.dumps(vim_info)

                vm['status'] = actionStatus2manoFormat[status]
                ips = [pod_ip]
                vm['interfaces'] = [
                    {
                        # 'vim_net_id': net_id,
                        'vim_interface_id': net_id,
                        'mac_address': mac_address,
                        'ip_address': ";".join(ips)
                    }
                ]

            except Exception as e:
                self.logger.error("Exception getting vm status: %s", str(e))
                vm['status'] = "VIM_ERROR"
                vm['error_msg'] = str(e)

            vm_dict[vm_id] = vm

        return vm_dict

    def delete_vminstance(self, vm_id, created_items=None):
        """
        Delete all resources created for this action. These include, job,
        service and pod.
        In addition, delete related argo resources

        :param vm_id: Action's activation id
        :type vm_id: ``str``
        """
        self.logger.debug(LOG_PREFIX + "delete_vminstance: %s" % vm_id)
        activation_id = vm_id

        # Swallow all errros. We do not want to fail delete.
        try:
            r = requestActivation(self.logger, self.owAPIHost,
                                  self.owb64APIKey, activation_id)
            r_json = r.json()
            if not r_json.get('response', {}).get('status'):
                raise Exception("Malformed activation result %s. Missing "
                                "'response' and/or 'status' key" %
                                r_json)

            # all activations include result
            result = r_json['response']['result']
            if result.get('detail', {}).get('flowId'):
                flowId = result['detail']['flowId']

                # blocking mode
                r = invokeAction(
                    self.logger, self.owAPIHost,
                    self.owb64APIKey,
                    action_name=self.offload['delete_action'],
                    blocking=True,
                    payload={
                        'offload-service-url': self.offload_host,
                        'flowId': flowId
                    }
                )

            elif result.get('_bootstrap', 'False').lower() in ['true']:
                '''
                In case of bootstrap activation record
                '''
                action_name = result['action_name']
                invokeAction(self.logger, self.owAPIHost, self.owb64APIKey,
                             action_name=action_name, blocking=False,
                             payload={'ns_name': result['ns_name'],
                                     'operation': 'delete',
                                     'proxierUrl': self.proxierUrl})

            elif result.get('_start', 'True').lower() in ['false']:
                '''
                In case of nop activation record
                '''
                ro_vim_vm_name = result.get('ro_vim_vm_name')
                # blocking mode
                invokeAction(
                    self.logger, self.owAPIHost,
                    self.owb64APIKey,
                    action_name=self.offload['delete_action_event'],
                    blocking=True,
                    payload={
                        'offload-service-url': self.offload_host,
                        'label_name': 'ro_vim_vm_name',
                        'label_value': ro_vim_vm_name
                    }
                )

        except Exception as e:
            self.logger.error(LOG_PREFIX + "Error deleting instance from VIM: %s" %
                              str(e))
        return None

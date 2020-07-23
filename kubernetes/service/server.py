"""Executable Python script for an OpenWhisk offload service.

Provides an offload service (using Flask, a Python web microframework)
that implements on action offload service for OpenWhisk.
The service is designed to be run as a service in a kubernetes cluster
 and executes the offloaded actions as kubernetes jobs in that cluster.
 
 Allows to specify node selector labels that influence scheduling, s.a., affinity and anti-affnity policies
 and allocation of nodes labeled to have specialized hardware, such as GPU.

/*
 * Copyright 2015 - 2020 IBM Corporation
 *
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
"""
import base64

import logging

import json
import os
import requests
import _thread
import time
import uuid
import re
import sys

import flask
from gevent.wsgi import WSGIServer
from werkzeug.exceptions import HTTPException

import kubernetes
from kubernetes import client,config

from kubernetes.client import V1Container
from kubernetes.client import V1ContainerPort
from kubernetes.client import V1EnvVar
from kubernetes.client import V1EnvVarSource
from kubernetes.client import V1Job
from kubernetes.client import V1JobSpec
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1PodSpec
from kubernetes.client import V1PodTemplateSpec
from kubernetes.client import V1Secret
from kubernetes.client import V1SecretKeySelector

from kubernetes.client import V1VolumeMount
from kubernetes.client import V1Volume

from kubernetes.client import V1Service
from kubernetes.client import V1ServiceSpec
from kubernetes.client import V1ServicePort

from kubernetes.client import V1LabelSelector
from kubernetes.client import V1LabelSelectorRequirement
from kubernetes.client import V1PodAffinityTerm
from kubernetes.client import V1PodAntiAffinity
from kubernetes.client import V1Affinity

from kubernetes.client import V1SecurityContext
from kubernetes.client import V1Capabilities


OSM_VERSION = "N/A"
FAAS_VERSION = "0.2.7"


ANNOTATION_PLACEMENT = 'placement'


# Linux has at least 128k for the entire environment;
# limit each entry to 32k so we stay under the 128k lower limit
MAX_LEN_ENVVAR = int(os.getenv("OW_OFFLOAD_LARGE_ARG_SIZE", '32768'))

# Should we preserve the state of failed jobs for debugging?
# Default to remove them in production
KEEP_FAILED_JOBS = "OW_OFFLOAD_KEEP_FAILED_JOBS" in os.environ

# Action's configuration port to expose. Must be alighned with action's conf
# microservice
CONF_SERVICE_PORT = int(os.getenv("CONF_SERVICE_PORT", '8081'))

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create console handler and add it to logger
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)

f_handler = logging.FileHandler('offloader.log')
f_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - \
%(levelname)s - %(message)s %(funcName)s %(pathname)s:%(lineno)d')

handler.setFormatter(formatter)
f_handler.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(f_handler)


PORT_UDP_REGEX = re.compile('([0-9]+)/(udp|UDP)')


def find(l, predicate):
    """
    Utility function to find element in given list
    """
    results = [x for x in l if predicate(x)]
    return results[0] if len(results) > 0 else None


def _from_service(service):
    """
    Helper method to build dictionary object out from service
    """
    service_ports = service.spec.ports
    app_ports = {}
    for p in service_ports:
        app_ports[int(p.port)] = int(p.node_port) if p.node_port else -1
    return {
        'name': service.metadata.name,
        'service_ports': app_ports
        #'cluster_ip': service.spec.cluster_ip,
        #'type': service.spec.type
    }


def _build_pod_antiaffinity(labels):
    """
    Generates pod anti-affinity based on the given labels.

    generated example (in yaml format):

    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: processor-required
            operator: In
            values:
            - gpu
          - key: storage-required
            operator: In
            values:
            - ssd
        topologyKey: kubernetes.io/hostname

    :param labels: dictionary of key, value pairs
    :type  labels: ``dict``
    :return: V1PodAntiAffinity with generated affinity term
    """
    label_selectors = []
    for k in labels:
        label_selectors.append(V1LabelSelectorRequirement(
            key=k, values=[labels[k]], operator='In'))
    
    affinity_term = V1PodAffinityTerm(
        label_selector=V1LabelSelector(match_expressions=label_selectors),
        topology_key='kubernetes.io/hostname')

    return V1PodAntiAffinity(
        required_during_scheduling_ignored_during_execution=[affinity_term])


def _action_from_pod(pod):
    """
    Internal helper to retrieve action name (stored as ENV VAR) inside action
    container and whether or not action container is terminated.

    This method handles a case where container does not exist (e.g. pod
    is in Init, Pending, Terminate, states)

    :return: tuple of terminate (boolean), action_name (str)
             Note: terminated true only when container explicitly set to
                   terminated.
    """
    terminated = False
    if pod.status.container_statuses:
        s = find(pod.status.container_statuses, lambda s: s.name =='ow-action')
        if s and s.state:
            terminated = True if s.state.terminated else False
        c = find(pod.spec.containers, lambda c: c.name =='ow-action')
        if not c:
            return None, terminated
        e = find (c.env, lambda e: e.name == '__OW_ACTION_NAME')
        if not e:
            return None, terminated
        return e.value, terminated
    else:
        return None, False


def _build_job(namespace, object_meta, node_selector, affinity,
                    invoker_image, action_image, invokerEnv, actionEnv,
                    params, action_timelimit, security_context):
    """
    Internal helper to build a Job spec out from the given parameters
    """
    pod_spec = V1PodSpec(
        containers= [
#             V1Container(
#                 image_pull_policy="IfNotPresent",
#                 image=invoker_image,
#                 name='ow-invoker',
#                 command=["python"],
#                 args=["-u", "/offloadServer/invoker.py"],
#                 env=invokerEnv
#             ),
            V1Container(
                image_pull_policy="Always",
                image=action_image,
                name='ow-action',
                env=actionEnv,
                command=["/action/exec"],
                args=[json.dumps(params)],
                volume_mounts=[V1VolumeMount(name='conf-volume',
                                             mount_path='/conf')],
                security_context=security_context
            ),
            V1Container(
                image_pull_policy="IfNotPresent",
                image=invoker_image,
                name='ow-conf',
                command=["python"],
                args=["-u", "/offloadServer/conf.py"],
                volume_mounts=[V1VolumeMount(name='conf-volume',
                                             mount_path='/conf')]
            )
        ],
        volumes=[V1Volume(name='conf-volume', empty_dir={})],
        restart_policy="Never",
        active_deadline_seconds=action_timelimit,
        node_selector=node_selector,
        affinity=affinity,
        termination_grace_period_seconds=1
    )
    job_spec = V1JobSpec(
        active_deadline_seconds=action_timelimit,
        completions=1,
        parallelism=1,
        template=V1PodTemplateSpec(
            spec=pod_spec,
            metadata=object_meta
        ),
    )
    return V1Job(spec=job_spec, metadata=object_meta)

#
# Parse a (possibly fully qualified) resource name into
# namespace and name components. If the namespace
# is missing from the qualified name, the argument namespace is used.
# Derived from wskutils.py in incubator-openwhisk-client-python.
#
# Return a (namespace, package+name) tuple.
#
# Examples:
#      foo => (_, foo)
#      pkg/foo => (_, pkg/foo)
#      /ns/foo => (ns, foo)
#      /ns/pkg/foo => (ns, pkg/foo)
#
def parseQName(qname, namespace):
    delimiter = '/'
    if len(qname) > 0 and qname[0] == delimiter:
        parts = qname.split(delimiter)
        namespace = parts[1]
        name = delimiter.join(parts[2:]) if len(parts) > 2 else ''
    else:
        name = qname
    return (namespace, name)


# Helper class to construct an offload request from an post to /offload
# Iteracts with OpenWhisk to authenticate request and obtain the code to run.
class OffloadRequest:
    """Offload Request."""

    def __init__(self, value):
        # relevant to reconfigure only
        self.flowId = value.get('flowId')

        self.owAPIHost = value.get('owAPIHost')
        if self.owAPIHost is None:
            flask.abort(400, 'Required parameter "owAPIHost" not provided')

        self.owAPIKey = value.get('owAPIKey')
        logger.info('API key: [%s]' % self.owAPIKey)
        if self.owAPIKey is None:
            flask.abort(400, 'Required parameter "owAPIKey" not provided')
        self.owb64APIKey = base64.b64encode(self.owAPIKey.encode()).decode()

        namespace = value.get('namespace', '_')
        action = value.get('action')
        if action is None:
            flask.abort(400, 'Required parameter "action" not provided')
        qn = parseQName(action, namespace)
        self.actionFQN = '/'+qn[0]+'/'+qn[1]
        self.actionURL = '/'+qn[0]+'/actions/'+qn[1]

        coe_action_params = value.get('coe_action_params', {})

        # relevant to reconfigure only
        self.annotations = coe_action_params.get('annotations', [])

        self.service_ports = coe_action_params.get('service_ports', [])
        if CONF_SERVICE_PORT not in self.service_ports:
            self.service_ports.append(CONF_SERVICE_PORT)

        self.service_type = coe_action_params.get('service_type', 'nodeport')
        if self.service_type:
            if self.service_type.lower() == 'nodeport':
                self.service_type = 'NodePort'
            elif self.service_type.lower() == 'clusterip':
                self.service_type = 'ClusterIP'
            else:
                raise Exception('Illegal service_type. Supported values: '
                                'ClusterIP, NodePort')

        self.params = coe_action_params.get('action_params', {})
        self.activationId = value.get('activationId', "42")
        self.ro_vim_vm_name = value.get('ro_vim_vm_name', "na")
        self.event_uuid = value.get('event_uuid', "na")
        self.params.update(dict(_VIM_VM_ID=self.activationId))

        self.endpoints = []
        completionTrigger = value.get('completionTrigger', None)
        if not completionTrigger is None:
            qn = parseQName(completionTrigger, namespace)
            self.endpoints.append('/'+qn[0]+'/triggers/'+qn[1])
        completionAction = value.get('completionAction', None)
        if not completionAction is None:
            qn = parseQName(completionAction, namespace)
            self.endpoints.append('/'+qn[0]+'/actions/'+qn[1])

        self.actionDef = None
        self.image = None
        self.code = None
        self.entry = None
        self.binary = None


    # Get action defintion from OpenWhisk (which also authenticates the request)
    def requestAction(self):
        r = requests.get(self.owAPIHost+'/api/v1/namespaces'+self.actionURL,
                         headers={'Authorization' : 'Basic %s' % self.owb64APIKey }, verify=False)
        if not r:
            flask.abort(r.status_code,
                        'Error while retrieving action %s' % self.actionFQN)
        return r.json()


    # Decode action definition and determine what we are being asked to do
    def decodeAction(self, actionDef):
        action = actionDef.get('exec')
        annotations = actionDef.get('annotations', [])
        element = find(annotations, lambda element: element['key']==ANNOTATION_PLACEMENT)
        if not element:
            self.placement = {}
        else:
            self.placement = element['value']

        # Use kind to determine image, code, binary and entry.
        kind = action.get('kind')
        if kind == 'blackbox':
            self.image = action.get('image')
        else:
            self.code = action.get('code')
            self.binary = action.get('binary')
            self.entry = action.get('main')
            if kind == 'nodejs:6' or kind == 'nodejs':
                self.image = 'openwhisk/nodejs6action'
                if self.entry is None:
                    self.entry = 'main' # nodejs6action container fails /init if main not explicitly specified
            elif kind == 'python:2' or kind == 'python':
                self.image = 'openwhisk/python2action'
            elif kind == 'python:3':
                self.image = 'openwhisk/python3action'
            elif kind == 'swift:3':
                self.image = 'openwhisk/swift3action'
            elif kind == 'java':
                self.image = 'openwhisk/java8action'
            elif kind == 'sequence':
                flask.abort(400, 'Offloading a sequence is not supported')

        if self.image is None:
            flask.abort(400, 'Unable to determine docker image to use for action kind: \"%s\"' % kind)


class Offloader:
    """Offloader."""

    def __init__(self):
        kubernetes.config.load_incluster_config()   # running inside  k8s cluster
#        kubernetes.config.load_kube_config()       # running outside k8s cluster
        self.batch_api = kubernetes.client.apis.batch_v1_api.BatchV1Api()
        self.core_api = kubernetes.client.CoreV1Api()
        self.invoker_image = os.environ['OW_OFFLOAD_IMAGE']
        self.action_timelimit = os.getenv('OW_OFFLOAD_TIME_LIMIT', 3600)
        self.kube_namespace = os.getenv('OW_OFFLOAD_KUBE_NAMESPACE', 'default')
        self.storage_host = os.getenv('OW_STORAGESERVICE_SERVICE_HOST')
        self.storage_port = os.getenv('OW_STORAGESERVICE_SERVICE_PORT')
        sys.stdout.write('OpenWhisk offload server initialized\n')

    # store a large parameter to the storage service for later retrieval by the job
    def storeValue(self, value):
        r = requests.post('http://'+self.storage_host+':'+self.storage_port+'/storeValue',
                          json = {'value' : value},
                          headers = {'Content-Type' : 'application/json'})
        r.raise_for_status()
        return r.json()['key']


    # execute an offloaded whisk action
    # @param req OffloadRequest instance containing details needed to run the offload action
    def executeAction(self, req):
        try:
            jobId = str(uuid.uuid4()).replace('-','')
            flowId = str(uuid.uuid4()).replace('-','')
            node_selector = req.placement.get('invoker-selector', {})
            labels = {
                'flowId': flowId,
                'jobId': jobId,
                'job-type': 'ow-offload-job'
            }
            object_meta = V1ObjectMeta(name='offload-invoker-'+jobId,
                                       labels=labels)
            try:
                parts = req.actionFQN.split('/')[1:]
                l = {"ow_action": '_'.join(parts)}
                labels.update(l)
                l = {"vim_id": req.activationId}
                labels.update(l)
                l = {"ro_vim_vm_name": req.ro_vim_vm_name}
                labels.update(l)
                l = {"event_uuid": req.event_uuid}
                labels.update(l)
            except:
                pass
            # label pod with these selectors, prefix them so that
            # we know how to retrieve them for anti-afinity
            for k in node_selector:
                labels.update({'FAAS_%s' %k : node_selector[k]})
            # Put owb64APIKey into a secret
            secret = V1Secret(metadata=object_meta, string_data={'ow-api-key' : req.owb64APIKey })
            logger.debug('About to create the secret..')
            self.core_api.create_namespaced_secret(namespace=self.kube_namespace, body=secret)
            logger.debug('Done creating a secret')
            apiKeySecret = V1SecretKeySelector(key='ow-api-key', name=object_meta.name)

            # build environment for invoker container
            invokerEnv = [V1EnvVar(name="OW_OFFLOAD_FLOW_ID", value=flowId),
                        V1EnvVar(name="OW_OFFLOAD_ACTIVATION_ID", value=req.activationId),
                        V1EnvVar(name="OW_OFFLOAD_OW_API_HOST", value=req.owAPIHost),
                        V1EnvVar(name="OW_OFFLOAD_ENDPOINTS", value=json.dumps(req.endpoints)),
                        V1EnvVar(name="OW_OFFLOAD_OW_API_KEY", value_from=V1EnvVarSource(secret_key_ref=apiKeySecret))]
            paramStr = json.dumps(req.params)
            if len(paramStr) > MAX_LEN_ENVVAR and not self.storage_host is None:
                key = self.storeValue(paramStr)
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_ARGS_FILE", value=key))
            else:
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_ARGS", value=paramStr))
            if not req.code is None:
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_BINARY_CODE", value=json.dumps(req.binary)))
                codeStr = json.dumps(req.code)
                if len(codeStr) > MAX_LEN_ENVVAR and not self.storage_host is None:
                    key = self.storeValue(codeStr)
                    invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_CODE_FILE", value=key))
                else:
                    invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_CODE", value=codeStr))
            if not req.entry is None:
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_MAIN", value=json.dumps(req.entry)))

            # build environment for action container
            actionEnv = [V1EnvVar(name="__OW_API_HOST", value=req.owAPIHost),
                         V1EnvVar(name="__OW_API_KEY", value_from=V1EnvVarSource(secret_key_ref=apiKeySecret)),
                         V1EnvVar(name="__OW_NAMESPACE", value="ow-offload"),
                         V1EnvVar(name="__OW_ACTION_NAME", value=req.actionFQN),
                         V1EnvVar(name="__OW_ACTIVATION_ID", value=jobId),
                         V1EnvVar(name="__OW_OFFLOADING_ACTIVATION_ID", value=req.activationId)]

            affinity = None
            security_context = None
            if req.placement.get('action-antiaffinity', 'false') == 'true':
                # take the first one
                k = find(labels, lambda k: k.startswith('FAAS')==True)
                print ('*** k for find labels :%s' % k)
                # if no placement related label then use the action name one
                l = {k: labels[k]} if k else dict(ow_action=labels['ow_action'])
                affinity = V1Affinity(pod_anti_affinity=_build_pod_antiaffinity(l))
            if req.placement.get('action-security_context', 'false') == 'true':
                security_context = V1SecurityContext(capabilities=V1Capabilities(add=['NET_ADMIN']))

            #node_selector = {}
            #for k in req.placement.get('invoker-selector', {}):
            #    node_selector[k] = req.placement['invoker-selector'][k]
            v1Job = _build_job(namespace=self.kube_namespace,
                object_meta=object_meta, node_selector=node_selector,
                affinity=affinity, invoker_image=self.invoker_image,
                action_image=req.image, invokerEnv=invokerEnv, actionEnv=actionEnv,
                params=req.params, action_timelimit=self.action_timelimit,
                security_context=security_context)

            self.batch_api.create_namespaced_job(
                namespace=self.kube_namespace, body=v1Job)

            sys.stdout.write('Created job '+jobId+'\n')

            #controller_uid = job.spec.selector.match_labels.get('controller-uid')

            service_dict = {}
            if req.service_type and req.service_ports:
                logger.debug('Creating %s service for action jobId: %s using '
                             'flowId: %s as a selector' %
                             (req.service_type, jobId, flowId))
                sys.stdout.write('Creating %s service for action jobId: %s using '
                             'flowId: %s as a selector' %
                             (req.service_type, jobId, flowId))

                service_object_meta = V1ObjectMeta(
                    name='offload-invoker-%s' % flowId,
                    labels={'flowId': flowId})
                # Wrap every port as a service
                ports = []
                for index, p in enumerate(req.service_ports):
                    if PORT_UDP_REGEX.match(str(p)):
                        # udp port
                        port = PORT_UDP_REGEX.match(p).group(1)
                        protocol = 'UDP'
                    else:
                        # default TCP
                        port = p
                        protocol = 'TCP'
                    ports.append(V1ServicePort(name='http-api-%d' % index,
                                               port=int(port), protocol=protocol))

                service_spec = V1ServiceSpec(
                    ports=ports,
                    type=req.service_type,
                    selector={'flowId': flowId})

                service = self.core_api.create_namespaced_service(
                    namespace=self.kube_namespace,
                    body=V1Service(metadata=service_object_meta,
                                   spec=service_spec))
                logger.debug('Successfully created %(service_type)s service '
                                '%(service)s for job: %(jobId)s'
                    %
                    {
                        'jobId': jobId,
                        'service': service,
                        'service_type': req.service_type
                    })
                service_dict = _from_service(service)

            return {
                'flowId': flowId,
                'jobId': jobId,
                'service': service_dict,
            }

        except Exception as e:
            print(e)
            try:
                headers = {'Content-Type' : 'application/json',
                           'Authorization' : 'Basic %s' % req.owb64APIKey }
                for endpoint in req.endpoints:
                    requests.post(req.owAPIHost+'/api/v1/namespaces'+endpoint,
                                  json={'error': str(e)}, headers=headers,
                                  verify=False)
            except Exception as e:
                print(e)

    def reconfigureAction(self, req):
        """
        Orchestrates reconfiguration of a POD that yields to creating a new
        shadow POD followed by deleting the former one once shadow is running.
        During this process, POD spec may change and lead to placing the POD
        into a different host (i.e. different affinity/antiaffinity), with
        different HW characteristics.

        It is important to note that the new POD/job is created under a flowId
        that already exists so that existing immutable resources such as
        service, secretes, .. are relate with the new POD.

        Finally, the former POD/job get deleted.

        On falure, roll-back is being done to revert back to original POD/job
        """
        if req.flowId is None:
            flask.abort(400, 'Required parameter "flowId" not provided')

        def _sanity_check(flowId):
            """
            Ensure there is only one pod under flowId and it is in running
            state.

            Return the running jobId, fail otherwise
            """
            podList = self.core_api.list_namespaced_pod(
                namespace=self.kube_namespace, label_selector='flowId='+flowId)
            if podList and len(podList.items) == 1:
                for i in podList.items:
                    pod = self.core_api.read_namespaced_pod(
                        namespace=self.kube_namespace,name=i.metadata.name)
                    if pod.status.phase != 'Running':
                        raise Exception('Failed sanity check: '
                                        'POD under flowId %s in other state %s'
                                        % (flowId, pod.status.phase))
                    else:
                        return i.metadata.labels['jobId']
            else:
                raise Exception('No POD or found more then one under flowId %s'
                                % flowId)

        def _wait_until_running(jobId):
            """
            Wait until POD under jobId is in running state
            """
            initAttempts = 0
            while True:
                podList = self.core_api.list_namespaced_pod(
                    namespace=self.kube_namespace,
                    label_selector='jobId='+jobId)
                if podList:
                    for i in podList.items:
                        pod = self.core_api.read_namespaced_pod(
                            namespace=self.kube_namespace,
                            name=i.metadata.name)
                        logger.info ('phase %s' % pod.status.phase)
                        if pod.status.phase != 'Running':
                            initAttempts += 1
                            if initAttempts > 10:
                                raise Exception('Timeout in POD readiness')
                            sys.stdout.write(
                                'POD not ready; waiting %d seconds and '
                                'retrying\n' % initAttempts)
                            time.sleep(initAttempts)
                        else:
                            return

        try:
            old_jobId = _sanity_check(req.flowId)
            jobId = str(uuid.uuid4()).replace('-','')

            logger.debug('old jobId: %s new jobId: %s' %(old_jobId, jobId))
            # reset placement and build from annotations passed here
            req.placement = {}
            element = find(req.annotations, lambda element: element['key']==ANNOTATION_PLACEMENT)
            if element:
                req.placement = element['value']
            node_selector = req.placement.get('invoker-selector', {})
            labels = {
                'flowId': req.flowId,
                'jobId': jobId,
                'job-type': 'ow-offload-job'
            }

            object_meta = V1ObjectMeta(name='offload-invoker-'+jobId,
                                       labels=labels)
            try:
                parts = req.actionFQN.split('/')[1:]
                l = {"ow_action": '_'.join(parts)}
                labels.update(l)
                l = {"vim_id": req.activationId}
                labels.update(l)
                l = {"ro_vim_vm_name": req.ro_vim_vm_name}
                labels.update(l)
                l = {"event_uuid": req.event_uuid}
                labels.update(l)
            except:
                pass
            # TODO: handle labels in the same way as in executeAction
            invokerEnv = [
                V1EnvVar(name="OW_OFFLOAD_FLOW_ID", value=req.flowId),
                V1EnvVar(name="OW_OFFLOAD_ACTIVATION_ID", value=""),
                # endpoits are not relevant
                V1EnvVar(name="OW_OFFLOAD_ENDPOINTS", value=json.dumps([]))
            ]
            paramStr = json.dumps(req.params)
            if len(paramStr) > MAX_LEN_ENVVAR and not self.storage_host is None:
                key = self.storeValue(paramStr)
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_ARGS_FILE", value=key))
            else:
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_ARGS", value=paramStr))
            if not req.code is None:
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_BINARY_CODE", value=json.dumps(req.binary)))
                codeStr = json.dumps(req.code)
                if len(codeStr) > MAX_LEN_ENVVAR and not self.storage_host is None:
                    key = self.storeValue(codeStr)
                    invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_CODE_FILE", value=key))
                else:
                    invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_CODE", value=codeStr))
            if not req.entry is None:
                invokerEnv.append(V1EnvVar(name="OW_OFFLOAD_MAIN", value=json.dumps(req.entry)))

            # build environment for action container
            actionEnv = [V1EnvVar(name="__OW_API_HOST", value=req.owAPIHost),
                         V1EnvVar(name="__OW_NAMESPACE", value="ow-offload"),
                         V1EnvVar(name="__OW_ACTION_NAME", value=req.actionFQN),
                         V1EnvVar(name="__OW_ACTIVATION_ID", value=jobId),
                         V1EnvVar(name="__OW_OFFLOADING_ACTIVATION_ID", value=req.activationId)]

            affinity = None
            if req.placement.get('action-antiaffinity', 'false') == 'true':
                # TODO: consider using ow_action label to distinguish between pods
                affinity = V1Affinity(pod_anti_affinity=_build_pod_antiaffinity(dict(ow_action=labels['ow_action'])))

            v1Job = _build_job(namespace=self.kube_namespace,
                object_meta=object_meta, node_selector=node_selector,
                affinity=affinity, invoker_image=self.invoker_image,
                action_image=req.image, invokerEnv=invokerEnv, actionEnv=actionEnv,
                params=req.params, action_timelimit=self.action_timelimit,
                security_context=None)

            self.batch_api.create_namespaced_job(
                namespace=self.kube_namespace, body=v1Job)
            def _asynch_work():
                try:
                    _wait_until_running(jobId)
                    # new one ok, delete old one
                    self.cleanupJob(old_jobId, 'reconfigure')
                except:
                    # error: clean new one
                    self.cleanupJob(jobId, 'reconfigure')

            _thread.start_new_thread(_asynch_work, ())
            time.sleep(1)

        except Exception as e:
            print(e)
            raise e

    # get logs for a completed job
    # @param jobId key to identify job to get logs from
    def getLogs(self, jobId):
        sys.stdout.write('Requesting logs for job '+jobId+'\n')
        podList = self.core_api.list_namespaced_pod(namespace=self.kube_namespace,
                                                    label_selector='jobId='+jobId)
        actionLogs = ''
        invokerLogs = ''
        for pod in podList.items:
            actionLogs += self.core_api.read_namespaced_pod_log(namespace=self.kube_namespace,
                                                                name=pod.metadata.name,
                                                                container='ow-action',
                                                                timestamps=True)
            invokerLogs += self.core_api.read_namespaced_pod_log(namespace=self.kube_namespace,
                                                               name=pod.metadata.name,
                                                               container='ow-invoker',
                                                               timestamps=True)
        return {'actionLogs' : actionLogs.splitlines(),
                'invokerLogs' : invokerLogs.splitlines()}



    def getPodFromRo(self, ro_vim_vm_name):
        sys.stdout.write('Requesting pod for ro_vim_vm_name '+ro_vim_vm_name+'\n')
        logger.debug('Requesting pod for ro_vim_vm_name '+ro_vim_vm_name+'\n')
        service_dict = {}

        podList = self.core_api.list_namespaced_pod(
            namespace=self.kube_namespace, label_selector='ro_vim_vm_name='+ro_vim_vm_name)
        # logger.debug('getPod: podList: %s' % podList)
        if podList and len(podList.items) > 0:
            records = []
            for i in podList.items:
                pod = self.core_api.read_namespaced_pod(
                    namespace=self.kube_namespace, name=i.metadata.name)
                flowId = pod.metadata.labels['flowId']
                vim_id = pod.metadata.labels['vim_id']
                sys.stdout.write('flowId: '+flowId+'\n')
                action, terminated = _action_from_pod(pod)
#                 if terminated:
#                     raise Exception('POD action container terminated [flowId: %s]' % flowId)
    
                serviceList = self.core_api.list_namespaced_service(
                    namespace=self.kube_namespace, label_selector='flowId='+flowId)
                for service in serviceList.items:
                    service_dict = _from_service(service)
                    break
    
                records.append({
                    'action': action or '',
                    'event_uuid': pod.metadata.labels['event_uuid'],
                    'flowId': flowId,
                    # vim-id: Importatnat to be same name as in VDUr
                    'vim-id': vim_id,
                    'pod_ip' : pod.status.pod_ip,
                    'host_ip': pod.status.host_ip,
                    'phase' : 'Terminated' if terminated else pod.status.phase,
                    'service': service_dict
                })
            return {'_exists': 'true', 'records': records}
        else:
            return {'_exists': 'false'}


    def getPod(self, flowId):
        sys.stdout.write('Requesting pod for flow '+flowId+'\n')
        logger.debug('Requesting pod for flow '+flowId+'\n')
        service_dict = {}

        serviceList = self.core_api.list_namespaced_service(
            namespace=self.kube_namespace, label_selector='flowId='+flowId)
        for service in serviceList.items:
            service_dict = _from_service(service)
            break

        podList = self.core_api.list_namespaced_pod(
            namespace=self.kube_namespace, label_selector='flowId='+flowId)
        # logger.debug('getPod: podList: %s' % podList)
        if podList and len(podList.items) > 0:
            # return the first in running state or pick up the first
            my_pod = None
            for i in podList.items:
                pod = self.core_api.read_namespaced_pod(
                    namespace=self.kube_namespace, name=i.metadata.name)
                if pod.status.phase == 'Running':
                    my_pod = pod
                    break
            if not my_pod:
                my_pod = self.core_api.read_namespaced_pod(
                    namespace=self.kube_namespace,
                    name=podList.items[0].metadata.name)
            #logger.debug('getPod: pod: %s' % my_pod)
            action, terminated = _action_from_pod(my_pod)
            if terminated:
                raise Exception('POD action container terminated [flowId: %s]' % flowId)
            return {
                'action': action or '',
                'flowId': flowId,
                # vim-id: Importatnat to be same name as in VDUr
                'vim-id': my_pod.metadata.labels['vim_id'],
                # 'name' : my_pod.metadata.name,
                'pod_ip' : my_pod.status.pod_ip,
                'host_ip': my_pod.status.host_ip,
                'phase' : my_pod.status.phase,
                'service': service_dict
            }
        else:
            raise Exception('POD not found for flowId: %s' % flowId)


#   def cleanupJobFromLabel(self, ro_vim_vm_name):
    def cleanupJobFromLabel(self, label_name, label_value):
        """
        Delete jobs with provided label.
        There could be multiple jobs with same value with *different* flowId
        """
        sys.stdout.write('Deleting job(s) "%s" "%s" \n' % (label_name, label_value))

        jobList = self.batch_api.list_namespaced_job(
            namespace=self.kube_namespace,
            label_selector=label_name+'='+label_value)
        for j in jobList.items:
            flowId = j.metadata.labels['flowId']
            sys.stdout.write('Deleting job/service with flowId: %s\n' %flowId)
            serviceList = self.core_api.list_namespaced_service(
                namespace=self.kube_namespace,
                label_selector='flowId='+flowId)
            for s in serviceList.items:
                sys.stdout.write('** Deleting service ' + s.metadata.name +'** \n')
                self.core_api.delete_namespaced_service(
                    namespace=self.kube_namespace, name=s.metadata.name)

            sys.stdout.write('** Deleting jobs of '+flowId+'** \n')
            self.batch_api.delete_collection_namespaced_job(
                namespace=self.kube_namespace,
                label_selector='flowId='+flowId)

            sys.stdout.write('** Deleting pods of '+flowId+'** \n')
            self.core_api.delete_collection_namespaced_pod(
                namespace=self.kube_namespace,
                label_selector='flowId='+flowId)

            sys.stdout.write('** Deleting secrets of '+flowId+'** \n')
            self.core_api.delete_collection_namespaced_secret(
                namespace=self.kube_namespace,
                label_selector='flowId='+flowId)


    # cleanup resources for a completed job
    # @param jobId key to identify job to cleanup
    def cleanupJob(self, identifier, statusString):
        """
        Cleanup resources for a completed or failed job.

        For completed job we use flowId to delete all resources including
        secretes and service

        For failed job coming from invoker, we use flowId to delete all
        resources

        For failed job coming directly from reconfigure orchestrator, we use
        jobId to delete the job only

        The above is determined from statusString
        """
        sys.stdout.write('Deleting {} job {}\n'.format(statusString, identifier))
        if statusString == 'delete' or  \
            statusString == 'completed' \
            or statusString == 'failed':

            selector = 'flowId'
            serviceList = self.core_api.list_namespaced_service(
                namespace=self.kube_namespace,
                label_selector=selector+'='+identifier)

            for s in serviceList.items:
                sys.stdout.write('Deleting service ' + s.metadata.name +
                                 ' of ' + identifier +'\n')
                self.core_api.delete_namespaced_service(
                    namespace=self.kube_namespace, name=s.metadata.name)

            sys.stdout.write('** Deleting jobs of '+identifier+'** \n')
            self.batch_api.delete_collection_namespaced_job(
                namespace=self.kube_namespace,
                label_selector=selector+'='+identifier)

            sys.stdout.write('** Deleting pods of '+identifier+'** \n')

            self.core_api.delete_collection_namespaced_pod(
                namespace=self.kube_namespace,
                label_selector=selector+'='+identifier)

            sys.stdout.write('** Deleting secrets of '+identifier+'** \n')

            self.core_api.delete_collection_namespaced_secret(
                namespace=self.kube_namespace,
                label_selector=selector+'='+identifier)

        elif statusString == 'reconfigure':
            # handle both cases:
            # 1. shadow failed - thus we want to delete it
            # 2. part of reconfigure flow - thus delete former job
            selector = 'jobId'

            sys.stdout.write('** Deleting jobs of '+identifier+'** \n')
            self.batch_api.delete_collection_namespaced_job(
                namespace=self.kube_namespace,
                label_selector=selector+'='+identifier)

            sys.stdout.write('** Deleting pods of '+identifier+'** \n')

            self.core_api.delete_collection_namespaced_pod(
                namespace=self.kube_namespace,
                label_selector=selector+'='+identifier)



proxy = flask.Flask(__name__)
proxy.debug = True
offloader = None
server = None


def setOffloader(o):
    global offloader
    offloader = o


def setServer(s):
    global server
    server = s


def getMessagePayload():
    message = flask.request.get_json(force=True, silent=True)
    if message and not isinstance(message, dict):
        flask.abort(400, 'message payload is not a dictionary')
    else:
        value = message.get('value', {}) if message else {}
    if not isinstance(value, dict):
        flask.abort(400, 'message payload did not provide binding for "value"')
    return value;


# Ping / ready to serve
# Used for kubernetes liveness probe
@proxy.route("/hello")
def hello():
    logger.info ('Enter /hello')
    return ("Greetings from the OpenWhisk offload server! "
            "OSM Version: %s FaaS Version: %s\n" %
            (OSM_VERSION, FAAS_VERSION))


# Offload an OpenWhisk action
# This is the only route that should be exposed outside of the kube cluster
@proxy.route("/offload",  methods=['POST'])
def offload():
    logger.info ('Enter /offload')
    sys.stdout.write('Received offload request\n')
    try:
        logger.debug('Before offloadrequest')
        req = OffloadRequest(getMessagePayload())
        logger.debug('after offloadrequest')
        actionDef = req.requestAction()
        logger.debug('actionDef: %s' % actionDef)
        req.decodeAction(actionDef)
        response = flask.jsonify(offloader.executeAction(req))
        response.status_code = 200
        return response
    except HTTPException as e:
        logger.debug('Exit /offload %s', str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        logger.debug('Exit /offload %s', str(e))
        return response

    logger.info('Exit /offload')
    #return ('OK', 202)


# Reconfigure an OpenWhisk action
@proxy.route("/reconfigure",  methods=['POST'])
def reconfigure():
    logger.info ('Enter /reconfigure')
    sys.stdout.write('Received reconfigure request\n')
    try:
        req = OffloadRequest(getMessagePayload())
        actionDef = req.requestAction()
        logger.debug('actionDef: %s' % actionDef)
        req.decodeAction(actionDef)
        offloader.reconfigureAction(req)
    except HTTPException as e:
        logger.debug('Exit /reconfigure %s', str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        logger.debug('Exit /reconfigure %s', str(e))
        return response

    return ('OK', 200)

    logger.info('Exit /reconfigure')


# Get the logs for an offloaded job
@proxy.route("/getLogs",  methods=['POST'])
def getLogs():
    value = getMessagePayload()

    jobId = value.get('jobId', None)

    if jobId is None:
        response = flask.jsonify({'error': 'Did not receive jobId for /getLogs route.'})
        response.status_code = 400
        return response

    try:
        logs = offloader.getLogs(jobId)
        response = flask.jsonify(logs)
        response.status_code = 200
        return response
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response


# Cleanup resources after successful completion of offloaded job
@proxy.route("/successfulJob",  methods=['POST'])
def successfulJob():
    value = getMessagePayload()

    flowId = value.get('flowId', None)

    if flowId is None:
        response = flask.jsonify({'error': 'Did not receive flowId for /successfulJob route.'})
        response.status_code = 400
        return response

    try:
        offloader.cleanupJob(flowId, 'completed')
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response

    return ('OK', 200)


# Hook to eventually allow cleanup of resources after unsuccessful completion of offloaded job
# Currently just logs that job failed to stdout.
@proxy.route("/failedJob",  methods=['POST'])
def failedJob():
    value = getMessagePayload()

    flowId = value.get('flowId', None)

    if flowId is None:
        response = flask.jsonify({'error': 'Did not receive flowId for /failedJob route.'})
        response.status_code = 400
        return response

    sys.stdout.write('Job '+flowId+' failed, but OW_OFFLOAD_KEEP_FAILED_JOBS not set -- therefore still deleting job resources.\n')
    try:
        offloader.cleanupJob(flowId, 'failed')
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response

    return ('OK', 200)


# Get the pod for an offloaded job
@proxy.route("/getPod",  methods=['POST'])
def getPod():
    value = getMessagePayload()

    flowId = value.get('flowId', None)

    if flowId is None:
        response = flask.jsonify({'error': 'Did not receive flowId for /getPod route.'})
        response.status_code = 400
        return response

    try:
        pod_json = offloader.getPod(flowId)
        response = flask.jsonify(pod_json)
        response.status_code = 200
        return response
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response


@proxy.route("/getPodFromRoLabel",  methods=['POST'])
def getPodFromRo():
    value = getMessagePayload()
    ro_vim_vm_name = value.get('ro_vim_vm_name', None)
    if ro_vim_vm_name is None:
        response = flask.jsonify({'error': 'Did not receive ro_vim_vm_name for /getPodFromRo route.'})
        response.status_code = 400
        return response

    try:
        pod_json = offloader.getPodFromRo(ro_vim_vm_name)
        response = flask.jsonify(pod_json)
        response.status_code = 200
        return response
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response


@proxy.route("/deleteJobFromLabel",  methods=['POST'])
def deleteJobFromRoLabel():
    value = getMessagePayload()

    label_name = value.get('label_name', None)
    label_value = value.get('label_value', None)
    
#    ro_vim_vm_name = value.get('ro_vim_vm_name', None)

    if label_name is None or label_value is None:
        response = flask.jsonify({'error': 'Did not receive label_name and/or label_value for /deleteJobFromLabel route.'})
        response.status_code = 400
        return response

#     if ro_vim_vm_name is None:
#         response = flask.jsonify({'error': 'Did not receive ro_vim_vm_name for /deleteJobFromRoLabel route.'})
#         response.status_code = 400
#         return response

    sys.stdout.write('Deleting Job(s) ' + label_name + ' ' + label_value + ' \n')
    try:
        offloader.cleanupJobFromLabel(label_name=label_name,
                                      label_value=label_value)
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response

    return ('OK', 200)


@proxy.route("/deleteJob",  methods=['POST'])
def deleteJob():
    value = getMessagePayload()

    flowId = value.get('flowId', None)

    if flowId is None:
        response = flask.jsonify({'error': 'Did not receive flowId for /deleteJob route.'})
        response.status_code = 400
        return response

    sys.stdout.write('Deleting Job(s) '+flowId+'\n')
    try:
        offloader.cleanupJob(flowId, 'delete')
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response

    return ('OK', 200)


@proxy.route("/conf/<ipaddress>",  methods=['POST'])
def conf(ipaddress):
    value = getMessagePayload()

    param_name = value.get('param_name', '')
    param_value = value.get('param_value', '')
    if param_name is None:
        response = flask.jsonify({'error': 'Did not receive param_name for /conf route.'})
        response.status_code = 400
        return response

    try:
        port = str(os.getenv('CONF_PROXY_PORT', 8081))
        # push into action container
        r = requests.post('http://'+ipaddress+':'+port+'/conf/'+param_name,
                          json = {'value': param_value},
                          headers = {'Content-Type' : 'application/json'})
        r.raise_for_status()
        return ('OK', 200)
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response


def main():
    port = int(os.getenv('FLASK_PROXY_PORT', 8080))
    server = WSGIServer(('0.0.0.0', port), proxy, log=None)
    setServer(server)
    server.serve_forever()

if __name__ == '__main__':
    setOffloader(Offloader())
    main()

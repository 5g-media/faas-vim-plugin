# Copyright 2017 – 2020 IBM Corporation

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import flask
import json
import os
import sys
import time

from gevent.wsgi import WSGIServer
from werkzeug.exceptions import HTTPException

import kubernetes


WAIT_TIME = 5


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
        'service_ports': app_ports,
        'cluster_ip': service.spec.cluster_ip,
        'type': service.spec.type
    }


class Proxier:
    def __init__(self):
        kubernetes.config.load_incluster_config()
        self.api = kubernetes.client.CustomObjectsApi()
        self.core_api = kubernetes.client.CoreV1Api()
        sys.stdout.write('Proxier server initialized\n')

    def createSensor(self, value):
        sys.stdout.write('Creating sensor..\n')
        sys.stdout.write(str(value))
        sys.stdout.write('\n')
        ns_name = value.get('ns_name', '')
        sensor_yaml = value.get('sensor_yaml', {})
        if ns_name:
            sensor_yaml['metadata']['name'] = 'sensor-%s' % ns_name
            sensor_yaml['spec']['dependencies'][0]['name'] = 'gateway-%s:handlerequest' % ns_name
            trigger = sensor_yaml['spec']['triggers'][0]
            for rp in trigger.get('resourceParameters', []):
                rp['src']['event'] = 'gateway-%s:handlerequest' % ns_name

        self.api.create_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="sensors",
            body=sensor_yaml
        )
        sys.stdout.write('Done creating sensor\n')
        return {}

    def createGateway(self, value):
        sys.stdout.write('Creating gateway..\n')
        sys.stdout.write(str(value))
        sys.stdout.write('\n')
        ns_name = value.get('ns_name', '')
        gateway_yaml = value.get('gateway_yaml', {})
        if ns_name:
            gateway_yaml['metadata']['name'] = 'gateway-%s' % ns_name
            gateway_yaml['spec']['template']['metadata']['name'] = 'gateway-%s' % ns_name
            gateway_yaml['spec']['template']['metadata']['labels']['gateway-name'] = 'gateway-%s' % ns_name
            gateway_yaml['spec']['service']['metadata']['name'] = 'gateway-%s' % ns_name
            gateway_yaml['spec']['service']['spec']['selector']['gateway-name'] = 'gateway-%s' % ns_name
            gateway_yaml['spec']['watchers']['sensors'][0]['name'] = 'sensor-%s' % ns_name
            gateway_yaml['spec']['eventSource'] = 'fiveg-media-event-source'

        self.api.create_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="gateways",
            body=gateway_yaml
        )
        sys.stdout.write('Done creating gateway\n')
        sys.stdout.write('Start retrieve service..\n')
        try:
            service_name = gateway_yaml['spec']['service']['metadata']['name']
        except KeyError:
            raise Exception('Unable to retrieve Gateway service name')
        sys.stdout.write('Wait for service to appear..\n')
        time.sleep(WAIT_TIME)
        sys.stdout.write('Wait done\n')
        service = self.core_api.read_namespaced_service(name=service_name, namespace='argo-events')
        sys.stdout.write('Done retrieve service\n')
        simple_service = _from_service(service)
        return {'IngressPort': simple_service['service_ports'][12000]}

    def createEventSource(self, value):
        sys.stdout.write('Creating event-source..\n')
        sys.stdout.write(str(value))
        sys.stdout.write('\n')
        event_source_yaml = value.get('event_source_yaml', {})
        self.api.create_namespaced_custom_object(
            group="",
            version="v1",
            namespace="argo-events",
            plural="configmaps",
            body=event_source_yaml
        )
        sys.stdout.write('Done creating event-source\n')
        return {}


    def getWorkflow(self, name):
        sys.stdout.write('Requesting workflow for name '+name+'\n')

        workflow = self.api.get_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="workflows",
            name=name)
        sys.stdout.write(str(workflow)+'\n')
        # list of dict name, value pairs
        workflow_parameters = workflow.get('spec', {}).get('arguments', {}).get('parameters', [])
        return {
            'name': workflow['metadata']['name'],
            'phase': workflow['status']['phase'],
            'workflow_parameters': workflow_parameters
        }


    def deleteWorkflowFromLabel(self, osm_ns):
        sys.stdout.write('Deleting workflows with label %s..\n' % osm_ns)

        wfList = self.api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="workflows",
            label_selector='osm_ns='+osm_ns)
        sys.stdout.write('%s\n' % str(wfList))        
        for wf in wfList.get('items', []):
            sys.stdout.write('Deleting workflow %s\n' % wf['metadata']['name'])
            self.api.delete_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="workflows",
            name=wf['metadata']['name'],
            body=kubernetes.client.V1DeleteOptions())

        sys.stdout.write('Done deleting workflows\n')
        return {}


    def deleteGateway(self, ns_name):
        sys.stdout.write('Deleting gateway..\n')

        self.api.delete_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="gateways",
            name='gateway-%s' % ns_name,
            body=kubernetes.client.V1DeleteOptions()
        )
        sys.stdout.write('Done deleting gateway\n')
        return {}


    def deleteSensor(self, ns_name):
        sys.stdout.write('Deleting sensor..\n')

        self.api.delete_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argo-events",
            plural="sensors",
            name='sensor-%s' % ns_name,
            body=kubernetes.client.V1DeleteOptions()
        )
        sys.stdout.write('Done deleting sensor\n')
        return {}


proxy = flask.Flask(__name__)
proxy.debug = True
proxier = None
server = None


def setProxier(o):
    global proxier
    proxier = o


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


@proxy.route("/hello")
def hello():
    sys.stdout.write ('Enter /hello\n')
    return ("Greetings from the Proxier server! ")


@proxy.route("/createGateway",  methods=['POST'])
def createGateway():
    sys.stdout.write('Received gateway request\n')
    try:
        value = getMessagePayload()
        response = flask.jsonify(proxier.createGateway(value))
        response.status_code = 200
        return response
    except HTTPException as e:
        sys.stdout.write('Exit /createGateway %s\n' % str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        sys.stdout.write('Exit /createGateway %s\n' % str(e))
        return response


@proxy.route("/createEventSource",  methods=['POST'])
def createEventSource():
    sys.stdout.write('Received event-source request\n')
    try:
        value = getMessagePayload()
        response = flask.jsonify(proxier.createEventSource(value))
        response.status_code = 200
        return response
    except HTTPException as e:
        sys.stdout.write('Exit /createEventSource %s\n' % str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        sys.stdout.write('Exit /createEventSource %s\n' % str(e))
        return response


@proxy.route("/createSensor",  methods=['POST'])
def createSensor():
    sys.stdout.write('Received sensor request\n')
    try:
        value = getMessagePayload()
        response = flask.jsonify(proxier.createSensor(value))
        response.status_code = 200
        return response
    except HTTPException as e:
        sys.stdout.write('Exit /createSensor %s\n' % str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        sys.stdout.write('Exit /createSensor %s\n' % str(e))
        return response


@proxy.route("/deleteWorkflowFromLabel/<osm_ns>",  methods=['DELETE'])
def deleteWorkflowFromLabel(osm_ns):
    sys.stdout.write('Received delete workflows request %s\n' % osm_ns)
    try:
        response = flask.jsonify(proxier.deleteWorkflowFromLabel(osm_ns))
        response.status_code = 200
        return response
    except HTTPException as e:
        sys.stdout.write('Exit /deleteWorkflowFromLabel %s\n' % str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        sys.stdout.write('Exit /deleteWorkflowFromLabel %s\n' % str(e))
        return response


@proxy.route("/deleteGateway/<ns_name>",  methods=['DELETE'])
def deleteGateway(ns_name):
    sys.stdout.write('Received delete gateway request %s\n' % ns_name)
    try:
        response = flask.jsonify(proxier.deleteGateway(ns_name))
        response.status_code = 200
        return response
    except HTTPException as e:
        sys.stdout.write('Exit /deleteGateway %s\n' % str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        sys.stdout.write('Exit /deleteGateway %s\n' % str(e))
        return response


@proxy.route("/deleteSensor/<ns_name>",  methods=['DELETE'])
def deleteSensor(ns_name):
    sys.stdout.write('Received delete sensor request %s\n' % ns_name)
    try:
        response = flask.jsonify(proxier.deleteSensor(ns_name))
        response.status_code = 200
        return response
    except HTTPException as e:
        sys.stdout.write('Exit /deleteSensor %s\n' % str(e))
        return e
    except Exception as e:
        print(e)
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        sys.stdout.write('Exit /deleteSensor %s\n' % str(e))
        return response


@proxy.route("/getWorkflow/<name>",  methods=['GET'])
def getWorkflow(name):
    try:
        flow_json = proxier.getWorkflow(name)
        response = flask.jsonify(flow_json)
        response.status_code = 200
        return response
    except HTTPException as e:
        return e
    except Exception as e:
        response = flask.jsonify({'error': 'Internal error. {}'.format(e)})
        response.status_code = 500
        return response


def main():
    port = int(os.getenv('LISTEN_PORT', 8080))
    server = WSGIServer(('0.0.0.0', port), proxy, log=None)
    setServer(server)
    server.serve_forever()


if __name__ == '__main__':
    setProxier(Proxier())
    main()

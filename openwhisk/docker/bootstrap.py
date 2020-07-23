#!/usr/bin/env python2

import base64
import json
import os
import requests
import sys
import yaml


"""
Bootstrap action responsible for deploying FaaS VNFM assets into kubernetes cluster.

This action is packaged into a base image called '5gmedia-bootstrap' where users extend it to add their own VNFM logic.

Users must add both gateway.yml and sensor.yaml under /. This is done via docker image as explained above.

The action is called by the FaaS VIM plug-in of OSM with the following parameters

:param proxierUrl: Url to workflow service
:param operation: The operation to perform. create: deploy the assets, delete: remove the assets
:param ns_name: Network service name the assets will be deployed under.

For create operation, the action returns the fully qualified action_name and ingress URL of the deployed gateway/sensor
:return action_name: This fully qualified action name. FaaS VIM plug-in, in deletion, will call this action to delete the assets
:return IngressPort: Ingress nodeport to gateway event service. FaaS VIM plug-in builds the full url and persists it inside the VNFR
"""


def raise_for_status(r):
    http_error_msg = ''

    if 400 <= r.status_code < 500:
        http_error_msg = '%s Client Error: %s' % (r.status_code, r.reason)

    elif 500 <= r.status_code < 600:
        http_error_msg = '%s Server Error: %s' % (r.status_code, r.reason)

    return http_error_msg

try:
    args = ''
    for i in range (1,len(sys.argv)):
        args = args + sys.argv[i]
    args = json.loads(args)

    proxierUrl = args.get('proxierUrl')
    if proxierUrl is None:
        raise Exception("Did not provide required proxierUrl parameter")
        #sys.stdout.write('{"error": "Did not provide required proxierUrl parameter"}')
        #sys.exit(0)

    ns_name = args.get('ns_name')
    if ns_name is None:
        raise Exception("Did not provide required ns_name parameter")
        #sys.stdout.write('{"error": "Did not provide required ns_name parameter"}')
        #sys.exit(0)

    operation = args.get('operation')
    if operation is None:
        raise Exception("Did not provide required operation parameter")
        #sys.stdout.write('{"error": "Did not provide required operation parameter"}')
        #sys.exit(0)
    if operation not in ['create', 'delete']:
        raise Exception("Illegal operation value")
        #sys.stdout.write('{"error": "Illegal operation value"}')
        #sys.exit(0)

    # TODO: Instead better to inject modified ns_name during sensor deploy
    ns_name_upper = ns_name.replace('_','-')

    headers = {'Content-Type': 'application/json', 'accept': 'application/json'}

    if operation == 'create':
        with open('/gateway.yaml') as f:
            gateway_yaml = yaml.load(f, Loader=yaml.FullLoader)
    
        with open('/sensor.yaml') as f:
            sensor_yaml = yaml.load(f, Loader=yaml.FullLoader)

        payload = {
            'ns_name': ns_name_upper,
            'gateway_yaml': gateway_yaml
        }

        r = requests.post(proxierUrl+'/createGateway', json={'value': payload},
                          headers=headers)
        error_msg = raise_for_status(r)
        if error_msg:
            sys.stdout.write('{"error": "Error creating gateway: %s. Details: %s"}' % (error_msg, r.text))
            raise Exception("Error creating gateway. Details in activation logs")

        r_gw_json = r.json()

        payload = {
            'ns_name': ns_name_upper,
            'sensor_yaml': sensor_yaml
        }

        r = requests.post(proxierUrl+'/createSensor', json={'value': payload},
                          headers=headers)
        error_msg = raise_for_status(r)
        if error_msg:
            sys.stdout.write("Error creating sensor: %s. Details: %s" % (error_msg, r.text))
            raise Exception("Error creating sensor. Details in activation logs")

        sys.stdout.write('{"_bootstrap": "true", "ns_name": "%s", "IngressPort": "%s", "action_name": "%s"}'
                         % (ns_name, r_gw_json['IngressPort'], os.getenv('__OW_ACTION_NAME')))
        sys.exit(0)

    else:
        r_g = requests.delete(proxierUrl+'/deleteGateway/%s' % ns_name_upper,
                            headers=headers)
        error_msg_g = raise_for_status(r_g)
        r_s = requests.delete(proxierUrl+'/deleteSensor/%s' %ns_name_upper,
                            headers=headers)
        error_msg_s = raise_for_status(r_s)

        r_wf = requests.delete(proxierUrl+'/deleteWorkflowFromLabel/%s' %ns_name,
                            headers=headers)
        error_msg_wf = raise_for_status(r_wf)


        if error_msg_g:
            sys.stdout.write('Error deleting gateway: %s. Details: %s' % (error_msg_g, r_g.text))
        if error_msg_s:
            sys.stdout.write('Error deleting sensor: %s. Details: %s' % (error_msg_s, r_s.text))
        if error_msg_wf:
            sys.stdout.write('Error deleting workflow: %s. Details: %s' % (error_msg_wf, r_wf.text))

        if error_msg_g or error_msg_s or error_msg_wf:
            raise Exception("Error deleting gateway/sensor/workflow. Details in activation logs")
        else:
            sys.stdout.write('{"ok": "200"}')
        sys.exit(0)

except Exception as e:
    sys.stdout.write('{"error": "%s"}' % str(e))
    sys.exit(0)
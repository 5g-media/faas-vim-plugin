""" OpenWhisk offload action
Offload an argument action to an OpenWhisk offload service.

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

import json
import requests
import os


"""
An action to offload another action to an external OpenWhisk Offload Service.

:param offload-service-url: Url to use to invoke offload service
:param url: Url to OpenWhisk API endpoint
:param action: the name of the OpenWhisk action to offload
:param ro_vim_vm_name: the name as provided by the RO layer of OSM. Used for a later
                       correlation of an event-based offloaded action
:param completionAction: the name of an OpenWhisk action to invoke with the
                         result of the offloaded action (Optional)
:param completionTrigger: the name of an OpenWhisk trigger to invoke with the
                          result of the offloaded action (Optional)
:prarm coe_action_params: the parameters to pass to the offload service
                               service_type: ``str``
                               service_ports: array of ``int``
                               action_params: ``dict``
                               format:
                               {
                                   'service_type': 'NodePort',
                                   'service_ports': [5000, 5001, 5002],
                                   'action_params': {
                                        'player1': 'John',
                                        'player2': 'Alice'
                                    }
                               }

"""

def main(args):
    offloadService = args.get('offload-service-url')
    if offloadService is None:
        return { 'error' : 'Did not provide required \"offload-service-url\" parameter' }
    action = args.get('action')
    if action is None:
        return { 'error' : 'Did not provide required \"action\" parameter' }
    url = args.get('url')
    if url is None:
        return { 'error' : 'Did not provide required \"url\" parameter' }
    ro_vim_vm_name = args.get('ro_vim_vm_name')
    if ro_vim_vm_name is None:
        return { 'error' : 'Did not provide required \"ro_vim_vm_name\" parameter' }

    '''
    event_uuid - optional
    '''
    event_uuid = args.get('event_uuid')

    completionAction = args.get('completionAction', None)
    completionTrigger = args.get('completionTrigger', None)
    params = args.get('coe_action_params', {})

    activationId = os.getenv('__OW_ACTIVATION_ID')
    owAPIHost = url
    owAuthKey = os.getenv('__OW_API_KEY')

    # Request offloaded execution of the action
    headers = {'Content-Type' : 'application/json'}
    payload = { 'action' : action,
                'ro_vim_vm_name': ro_vim_vm_name,
                'coe_action_params' : params,
                'owAPIHost' : owAPIHost,
                'owAPIKey' : owAuthKey,
                'activationId' : activationId }
    if not completionAction is None:
        payload['completionAction'] = completionAction
    if not completionTrigger is None:
        payload['completionTrigger'] = completionTrigger

    if event_uuid:
        payload['event_uuid'] = event_uuid

    r = requests.post(offloadService+'/offload',
                      headers=headers, json={ 'value' : payload })

    if r:
        return {
            'ok' : str(r),
            'detail': r.json()
        }
    else:
        message = ''
        try:
            message = r.text
            json = r.json()
            message = json.get('error', message)
        except Exception:
            { } # swallow exception

        return { 'error' : str(r) + ': '+message }

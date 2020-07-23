"""Executable Python script for an OpenWhisk offload invoker.

An invoker that calls the /init and /run routes on an OpenWhisk
container to cause an offloaded action to execute. The result
of the action is returned to OpenWhisk by invoking the completionEndpoint.
Intended to run in the same pod as the offloaded action.

Most arguments are passed via the container's environment;
very large arguments are passwd via envars that contain keys
to use with the storage server to retrieve the values.

/*
 * Copyright 2015 - 2016 IBM Corporation 
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

import sys
import os
import json
import requests
import time
import timeit
from datetime import datetime, timezone


def getValue(local, remote):
    if not local is None:
        return json.loads(local)
    else:
        storage_host = os.getenv('OW_STORAGESERVICE_SERVICE_HOST')
        storage_port = os.getenv('OW_STORAGESERVICE_SERVICE_PORT')
        r = requests.post('http://'+storage_host+':'+storage_port+'/retrieveValue',
                          json = {'key' : remote},
                          headers = {'Content-Type' : 'application/json'})
        r.raise_for_status()
        return json.loads(r.json()['value'])


def executeAction():
    headers = {'Content-Type' : 'application/json'}
    action_url = 'http://localhost:8080'

    owAPIHost = os.getenv('OW_OFFLOAD_OW_API_HOST')
    owAPIKey = os.getenv('OW_OFFLOAD_OW_API_KEY')
    endpoints = json.loads(os.getenv('OW_OFFLOAD_ENDPOINTS'))
    code_env = os.getenv('OW_OFFLOAD_CODE')
    code_file_env = os.getenv('OW_OFFLOAD_CODE_FILE')
    binary_env = os.getenv('OW_OFFLOAD_BINARY_CODE')
    main_env = os.getenv('OW_OFFLOAD_MAIN')
    args_env = os.getenv('OW_OFFLOAD_ARGS')
    args_file_env = os.getenv('OW_OFFLOAD_ARGS_FILE')
    activationId = os.getenv('OW_OFFLOAD_ACTIVATION_ID')
    flowId = os.getenv('OW_OFFLOAD_FLOW_ID')

    offload_host = os.getenv('OW_OFFLOADSERVICE_SERVICE_HOST')
    offload_port = os.getenv('OW_OFFLOADSERVICE_SERVICE_PORT')

    ow_headers = {'Content-Type' : 'application/json',
                  'Authorization' : 'Basic %s' % owAPIKey }

    sys.stdout.write('initiating offload of job '+flowId+'\n')
    try:
        init_payload = {}
        if not (code_env is None and code_file_env is None):
            init_payload['binary'] = json.loads(binary_env)
            init_payload['code'] = getValue(code_env, code_file_env)
        if not main_env is None:
            init_payload['main'] = json.loads(main_env)

        # /init
        initAttempts = 0
        while True:
            try:
                r = requests.post(action_url+'/init', json={'value': init_payload}, headers=headers)
                r.raise_for_status()
                sys.stdout.write('post to /init completed successfully\n')
                break
            except Exception as e:
                initAttempts += 1
                if initAttempts > 10:
                    raise e
                sys.stdout.write('Action not ready; waiting %d seconds and retrying\n' % initAttempts)
                time.sleep(initAttempts)

        # /run
        args = getValue(args_env, args_file_env)
        r = requests.post(action_url+'/run', json={'value': args}, headers=headers)
        r.raise_for_status()
        sys.stdout.write('post to /run completed successfully\n')
        actionResult = r.json()

        # request logs from offload service (encapsulate k8s in server)
        start = timeit.default_timer()
        r = requests.post('http://'+offload_host+':'+offload_port+'/getLogs',
                          json = {'value': {'flowId' : flowId }},
                          headers = headers)
        logs = ''
        if r:
            logs = r.json()
            ts = datetime.now(timezone.utc).astimezone().isoformat();
            end = timeit.default_timer()
            logtime = end - start
            logs.setdefault('invokerLogs',[]).append(ts+' spent %0.3f seconds collecting logs' % logtime)

        # return result to OpenWhisk via specified endpoint(s)
        for endpoint in endpoints:
            sys.stdout.write('attempting to post result to completionEndpoint '+endpoint+'\n')
            r = requests.post(owAPIHost+'/api/v1/namespaces'+endpoint,
                              json={'result': actionResult,
                                    'offloadingActivationId': activationId,
                                    'activationId' : flowId,
                                    'logs': logs },
                              headers=ow_headers, verify=False)
            r.raise_for_status()
            sys.stdout.write('successful post to completionEndpoint '+endpoint+'\n')

        # Notify offload service that the job has completed successfully.
        sys.stdout.write('notifying offload service of successfulJob '+flowId+'\n')
        r = requests.post('http://'+offload_host+':'+offload_port+'/successfulJob',
                          json= {'value': {'flowId' : flowId }}, headers = headers)
        if not r:
            sys.stdout.write('internal error notifying offload service\n')
            print(r)

    except Exception as e:
        print(e)
        try:
            sys.stdout.write('attempting to post error to completionEndpoint\n')
            for endpoint in endpoints:
                r = requests.post(owAPIHost+'/api/v1/namespaces'+endpoint,
                                  json={'error': str(e),
                                        'offloadingActivationId': activationId,
                                        'activationId' : flowId},
                                  headers=ow_headers, verify=False)
                r.raise_for_status()
                sys.stdout.write('successfully posted error to '+endpoint+'\n')
        except Exception as e:
            print(e)

        try:
            sys.stdout.write('notifying offload service of failedJob '+flowId+'\n')
            r = requests.post('http://'+offload_host+':'+offload_port+'/failedJob',
                              json= {'value': {'flowId' : flowId, 'activationId' : activationId }},
                              headers = headers)
            r.raise_for_status()
        except Exception as e:
            sys.stdout.write('internal error notifying offload service\n')
            print(e)

    sys.stdout.write('offload invoker exiting\n')


def main():
    executeAction()

if __name__ == '__main__':
    main()

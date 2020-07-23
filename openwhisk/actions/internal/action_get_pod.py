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

import requests

"""
Openwhisk helper action that retrieves a pod information for a given flowId

:param offload-service-url: Url to offload service (e.g. http://172.15.0.251:31567)
:param flowId: The flowId to search the pod under
"""

def raise_for_status(r):
    http_error_msg = ''

    if 400 <= r.status_code < 500:
        http_error_msg = '%s Client Error: %s' % (r.status_code, r.reason)

    elif 500 <= r.status_code < 600:
        http_error_msg = '%s Server Error: %s' % (r.status_code, r.reason)

    return http_error_msg


def main(args):
    url = args.get('offload-service-url')
    if not url:
        return {'error': 'Missing offload-service-url'}
    flowId = args.get('flowId')
    if not flowId:
        return {'error': 'Missing flowId'}

    headers = {'Content-Type': 'application/json'}
    r = requests.post('%(offload-service-url)s/getPod' %
                            {
                                'offload-service-url': url
                            },
                            json={'value': {'flowId' : flowId}},
                            headers=headers)

    error_msg = raise_for_status(r)
    if not error_msg:
        r_json = r.json()
        return r_json
#         {
#             'name': r_json['name'],
#             'action': r_json['action'], 
#             'pod_ip': r_json['pod_ip'],
#             'host_ip': r_json['host_ip'],
#             'phase': r_json['phase'],
#             'service': r_json['service']
#         }
    else:
        return {'error': '%s. Details: %s' % (error_msg, r.text)}

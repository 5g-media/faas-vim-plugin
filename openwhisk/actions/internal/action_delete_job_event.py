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
Action called by the FaaS VIM plug-in for event-based VNF.

It deletes the pod with the given full ro name

:param offload-service-url: Url to offload service (e.g. http://172.15.0.251:31567)
:param label_name: The name of the label to delete the pod under
:param label_value: The value of the label to delete the pod under

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
#     ro_vim_vm_name = args.get('ro_vim_vm_name')
#     if not ro_vim_vm_name:
#         return {'error': 'Missing ro_vim_vm_name'}

    label_name = args.get('label_name')
    if not label_name:
        return {'error': 'Missing label_name'}
    label_value = args.get('label_value')
    if not label_value:
        return {'error': 'Missing label_value'}

    headers = {'Content-Type': 'application/json'}
    r = requests.post('%(offload-service-url)s/deleteJobFromLabel' %
                        {
                            'offload-service-url': url
                        },
                        json={'value': {'label_name': label_name,
                                        'label_value': label_value}},
                        headers=headers)
#     r = requests.post('%(offload-service-url)s/deleteJobFromLabel' %
#                         {
#                             'offload-service-url': url
#                         },
#                         json={'value': {'ro_vim_vm_name' : ro_vim_vm_name}},
#                         headers=headers)

    error_msg = raise_for_status(r)
    if not error_msg:
        return {'ok' : str(r)}
    else:
        return {'error': '%s. Details: %s' % (error_msg, r.text)}

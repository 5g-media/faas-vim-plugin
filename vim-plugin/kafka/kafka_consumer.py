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


import json
import requests

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from kafka_settings import KAFKA_SERVER, KAFKA_CONFIGURATION_TOPIC, \
    KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_GROUP_ID


OSM_VERSION = "v5.0.5"
FAAS_VERSION = "v2.0.2"
LOG_PREFIX = ">>>>>>>>> " + OSM_VERSION + " " + FAAS_VERSION


def _to_reconfigure_payload(**kwargs):
    """
    Utility to convert kafka message to reconfigure API payload.

    :param action_params: Action parameters in key/value pairs.
                          key - param name, value - param value
    :type action_params: ``dict``

    :param invoker-selector: Possible values: cpu, gpu. If supplied, implies
                             reconfiguration at the NFVI level to cpu/gpu node
    :type invoker-selector: ``str``

    :param action-antiaffinity: Possible values: 'true', 'false'. If 'true', do
                                not allow two actions to run on same NFVI node.
                                Relevant with invoker-selector
    :type action-antiaffinity: ``str``

    """
    if not kwargs.get('invoker-selector'):
        payload = {
            'coe_action_params': {
                'action_params': kwargs.get('action_params', {})
            }
        }
    else:
        payload = {
            'coe_action_params': {
                'action_params': kwargs.get('action_params', {}),
                'annotations': [{
                    'key': 'placement',
                    'value': {
                        'invoker-selector': {'processor': kwargs['invoker-selector']},
                        'action-antiaffinity': kwargs.get('action-antiaffinity',
                                                          'false')
                    }
                }]
            },
        }
    return payload


def reconfigure(osm_ip_address, ns_name, vnf_name, vnf_index, payload=None):
    print(LOG_PREFIX + "reconfigure: '%(osm_ip_address)s' '%(ns_name)s' "
                 "'%(vnf_name)s' '%(vnf_index)s' '%(payload)s'" %
                {
                    'osm_ip_address': osm_ip_address,
                    'ns_name': ns_name,
                    'vnf_name': vnf_name,
                    'vnf_index': vnf_index,
                    'payload': payload
                })

    headers = {'Content-Type': 'application/json'}
    r = requests.post(
        'http://%(osm_ip_address)s/osm/reconfigure/%(ns_name)s/%(vnf_name)s.%(vnf_index)s' %
        {
            'osm_ip_address': osm_ip_address,
            'ns_name': ns_name,
            'vnf_name': vnf_name,
            'vnf_index': vnf_index
        }, headers=headers, json=payload)

    print(LOG_PREFIX + "reconfigure: Received: %s" % r.text)

    r.raise_for_status()
    return r


def main():
    print ('\n\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-')
    print ("Starting Configuration Kafka bridge...\n\n"
           "KAFKA_GROUP_ID: '%s' "
           "KAFKA_CLIENT_ID: '%s' \n"
           "KAFKA_SERVER '%s' "
           "KAFKA_API_VERSION '%s' " %
           (KAFKA_GROUP_ID, KAFKA_CLIENT_ID, KAFKA_SERVER, KAFKA_API_VERSION))
    print ('-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n')

    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_SERVER,
        client_id=KAFKA_CLIENT_ID,
        enable_auto_commit=True,
        api_version=KAFKA_API_VERSION,
        group_id=KAFKA_GROUP_ID)

    consumer.subscribe(pattern=KAFKA_CONFIGURATION_TOPIC)

    for msg in consumer:
        try:
            key = msg.key.decode('utf-8')
            message = json.loads(msg.value.decode('utf-8'))
            print(LOG_PREFIX + ' key: {} has value {}'.format(key, message))
            if key == '"faas"':
                payload = _to_reconfigure_payload(**message)
                reconfigure('127.0.0.1:5001', ns_name=message['ns_name'],
                            vnf_name=message['vnf_name'],
                            vnf_index=message['vnf_index'],
                            payload=payload)
            else:
                print (LOG_PREFIX + 'Not FaaS message. Ignoring ...')
        except Exception as e:
            print (LOG_PREFIX + 'Exception: %s' % str(e))


if __name__ == '__main__':
    main()

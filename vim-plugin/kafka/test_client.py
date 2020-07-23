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
from kafka import KafkaProducer
from kafka.errors import KafkaError

from kafka_settings import KAFKA_SERVER, KAFKA_CONFIGURATION_TOPIC, \
    KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_GROUP_ID

KEY= "faas"

'''
An example that sends two day1 configuration messages.

Note: It is assumed that a network service named: 'sky_balls' already instantiated with
      two FaaS vnfd-name of transcoder_2_8_4_vnfd at index '1' and '2'.
'''

day_1_payload = [
    {
        "ns_name": "sky_balls",
        "vnf_name": "transcoder_2_8_4_vnfd",
        "vnf_index": "1",
        "action_params": {
            "produce_profiles": [1,2,3]
        }
        
    },
    {
        "ns_name": "sky_balls",
        "vnf_name": "transcoder_2_8_4_vnfd",
        "vnf_index": "2",
        "action_params": {
            "produce_profiles": [1,4]
        }
    }
]


'''
An example that sends two day1 replacement messages to CPU node instantiating one with
an overridden parameter value and second with no parameter leading to preserving with
the ones set previously.

Note: It is assumed that a network service named: 'sky_balls' already instantiated with
      two FaaS vnfd-name of transcoder_2_8_4_vnfd at index '1' and '2'.
'''

day_1_nfvi_payload = [
    {
        "ns_name": "sky_balls",
        "vnf_name": "transcoder_2_8_4_vnfd",
        "vnf_index": "1",
        "invoker-selector": "cpu",
        "action-antiaffinity": "false",
        "action_params": {
            "produce_profiles": [1],
            "gpu_node":"0"
        }
    },
    {
        "ns_name": "sky_balls",
        "vnf_name": "transcoder_2_8_4_vnfd",
        "vnf_index": "2",
        "invoker-selector": "cpu",
        "action-antiaffinity": "false",
        "action_params": {
            "gpu_node":"0"
        }
    }
]


def main():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        api_version=KAFKA_API_VERSION,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda v: json.dumps(v).encode('utf-8'))

    for p in day_1_payload:# + day_1_nfvi_payload:
        t = producer.send(KAFKA_CONFIGURATION_TOPIC, value=p, key=KEY)
        try:
            t.get(timeout=5)
        except KafkaError as e:
            logger.error(e)
            pass
    producer.close()


if __name__ == '__main__':
    main()

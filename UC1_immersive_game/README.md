# Use-case 1 Immersive Game

**Note:** it is assumed that:

* [FaaS VIM plugin](../vim-plugin) is already loaded into OSM and references to the correct openwhisk
* [Argo](../kubernetes/docs/argo.md) is installed on the correct kubernetes cluster
* [GPU nodes](../kubernetes/docs/k8s-gpu-prerequisites.md) are registered with kubernetes cluster

**Please notice [FaaS Guidelines](../vim-plugin/docs/GUIDELINES.md) before proceeding**

## Onboard Openwhisk actions

Log into OW controller

### bootstrap
```
wsk -i package create immersive-game
wsk -i action create /guest/immersive-game/bootstrap --docker docker5gmedia/immersive-game-bootstrap:07e5b29
```

### transcoders
```
wsk -i action create /guest/5g-media/vtranscoder_2_9_0_gpu -A ../openwhisk/actions/gpu-annotations.json --docker docker5gmedia/transcoder_2_9_0
wsk -i action create /guest/5g-media/vtranscoder_2_9_0_cpu -A ../openwhisk/actions/cpu-annotations.json --docker docker5gmedia/transcoder_2_9_0
```

### vbroker
```
wsk -i action create /guest/5g-media/vbroker --docker docker5gmedia/broker_1
```

### vbuffer
```
wsk -i action create /guest/5g-media/vbuffer --docker docker5gmedia/vbuffer
```

### vreplay
```
wsk -i action create /guest/5g-media/vreplay --docker docker5gmedia/vreplay
```

### vspectator (for tests only)
```
wsk -i action create /guest/5g-media/vspectator --docker docker5gmedia/simulated_spectator_hardcoded
```

## On-board VNFs and NSs

* Log into OSM launchpad
* Goto catalog
* On-board by drag/drop [UC1 packages](https://github.com/5g-media/service-descriptors/tree/master/UC1)

## Define day0 parameters for the "static" VNFs

### vbroker
Login to OSM

```bash
curl -X POST \
  http://127.0.0.1:5001/conf/sky_balls/vbroker_vnfd/4\
  -H 'content-type: application/json' \
  -d '{
  "service_ports": [
    "9092"
  ]
}'
```

## Instantiate the network service
Instantiate it from OSM GUI under name: `sky_balls`

### Poll for vBroker Ingress IP/Port
```bash
curl 127.0.0.1:5001/osm/sky_balls | jq -r '.vnfs[3].vim_info.host_ip,.vnfs[3].vim_info.service.service_ports."9092"'
```

### Set vbroker with day1 params
Copy above vBroker Ingress IP/Port to below curl

```bash
curl -X POST \
  http://127.0.0.1:5001/osm/reconfigure/sky_balls/vbroker_vnfd.4\
  -H 'content-type: application/json' \
  -d '{
  "coe_action_params": {"action_params": {"advertised_host": "...", "advertised_port": "..."}}
  }'
```

### Set vbuffer with day1 params
Copy above vBroker Ingress IP/Port to below curl

```bash
curl -X POST \
  http://127.0.0.1:5001/osm/reconfigure/sky_balls/vbuffer_vnfd.5\
  -H 'content-type: application/json' \
  -d '{
  "actions_params": {
  "brokerEndpoint":"...:...",
  "p1topic": "1_profile_0",
  "p2topic": "2_profile_0",
  "bufferSize": "30",
  "flushCommandsTopic": "flush_commands"    
  }
}'
```

### Poll for IngressUrl
Log into OSM

```bash
curl http://127.0.0.1:5001/osm/sky_balls | jq -r '.vnfs[0].vim_info.IngressUrl'
```

## Spawn event based transcoder
Copy url from above IngressUrl

Note: profiles: 0,1,2 cpu 3,4,5 gpu

```bash
curl -X POST \
  .../handlerequest \
  -H 'Content-Type: application/json' \
  -d '{
  "osm_ip": "10.100.176.66",
  "event_uuid": "1",
  "osm_ns": "sky_balls",
  "operation": "spawn_transcoder",
  "player_index": "1",
  "vnfd_name": "transcoder_2_9_0_cpu_vnfd",
  "vnfd_index": "3",
  "gpu_node": "0",
  "produce_profile": "1",
  "metrics_broker_ip": "192.158.1.175",
  "metrics_broker_port": "9092"
  }'
```

## Terminate transcoder

```bash
curl -X POST \
  .../handlerequest \
  -H 'Content-Type: application/json' \
  -d '{
  "osm_ip": "10.100.176.66",
  "event_uuid": "2",
  "osm_ns": "sky_balls",
  "operation": "terminate_transcoder",
  "uuid": "1"
  }'
```

## Spawn event based vreplay
Copy above vBroker Ingress IP/Port to `BrokerEndpoint`

```bash
curl -X POST \
  .../handlerequest \
  -H 'Content-Type: application/json' \
  -d '{
  "osm_ip": "10.100.176.66",
  "event_uuid": "3",
  "osm_ns": "sky_balls",
  "operation": "spawn_replay",
  "vnfd_name": "vreplay_vnfd",
  "vnfd_index": "6",
  "SessionID": "123",
  "TimestampTopic":"ts-topic",
  "GameStateTopic": "gs-topic",
  "OutputTopic": "out-topic",
  "BrokerEndpoint": "...:..."
  }'
```

## Terminate vreplay

```bash
curl -X POST \
  .../handlerequest \
  -H 'Content-Type: application/json' \
  -d '{
 "osm_ip":"10.100.176.66",
 "event_uuid":"4",
 "osm_ns":"sky_balls",
 "operation":"terminate_replay",
 "uuid":"3"
  }'
```

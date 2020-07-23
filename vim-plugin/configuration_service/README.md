# FaaS-Configuration service

FaaS configuration service is a microservice responsible for Day 0 and Day 1 configuration of VNFs.
* Day 0: the microservice persists initial parameters for FaaS VIM to consume and use at the VNF instantiation time
* Day 1: the microservice accepts a new configuration in a JSON format and applies it to a running instance of a VNF specified as a target parameter  


## Verify the service
FaaS configuration service is already available in 5G-MEDIA OSM

Ensure it responds to the following APIs:

```
curl http://osm_ip_address:5001/conf
curl http://osm_ip_address:5001/tenants

REST path:
    osm_ip_address - ipaddress of OSM r5.
```

## Day 0 APIs

### Persist Day 0 parameters
Define the parameters of a VNF that is going to get instantiated under the provided network service instance name

```
curl -H "Content-type: application/json" -POST -d '{"service_ports": ["<port1>", ..., "<portn>"], "action_params": {"<param_name>": "<param_value>", ...}}' http://osm_ip_address:5001/conf/<ns_name>/<vnf_name>/<vnf_index>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    ns_name        - network service instance name
    vnf_name       - the name of the vnfd
    vnf_index      - index of vnf inside nsd

Data payload:
    service_ports - array of strings
        port1 - application port (str)
        portn - another application port (str)
    
    action_params - set of key/values
        param_name  - parameter name (str)
        param_value - parameter value (str)
```

### Query Day 0 parameters
```
curl http://osm_ip_address:5001/conf/<ns_name>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    ns_name        - network service instance name
```

### Query Day 0 parameters for a given VNF
```
curl http://osm_ip_address:5001/conf/<ns_name>/<vnf_name>/<vnf_index>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    ns_name        - network service instance name
    vnf_name       - the name of the vnfd
    vnf_index      - index of vnf inside nsd
```

## Polling API

Retrieve a list of FaaS VNFRs from the given ns name
```
curl http://osm_ip_address:5001/osm/<ns_name>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    ns_name        - the network service instance name
```

## Day 1 APIs

### Reconfigure at the application level

Inject parameters to VNF runtime
```
curl -H "Content-type: application/json" -POST -d '{"coe_action_params": {"action_params": {"<param_name>": "<param_value>", ...}}}' http://osm_ip_address:5001/osm/reconfigure/<ns_name>/<vnf_name>.<vnf_index>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    ns_name        - network service instance name
    vnf_name       - the name of the vnfd
    vnf_index      - index of vnf inside nsd
    NOTE: <vnf_name>.<vnf_index> obtained from vnf_name via polling API

Data payload:
    action_params - set of key/value pair
        param_name  - parameter name (str)
        param_value - parameter value (str)

```

### Reconfigure at the NVFI level

Orchestrates replacement of the VNF into a different node within kubernetes cluster.

```
curl -H "Content-type: application/json" -POST -d '{"coe_action_params": {"action_params": {"<param_name>": "<param_value>", ...}, "annotations": [{"key": "placement", "value": {"invoker-selector": {"<label_name>": "<label_value>", ...}, "action-antiaffinity": "<boolean>"}}]}}'
 http://osm_ip_address:5001/osm/reconfigure/<ns_name>/<vnf_name>.<vnf_index>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    ns_name        - network service instance name
    vnf_name       - the name of the vnfd
    vnf_index      - index of vnf inside nsd
    NOTE: <vnf_name>.<vnf_index> obtained from vnf_name via polling API

Data payload:
    action_params - set of key/value pair
        param_name  - parameter name
        param_value - parameter value

    annotations - parent key to include the entire NVFI reconfiguration
        placement - key containing placement hints to the underlying container orchestrator system
            invoker-selector - set of node labels in key/val format. Multiple key/val interpreted as AND
                label_name  - label name
                label_value - label value

            action-antiaffinity - key to denote whether to avoid placing two actions with same name on the same node
                true  - do not place them on same node
                false - can be placed on same node
```

### Reconfigure example

The below curl migrates VNF transcoder_2_9_0_vnfd at index 2 of sky_balls NS to CPU node
```
Log into OSM

curl -H "Content-type: application/json" -POST  http://127.0.0.1:5001/osm/reconfigure/sky_balls/transcoder_2_9_0_vnfd.2 -d '{
  "coe_action_params": {
    "action_params": {
      "gpu_node": "0"
    },
    "annotations": [
      {
        "key": "placement",
        "value": {
          "invoker-selector": {
            "processor": "cpu"
          }
        }
      }]
    }
}'
```
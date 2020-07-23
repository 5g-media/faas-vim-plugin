# Creating / using FaaS pingpong example

**Note:** it is assumed that:

* [FaaS VIM plugin](../../../../vim-plugin) is already loaded into OSM and references to the correct openwhisk and kubernetes clusters
* FaaS [configuration service](../../../../vim-plugin/configuration_service) is running on OSM host

**Please notice [FaaS Guidelines](../GUIDELINES.md) before proceeding**

### Build ping pong docker images [**do that only if images not in docker5gmedia repository**]

Run the following commands under `sudo`.

* `docker build --tag "docker5gmedia/action-pong" --force-rm=true --file ./Dockerfile.pong .`
* `docker login --username=docker5gmedia`
* `docker push docker5gmedia/action-pong`

* `docker build --tag "docker5gmedia/action-ping" --force-rm=true --file ./Dockerfile.ping .`
* `docker login --username=docker5gmedia`
* `docker push docker5gmedia/action-ping`


### Create ping pong openwhisk actions

* `openwhisk/bin/wsk -i package create 5g-media`
* `openwhisk/bin/wsk -i action create /guest/5g-media/action_pong --docker docker5gmedia/action-pong`
* `openwhisk/bin/wsk -i action create /guest/5g-media/action_ping --docker docker5gmedia/action-ping`

**Note:** it is assumed that you are using the `guest` namespace

### On-board VNFs and NSs

* Log into OSM launchpad

* Goto catalog

* On-board by drag/drop `faas_ping_vnfd.tar.gz`, `faas_pong_vnfd.tar.gz`,
  `faas_pingpong_nsd.tar.gz` packages

### Invoke FaaS NS from OSM

* Decide the NS name to be used: e.g. `star_balls`
* Specify the ports and parameters that the VNFs will expose and will get instantiated with. **Use the same NS name from the previous step**
* **Note:** VDU:Name is being supplied (e.g. faas_ping_vnfd, faas_pong_vnfd)

```
curl -H "Content-type: application/json" -POST -d '{"service_ports": ["5000"], "action_params": {"Name": "FaaS PING"}}' http://osm_ip_address:5001/conf/star_balls/faas_ping_vnfd/1
curl -H "Content-type: application/json" -POST -d '{"service_ports": ["5001"], "action_params": {"Name": "FaaS PONG"}}' http://osm_ip_address:5001/conf/star_balls/faas_pong_vnfd/2
```

* Goto Instantiate page
    * Fill in **same NS name from the previous step** and FaaS VIM in VIM Account.
    * Hit OK

* Poll the VNFs until they receive IP addresses: `curl http://osm_ip_address:5001/osm/star_balls`

### Polling
Each NS comprises an array of VNFs (under `vnfs` key). Every element in this array is a json dictionary (i.e key/value):

* `vnf_name`: the name of the VNF as appear in network service descriptor (NSD) postfixed with its index inside NSD.
* `ip_address`: the flannel IP address of VNF
* `vim_info`: specific kubernetes related info of the VNF POD. Can contain the following keys:
    * `host_ip`: the host ip the VNF POD landed on
    * `pod_ip`: the flannel IP address of VNF
    * `pod_phase`: status of POD
    * `service`: port mapping info. Note: Can be empty in case no ports are requested to be mapped.
        * `service_ports`: key/val of the mapping. key: application port. val: the port opened on `host_ip` node.

```bash
localadmin@os-5gmedia:~$ curl osm_ip_address:5001/osm/star_balls
{
  "name": "star_balls",
  "vnfs": [
    {
      "ip_address": "10.244.4.7",
      "status": "ACTIVE",
      "vim_info": {
        "host_ip": "10.30.2.63",
        "pod_phase": "Running",
        "service": {
          "service_ports": {
            "5000": 30053
          },
        }
      },
      "vnf_name": "faas_ping_vnfd.1"
    },
    {
      "ip_address": "10.244.4.8",
      "status": "ACTIVE",
      "vim_info": {
        "host_ip": "10.30.2.63",
        "pod_phase": "Running",
        "service": {
          "service_ports": {
            "5001": 31057
          },
        }
      },
      "vnf_name": "faas_pong_vnfd.2"
    }
  ]
}

```
## Dynamic configuration

You should notice that first invocation of the ping VNF API returns an error.
This is because ping application (`action_ping.py`) requires `target_ip` parameter to be set with ipaddress of pong VNF.

Assuming that the host_ip and mapped port of ping are obtained from polling VNFR as described above:
```
curl 10.30.2.63:30053/ping/10
I don't know the target I should ping to :(
```

Follow the below to reconfigure ping VNF with the Day 1 parameter `target_ip`.

### Select the VNF you would like to re-configure (in our case it would be ping)

### Define day 1 parameter

* Poll the network service: `curl osm_ip_address:5001/osm/star_balls`
* Obtain `ip_address` of vnf `faas_pong_vnfd.2` , which would be the target `ip_address` for faas_ping_vnfd.1

### Invoke reconfigure API

Assuming that the `target_ip` value obtained in the previous step is `10.244.4.8`

```bash
curl -H "Content-type: application/json" -POST -d '{"coe_action_params": {"action_params": {"target_ip": "10.244.4.8"}}}' http://osm_ip_address:5001/osm/reconfigure/star_balls/faas_ping_vnfd.1
```

### Invoke ping VNF API

You should notice it replies with 10 times `pong`

```bash
curl 10.30.2.63:30053/ping/10
pongpongpongpongpongpongpongpongpongpong
```

# Use-case 3 UHD over vCDN

**Note:** it is assumed that:

* [FaaS VIM plugin](../vim-plugin) is already loaded into OSM and references to the correct openwhisk
* [Argo](../kubernetes/docs/argo.md) is installed on the correct kubernetes cluster


**Please notice [FaaS Guidelines](../vim-plugin/docs/GUIDELINES.md) before proceeding**

## Onboard Openwhisk actions

Log into OW controller

### bootstrap
```
wsk -i package create vcdn
wsk -i action create /guest/vcdn/bootstrap --docker docker5gmedia/vcdn-bootstrap:b992ac8
```

### vcache
```
wsk -i action create /guest/5g-media/vcache --docker docker5gmedia/vcache-faas:0.0.15
```

## On-board VNFs and NSs

* Log into OSM launchpad
* Goto catalog
* On-board by drag/drop [UC3 packages](https://github.com/5g-media/service-descriptors/tree/master/UC3/ETSI_OSM/faas_vCDN)

## Create the VIMs

Create OpenStack VIM

```
osm vim-create --name Openstack_ENG --user 5gmediauser --password **** --auth_url http://217.172.11.169:5000/v3 --tenant 5gmedia --account_type openstack
```

Create OpenWhisk VIM

Follow this [FaaS VIM plugin](../../../../vim-plugin)

## Instantiate the network service

Instantiate it from OSM GUI under name: `my_cdn`

For NSD-ID, select: faas_vm_vCDN-v1.20

Paste the below into config yaml box (update vim accounts with the correct Ids)

```
{ vnf: [ {member-vnf-index: "1", vimAccountId: 122497ab-3872-41b7-b9b3-8d4dd3624e4a}, {member-vnf-index: "2", vimAccountId: 122497ab-3872-41b7-b9b3-8d4dd3624e4a}, 
{member-vnf-index: "3", vimAccountId: fdf14f71-5dd6-4a0e-bf21-8dd84c78ca6b}, {member-vnf-index: "4", vimAccountId: fdf14f71-5dd6-4a0e-bf21-8dd84c78ca6b}]}
```

### Poll for IngressUrl from VNFR
Log into OSM

Pass `my_cdn` to curl

```bash
curl http://127.0.0.1:5001/osm/my_cdn | jq -r '.vnfs[0].vim_info.IngressUrl'
```


## Spawn event based vcache
Copy url from above IngressUrl

```bash
curl -X POST \
  .../handlerequest \
  -H 'Content-Type: application/json' \
  -d '{
  "kafka_broker": "192.168.111.17:9092",
  "osm_ip": "10.100.176.66",
  "event_uuid": "1",
  "osm_ns": "my_cdn",
  "operation": "spawn_vcache",
  "vnfd_name": "vcache_vnfd",
  "vnfd_index": "2",
  "origin_ip": "192.168.253.3",
  "origin_port": "8080",
  "fqdn": "cdn-uhd.cache-faas-3.5gmedia.lab",
  "vdns_ip": "192.168.111.20",
  "vdns_port": "9999"
  }'
```

## List spawned instances from VNFR
Pass `my_cdn` to curl

```bash
curl http://127.0.0.1:5001/osm/my_cdn | jq -r '.vnfs[1].vim_info.records'
```

## Terminate vcache
Copy url from above IngressUrl

Terminate vcache created by event_uuid "1". (E.g. pass `uuid: "1"`) passing `fqdn`
for the de-registration of it.

```bash
curl -X POST \
  .../handlerequest \
  -H 'Content-Type: application/json' \
  -d '{
  "osm_ip": "10.100.176.66",
  "event_uuid": "2",
  "osm_ns": "my_cdn",
  "operation": "terminate_vcache",
  "fqdn": "cdn-uhd.cache-faas-3.5gmedia.lab",
  "vdns_ip": "192.168.111.20",
  "vdns_port": "9999",
  "uuid": "1"
  }'
```

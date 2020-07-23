# Broadcaster Service
Broadcaster service is a micro service that defines and persists, broadcasters model and their safe-environments (edges).

It also contains the 'edge-selector' component which contacts [SS-CNO](https://github.com/5g-media/CNO/tree/master/SS-CNO-UC2-MC) via [Apache Kafka](https://kafka.apache.org/) to select the most suitable edge.

## Prerequisites

* Publish/subscribe broker as described in [SVP Installation](https://github.com/5g-media/service-virtualization-platform#installation)
* [SS-CNO](https://github.com/5g-media/CNO/tree/master/SS-CNO-UC2-MC) for Use-case 2

## Build docker image [**only if image not in docker5gmedia repository**]
```
sudo docker build --tag docker5gmedia/broadcaster_service:edge-7d3162a --force-rm=true .
sudo docker login --username=docker5gmedia
sudo docker push docker5gmedia/broadcaster_service:edge-7d3162a
```

## Run and configure

Log into OSM

### Start the service (under port 5003)
**Notes:**
* if you would like the edge-selector to use SS-CNO, pass `-e SS_CNO=1`
* if you would like to override broker ipaddress, pass `-e KAFKA_HOST=<ipaddress>`

```
docker run --name broadcaster-service -p 5003:5003 -e CONF_PORT=5003 -e SS_CNO=1 -d docker5gmedia/broadcaster_service:edge-7d3162a
```

### Verify the service
Ensure it responds to the following APIs. You should receive empty results

```
curl --insecure https://osm_ip_address:5003/broadcaster-management/broadcasters
curl --insecure https://osm_ip_address:5003/mc-pop-management/cognitive-pops

REST path:
    osm_ip_address - ipaddress of OSM r5.
```

### Populate data model
Log into OSM

```
chmod +x ./init.sh
./init.sh
```

## Broadcasters APIs

### Add entry
Add new broadcaster entry

```
curl --insecure -H "Content-type: application/json" -POST -d '{"name": "<string>", "description": "<string>"}' https://osm_ip_address:5003/broadcaster-management/broadcasters/<br_id>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    br_id          - broadcaster id (e.g. irt, rtve, bbc)

Data payload:
    name        - full broadcaster name (str)
    description - broadcaster description (str)
```

### Add endpoint
Add broadcaster with remote endpoint. At most two endpoints can be defined for given broadcaster: `safe-remote` and `live-remote`

```
curl --insecure -H "Content-type: application/json" -POST -d '{"name": "<str>", "url": "<str>", "gps": "<str>", "description": "<string>"}' https://osm_ip_address:5003/broadcaster-management/broadcasters/<br_id>/endpoints

REST path:
    osm_ip_address - ipaddress of OSM r5.
    br_id          - broadcaster id (e.g. irt, rtve, bbc)

Data payload:
    name        - endpoint name(str). Valid values 'safe-remote', 'live-remote'
    url         - url to the remote endpoint (str)
    gps         - gps location (str) in coordinate format (e.g. '48.1860 N, 11.6282 E')
    description - broadcaster description (str)
```

### Delete endpoint
Delete broadcaster endpoint

```
curl --insecure -H "Content-type: application/json" -DELETE https://osm_ip_address:5003/broadcaster-management/broadcasters/<br_id>/endpoints/<name>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    name           - endpoint name to delete (e.g. 'safe-remote', 'live-remote')
```

### Delete entry
Delete broadcaster entry

```
curl --insecure -H "Content-type: application/json" -DELETE https://osm_ip_address:5003/broadcaster-management/broadcasters/<br_id>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    br_id          - broadcaster id to delete (e.g. irt, rtve)
```

### Retrieve edge
Get an edge entry for a given broadcaster id

```
curl --insecure -H "Content-type: application/json" -POST -d '{}' https://osm_ip_address:5003/broadcaster-management/broadcasters/<br_id>/edge-selection

REST path:
    osm_ip_address - ipaddress of OSM r5.
    br_id          - broadcaster id (e.g. irt, rtve)

Data payload:
    gps      - gps location (str) in coordinate format (e.g. '48.1860 N, 11.6282 E')
    function - cognitive function(s) to be applied to the contribution; allowed values: 'vspeech', 'vdetection', 'vspeech_vdetection' (str)
    mode     - contribution mode; allowed values: 'safe-local', 'safe-remote' (str)

```

## Cognitive pops APIs

### Add entry
Add edge POP entry

```
curl --insecure -H "Content-type: application/json" -POST -d '{"name": "<str>", "url": "<str>", "gps": "<str>", "broadcasters": ["<br_id1>", ..., "<br_idn>"], "description": "<string>"}' https://osm_ip_address:5003/mc-pop-management/cognitive-pops/<pop_id>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    pop_id         - edge id (e.g. ncsrd, tid)

Data payload:
    name         - full name of edge (str)
    url          - url to the edge gateway (str)
    gps          - gps location (str) in coordinate format (e.g. '48.1860 N, 11.6282 E')
    broadcasters - list of broadcaster ids that belong to this edge (array of str) 
    description  - edge description (str)
```

### Show entry
```
curl --insecure -H "Content-type: application/json" https://osm_ip_address:5003/mc-pop-management/cognitive-pops/<pop_id>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    pop_id         - edge id (e.g. ncsrd, tid)
```

### Delete entry
Delete edge POP entry

```
curl --insecure -H "Content-type: application/json" -DELETE https://osm_ip_address:5003/mc-pop-management/cognitive-pops/<pop_id>

REST path:
    osm_ip_address - ipaddress of OSM r5.
    pop_id         - edge id to delete (e.g. ncsrd, tid)
```

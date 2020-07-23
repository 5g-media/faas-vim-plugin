# Use-case 2 Mobile Contribution

It is assumed that:

* [FaaS VIM plugin](../vim-plugin) is already loaded into OSM and references to the correct openwhisk
* [Broadcaster Service](./broadcaster/service) is running on OSM host
* [Argo](../kubernetes/docs/argo.md) is installed on the correct kubernetes cluster

**Please notice [FaaS Guidelines](../vim-plugin/docs/GUIDELINES.md) before proceeding**

## Onboard Openwhisk actions

Log into OW controller at the edge (i.e. Demokritos edge)

### bootstrap
```
wsk -i package create mobile-contribution
wsk -i action create /guest/mobile-contribution/bootstrap --docker docker5gmedia/mobile-contribution-bootstrap:9b9a966
```

### splitter
```
wsk -i package create 5g-media
wsk -i action create /guest/5g-media/splitter --docker docker5gmedia/splitter:faas-5ce8a2c
```

### vspeech
```
wsk -i action create /guest/5g-media/vspeech_gpu -A ../openwhisk/actions/gpu-annotations.json --docker docker5gmedia/vspeech:faas_gpu-e5896bc
wsk -i action create /guest/5g-media/vspeech_cpu -A ../openwhisk/actions/cpu-annotations.json --docker docker5gmedia/vspeech:faas-6501fd2
```

### vdetection
```
wsk -i action create /guest/5g-media/vdetection_gpu -A ../openwhisk/actions/gpu-annotations.json --docker docker5gmedia/vdetection:faas_gpu-9ca0688
wsk -i action create /guest/5g-media/vdetection_cpu -A ../openwhisk/actions/cpu-annotations.json --docker docker5gmedia/vdetection:faas-35643fb
```

### Gateway actions

```
wsk -i action create /guest/mobile-contribution/session_instantiate session_instantiate.py --web true
wsk -i action create /guest/mobile-contribution/session_instantiate_poll session_instantiate_poll.py --web true
wsk -i action create /guest/mobile-contribution/session_initialize session_initialize.py --web true
wsk -i action create /guest/mobile-contribution/session_initialize_poll session_initialize_poll.py --web true
wsk -i action create /guest/mobile-contribution/session_finalize session_finalize.py --web true
```

### Expose actions as API endpoints

```
wsk -i api create /session /instantiate post /guest/mobile-contribution/session_instantiate --response-type http
wsk -i api create /session /instantiate_poll get /guest/mobile-contribution/session_instantiate_poll --response-type http
wsk -i api create /session /initialize post /guest/mobile-contribution/session_initialize --response-type http
wsk -i api create /session /initialize_poll get /guest/mobile-contribution/session_initialize_poll --response-type http
wsk -i api create /session /finalize post /guest/mobile-contribution/session_finalize --response-type http
```

## On-board VNFs and NSs

* Log into OSM launchpad
* Goto catalog
* On-board by drag/drop [UC2.b packages](https://github.com/5g-media/service-descriptors/tree/master/UC2/UC2b)

## Run and configure Broadcaster Service

Log into OSM

### Start the service

```bash
docker run --name broadcaster-service -p 5003:5003 -e CONF_PORT=5003 -e SS_CNO=1 -d docker5gmedia/broadcaster_service:edge-7d3162a
```

### Populate data model

```bash
chmod +x ./broadcaster/service/init.sh
./broadcaster/service/init.sh
```

## Start RTMP Service

Log into a VM at the edge (i.e. Demokritos edge)

This RTMP service is configured to record the stream for safe-local mode

```bash
docker run -p 1935:1935 -p 8080:8080 -e RTMP_STREAM_NAMES=detection docker5gmedia/rtmp-sink:v3.1
```

# Typical flow

The steps/sections below illustrate a basic flow which [Mobile Journalist App emulator](broadcaster/tools/end-to-end-flow.sh) automates.

**Note:** for the sake of brevity main flow steps are described. For a full end to end example, refer to [Mobile Journalist App emulator](broadcaster/tools/end-to-end-flow.sh)

## Edge selection

Invoke a REST API against the edge selection service. Pass broadcaster ID, GPS location and the Function(s) to be used

```bash
curl --insecure -X POST -d '{"gps": "37.987 N, 23.750 E", "function": "vdetection", "mode": "safe-local"}' https://osm_ip_address:5003/broadcaster-management/broadcasters/irt/edge-selection
```

The below response is returned:

```
{
  "session_uuid":"0f58a27d270e4f75942825f4dc66be01"
}
```

Retrieve selected edge result (passing the above session_uuid)

```bash
curl --insecure https://osm_ip_address:5003/broadcaster-management/broadcasters/irt/edge-selection/0f58a27d270e4f75942825f4dc66be01
```

The below response is returned:

```
{
  "description": "A safe local environment at Demokritos 5G edge",
  "gps": "37.9992 N, 23.8194 E",
  "name": "Demokritos",
  "session_uuid": "0f58a27d270e4f75942825f4dc66be01",
  "resource": {
    "CPU": [],
    "GPU": [
      "vdetection"
    ],
    "nfvi_uuid": "ncsrd"
  },
  "url": "http://10.30.2.56:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502"
}
```

## Create contribution session

### Instantiate session

```bash
curl --insecure -X POST -d '{"br-id": "irt", "mode": "safe-local", "function": "vdetection", "session_uuid": "0f58a27d270e4f75942825f4dc66be01"}' -H "Content-Type: application/json" https://10.30.2.56:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502/session/instantiate
```

Wait for the result to appear. The result contains the created session uuid

```
{
  "session-uuid": "0f954b302e324f7ab967d91452a2835e"
}
```

### Initialize session

Initialize session is an async operation that needs to be polled until a successfully completion

```bash
curl --insecure -X POST -d '{"br-id": "irt", "mode": "safe-local", "function": "vdetection", "session_uuid": "0f58a27d270e4f75942825f4dc66be01", "resource": {"CPU": [], "GPU": ["vdetection"]} }' -H "Content-Type: application/json" https://10.30.2.56:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502/session/initialize
```

### Poll session status
Poll session creation status until it completes either reaches `Succeeded` or `Failed`. Append `session/initialize_poll` to `url` above and pass br-id, session-uuid and event-uuid (returned in previous call)

```bash
curl --insecure 'https://10.30.2.56:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502/session/initialize_poll?br-id=irt&event-uuid=9f476ce873c7471b9b496ebe5f2099c9&session-uuid=9272aa982cb148ada43f24be63edf2c2'
```

```
{
  "phase": "Running",
  "session-uuid": "0f954b302e324f7ab967d91452a2835e",
  "event-uuid": "9f476ce873c7471b9b496ebe5f2099c9"
}
```

until it completes

```
{
  "event-uuid": "9f476ce873c7471b9b496ebe5f2099c9",
  "ipaddress": "10.30.2.54",
  "phase": "Succeeded",
  "port": "30636",
  "session-uuid": "0f954b302e324f7ab967d91452a2835e"
}
```

## Stream content
Stream to `10.30.2.54:30636`

E.g. `sudo docker run docker5gmedia/srtx -fflags +genpts -re -i https://www.dropbox.com/s/scdv2ibc1eb9zkw/time.mp4?raw=1 -c copy -y -f mpegts srt://10.30.2.54:30636?pkt_size=1316`

## Finalize contribution session
Once streaming is over, invoke the below

```bash
curl --insecure -X POST -d '{"br-id": "irt", "session-uuid": "0f954b302e324f7ab967d91452a2835e", "event-uuid": "9f476ce873c7471b9b496ebe5f2099c9"}' -H "Content-Type: application/json" https://10.30.2.56:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502/session/finalize
```

The result contains the url to contribution entry stored in broadcaster service

```
{
  "contribute-url": "http://osm_ip_address:5003/broadcaster-management/broadcasters/irt/contributions/0f954b302e324f7ab967d91452a2835e",
  "session-uuid": "0f954b302e324f7ab967d91452a2835e"
}
```

## Retrieve contribution entry
Access broadcaster service to retrieve media and metadata file(s)

```bash
curl http://osm_ip_address:5003/broadcaster-management/broadcasters/irt/contributions/9272aa982cb148ada43f24be63edf2c2
{
  "url-media": "http://10.30.2.54:8080/0f954b302e324f7ab967d91452a2835e.flv",
  "req_url_vdetection": "http://10.30.2.54:8080/0f954b302e324f7ab967d91452a2835e.objects.ass"
}
```

Continue with the below step when you have two metadata files; the above url indicates both `req_url_vspeech` and `req_url_vdetection` which happens if you instantiated the session with `"function": "vspeech_vdetection"`

## Merge Metadata files
Information about this tool can be found [here](./broadcaster/tools/#merging-metadata)

1. From a linux host that has docker installed, run merge_metadata.sh passing it the contribution URL
   ```
   ./merge_metadata.sh http://osm_ip_address:5003/broadcaster-management/broadcasters/irt/contributions/0f954b302e324f7ab967d91452a2835e
   ```
   **Note:** first run may take time since docker pulls a container image used by the script

1. The script should output: "Produced merge file...". Open VLC to play the *.flv file you downloaded at [Retrieve contribution entry](#retrieve-contribution-entry) step.
   **Tip:** if the produced `*.all.ass` file is placed in same folder flv located, then VLC should automatically apply it

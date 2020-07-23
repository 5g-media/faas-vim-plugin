# FaaS VIM OSM Plugin
Plug-in that implements OSM R5 abstract VIM class interfacing with Openwhisk on its south bound

## Installation

### Install 5G-MEDIA SVP OSM v5.0.5
Follow [these instructions](docs/install_osm_with_faas.md) to install OSM with FaaS support

### Install Openwhisk actions
Follow [these instructions](../openwhisk/actions/internal) to install internal Openwhisk actions used by the FaaS plug-in

## Create FaaS VIM Instance

### Invoke the following command from OSM host

Log into OSM

Replace ipaddresses/ports/token with environment specific:
```bash
osm vim-create --name <faas vim name> --auth_url "https://<ow-api-ip>:<ow-api-port>" --tenant whisk --account_type faas --config '{offload-service-url: "http://<k8s-master-ip or minikube-ip>:<service_port>", proxierPort: "<proxier_port>", offload-action: "/guest/k8s_pkg/offload", auth_token: <auth_token>}'
```

### Verify Plugin state

* Select VIM Accounts
* Ensure FaaS VIM Operational State set to `Enabled`

### The following arguments are supported:

*   `name` | *string*
    * Name of this VIM instance (e.g. openwhisk_k8s_vim)
    * **Required** 

*   `auth_url` | *string*
    * URL of Openwhisk management API (e.g. https://ow-api-ip:443)
      Note: make sure to surround it with quotes
    * **Required**

*   `tenant` | *string*
    * Openwhisk tenant that will be used for this FaaS VIM (e.g. whisk.sys)
    * **Required (currently being ignored)**

*   `account_type` | *string*
    * VIM type. Should be set with: faas
    * **Required**

*   `offload-service-url` | *string*
    * URL of Openwhisk offload-service (e.g. http://172.16.0.251:31567)
      Note: make sure to surround it with quotes
    * **Required**
*   `proxierPort` | *string*
    * Port of proxier service (e.g. "31567")
      Note: make sure to surround it with quotes
    * **Required**
*   `offload-action` | *string*
    * Fully qualified internal action name responsible to offload the action 
      (e.g. /guest/k8s_pkg/offload)
    * **Required**

*   `auth_token` | *string*
    * Openwhisk API authentication token. Note: make sure to surround it with quotes
    * **Required**

**Example:**
```bash
osm vim-create --name FaaS_VIM --auth_url "https://172.15.0.50:443" --tenant whisk --account_type faas --config '{offload-service-url: "http://172.15.0.251:30197", proxierPort: "38152", offload-action: "/guest/k8s_pkg/offload", auth_token: "23bc46b1-71f6-4ed5-8c54-816aa4f8c502:123zO3xZCLrMN6v2BKK1dXYFpXlPkccOFqm12CdAsMgRU4VrNZ9lyGVCGuMDGIwP"}'
```

# All-in-one FaaS Development Environment

## Set-up
Create a **fresh** Linux Ubuntu 16.04 VM with 2vCPU, 8GB memory and 50GB disk. (For single VM that includes OSM as well, 12GB memory and 100GB disk) This VM will serve as a local development sandbox for your FaaS VNFs.  

**Install the following in this order**

## Ensure your system is up to date

```bash
sudo apt-get update
sudo apt-get upgrade
```

## OSM
Start with: [Installing OSM for 5G-MEDIA](../vim-plugin/docs/install_osm_with_faas.md)

## Lean Openwhisk
All-in-one openwhisk
Install [lean openwhisk](efx)

## Minikube
All-in-one kubernetes cluster
Install [minikube](minikube)

## Start working with openwhisk
Follow the [FaaS-VIM plugin installation instructions](../vim-plugin/README.md)

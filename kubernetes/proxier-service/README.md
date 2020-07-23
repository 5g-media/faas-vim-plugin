# Proxier Service

Proxier service is responsible for creating and deleting serverless orchestrator assets (i.e Gateway and Sensor) on the creation and termination of FaaS network service instances. It also provides management endpoint APIs for serverless flow status and configuration for the FaaS VIM to use.

**Note:** it is assumed that:

* [Argo](../../docs/argo.md) is installed on the correct kubernetes cluster

### Deploy the service into kubernetes cluster

Log into kubernetes master

* Create role and its binding to manage secretes, pods and jobs:
    * `kubectl create -f rbac/role.yaml`

* Create deployment resources:
    * `kubectl create -f config/deployment.yaml`
* Create NodePort service:
    * `kubectl create -f config/service.yaml`

### Build and push docker images (**relevant for developers only**)

* Run the following commands under `sudo`. Replace username with your dockerhub userid e.g. docker5gmedia:
    * `docker build --tag "docker5gmedia/proxier-server:0.1" --force-rm=true .`
    * `docker login --username=docker5gmedia`
    * `docker push docker5gmedia/proxier-server:0.1`

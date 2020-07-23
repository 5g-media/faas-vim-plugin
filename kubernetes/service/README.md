# Offloader server

Offloader server is responsible for offloading openwhisk actions into
kubernetes cluster. It also provides management endpoint API of kubernetes
resources such as pods, networks, etc.. for the FaaS VIM to use.

## Installation
It is assumed that you already have kubernetes cluster installed. If not,
follow the instructions to:
* [Install `docker`, `kubeadm`, `kubectl`](https://kubernetes.io/docs/tasks/tools/install-kubeadm/)
* [Bootstrap kubernetes cluster with flannel network](https://kubernetes.io/docs/setup/independent/create-cluster-kubeadm/)

### Define RBAC roles

The offloader service POD should have special RBAC role to successfully call
kubernetes APIs on various resources. Therefore the following role should be added for
the `default` service account.

* Log into kubernetes master
* Create role and its binding to manage secretes, pods and jobs:
    * `kubectl create -f rbac/offload-role.yml`
    * `kubectl create -f rbac/offload-role-bind.yml`

* Verify their creation:
    * `kubectl get role`
    * `kubectl get rolebinding`

**Note:** It is assumed that `default` namespace and service account being used.

### Deploy the service into kubernetes cluster

* Log into kubernetes master
* Label the nodes you want the offloader to be deployed on:
```
kubectl label nodes <node name> offloader=true
```
* Create deployment resources:
    * `kubectl create -f config/offload-deployment.yml`
* Wait for the deployments to come up
    * `kubectl get deployment` and inspect AVAILABLE
* Create NodePort service:
    * `kubectl create -f config/offload-service.yml`
* Retrieve `offload-port`:
    * `kubectl describe service ow-offloadservice | grep http-api | grep NodePort| awk '{print $3}' | cut -d'/' -f1`

### Ensure server is reachable from openwhisk

* Log into openwhisk controller host
* Run the following command and ensure it returns greeting (replace `offload-port` with the one retrieved in previous step):
    * `curl http://<kubernetes master host ip>:<offload-port>/hello`

### Build and push docker images (**relevant for developers only**)

* Run the following commands under `sudo`. Replace username with your dockerhub userid e.g. docker5gmedia:
    * `docker build --tag "<username>/ow-offload-serverprereqs:0.1" --force-rm=true --file ./Dockerfile.prereq .`
    * `docker build --tag "docker5gmedia/ow-offload-server:c056640" --force-rm=true --file ./Dockerfile.server .`
    * `docker login --username=docker5gmedia`
    * `docker push docker5gmedia/ow-offload-server:c056640`
    
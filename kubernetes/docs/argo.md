# Argo workflow engine

Log into kubernetes master

(commands taken from [install-argo](https://github.com/argoproj/argo/blob/master/demo.md)) manual.

### Argo CLI

```
sudo curl -sSL -o /usr/local/bin/argo https://github.com/argoproj/argo/releases/download/v2.4.2/argo-linux-amd64
sudo chmod +x /usr/local/bin/argo
```

### Argo controller

```
kubectl create namespace argo
kubectl apply -n argo -f https://raw.githubusercontent.com/argoproj/argo/v2.4.2/manifests/install.yaml
```

### Configure service account

```
kubectl create rolebinding default-admin --clusterrole=admin --serviceaccount=default:default
```

### Argo events v0.11

Clone argo events v0.11 repository
```
cd ~
git clone https://github.com/5g-media/argo-events.git
cd argo-events
git checkout v0.11-branch
```

Create namespace

```
kubectl create namespace argo-events
```

Apply the below manifests (in this order)

```
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/argo-events-sa.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/argo-events-cluster-roles.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/sensor-crd.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/gateway-crd.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/sensor-controller-configmap.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/gateway-controller-configmap.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/sensor-controller-deployment.yaml
kubectl apply -n argo-events -f ~/argo-events/hack/k8s/manifests/gateway-controller-deployment.yaml
```

### Apply RBAC

```
cd ~/faas-vim-plugin/kubernetes
kubectl create -f ./argo-k8s-resource-admin-role.yaml -n argo-events
```

### Apply generic event-source

```
cd ~/faas-vim-plugin/kubernetes
kubectl create -f ./fiveg-media-event-source.yaml -n argo-events
```

### Apply common workflow templates

```
cd ~/faas-vim-plugin/openwhisk/actions
kubectl create -f ./workflow-base.yaml -n argo-events
```

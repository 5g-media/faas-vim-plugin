# Kubernetes Monitoring

The following instructions are verified to work with kubernetes v1.11.2

Log in to master

```bash
cd ~
git clone https://github.com/5g-media/kubernetes-prometheus.git
cd kubernetes-prometheus
git checkout 7a0dd19d03c8909420ee1031ea5c5509cde134df
```

```
kubectl create namespace monitoring
kubectl create -f clusterRole.yaml
kubectl create -f config-map.yaml
kubectl create -f prometheus-deployment.yaml 
```

```
kubectl create -f prometheus-service.yaml --namespace=monitoring
```

## Install Grafana
Login to master

```
docker run -d -p 3000:3000 --name grafana grafana/grafana:4.6.3
```

## Configure Grafana

Login to UI: http://master_ip_address:3000(admin:admin)

### Create data source

* Type: Prometheus
* HTTP Settings -> URL: http://master_ip_address:30000
* Access: Proxy
* Save and Test

### Import dashboard
* Dashboard -> Import
* From json -> Paste contents of `5G MEDIA Apache OpenWhisk VIM-GPU-1536160005130.json`


## Install Kube State Metrics (to expose kube_pod_labels)

Log into master

```bash
cd ~
git clone https://github.com/kubernetes/kube-state-metrics.git
cd kube-state-metrics
git checkout 1b79b318b25f80aa1a771e5da7611c69a4888304
kubectl apply -f kubernetes
```

## Add GPU Host metrics
TBD

## Note
If, nevertheless, you are using a recent kubernetes cluster, pay attention to [removed-cadvisor-metric-labels](https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG-1.16.md#removed-metrics)
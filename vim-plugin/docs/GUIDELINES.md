# Guidelines for FaaS Network services and VNFs

This document contains the following topics:

* [Naming conventions](./GUIDELINES.md#naming-conventions)
* [Short lived VNFs](./GUIDELINES.md#short-lived-vnfs)
* [Manual cleaning of Kubernetes resources](./GUIDELINES.md#manual-cleaning-of-kubernetes-resources)
* [Manual cleaning of OSM NS instances](./GUIDELINES.md#manual-cleaning-of-osm-ns-instances)
* [OSM recovery procedure](./GUIDELINES.md#osm-recovery-procedure)
* [Large runtime images](./GUIDELINES.md#large-runtime-images)
* [FaaS VNF outputs](./GUIDELINES.md#faas-vnf-outputs)

### Naming conventions

* VNFD and NSD names should contain only alphanumeric and underscores (`_`)
* Network service should be instantiated under name containing only alphanumeric and underscores (`_`)
* Do not instantiate two network services with same name

### Short lived VNFs

* FaaS VNF PODs automatically terminated after 1 hour. Delete the network service
when done or before 1 hour elapse.

### Manual cleaning of Kubernetes resources

In case VNF residuals exist in Kubernetes cluster

Login to kubernetes master:

```
kubectl get pod
kubectl get job
kubectl get services
```

Delete resources starting with `offload-invoker-`

```
kubectl delete pod <POD NANE>
kubectl delete job <JOB NAME>
kubectl delete services <SERVICE NAME>
```

### Manual cleaning of OSM NS instances

Log into OSM

In case of NSD VNFR resources exist even though NS is delete E.g the below curl returns data (we use sky_balls example here)
```bash
curl 127.0.0.1:5001/osm/sky_balls | jq .
```

Log into RO container
```bash
docker ps --all | grep osm_ro.1
docker exec -it <container ID> /bin/bash
```

List NS from inside RO container and locate the ones to delete
```bash
openmano instance-scenario-list
```

Delete the instance
```bash
openmano instance-scenario-delete <ID>
Delete scenario instance 8514d669-45e8-4e04-8503-26d19c72cdb8 (y/N)? y
```

Issue instance-scenario-list again to ensure it is deleted and exit the container (`^D`)

Run curl again to ensure no ns exists
```bash
curl 127.0.0.1:5001/osm/sky_balls | jq .
```

### OSM recovery procedure

Log into OSM

* Shutdown OSM
  ```bash
  sudo docker stack rm osm && sleep 60
  ```

* Delete OSM volumes
  ```bash
  sudo docker volume rm osm_mongo_db osm_mon_db osm_ro_db osm_prom_db
  ```

* Launch OSM
  ```bash
  sudo docker stack deploy -c /etc/osm/docker/docker-compose.yaml osm
  ```

* Wait for the service to run
  ```bash
  sudo docker stack ps osm | grep -i running
  ```

### Large runtime images

FaaS VNF (media) runtime images are large. When an action is being invoked for the first time, OpenWhisk invoker pulls them out from docker hub. Depending on the network conditions this can take a fairly amount of time and can cause timeouts for the action invocation. In oder to avoid this, pull your VNF docker images in advance, by invoking these commands from all of cluster nodes.

Replace IMAGE_NAME with your docker5gmedia repository images (e.g. docker5gmedia/action-vdetection, docker5gmedia/transcoder_2_8_4)

```
docker pull <IMAGE_NAME>
```

### FaaS VNF outputs

Perform NS instantiation as usual

* Locate your pod in interest (e.g. vtranscoder, vbroker, ...)

  Log into Kubernetes master

  **Note:** You may need to run these command under sudo

  ```
  kubectl get pod --show-labels | grep vtranscoder
  kubectl get pod --show-labels | grep vbroker
  ```

  You should see similar output to this

  ```
  offload-invoker-58f3b6d40a99411b8522c7799d2e79d5-49hqt   1/2     Running   0          23s   controller-uid=909f4595-f5b1-11e9-b8e8-000c29298102,flowId=307510ebf36d4b3a98068369daa48141,job-name=offload-invoker-58f3b6d40a99411b8522c7799d2e79d5,job-type=ow-offload-job,jobId=58f3b6d40a99411b8522c7799d2e79d5,ow_action=guest_5g-media_vtranscoder_2_8_4,vim_id=f3af61b2db2442a2af61b2db2482a26c
  offload-invoker-6074dfba7c454b09833cda4434708769-q74l2   2/2     Running   0          23s   controller-uid=9067be87-f5b1-11e9-b8e8-000c29298102,flowId=eccf93527055413fb9bb0fafc6e913b8,job-name=offload-invoker-6074dfba7c454b09833cda4434708769,job-type=ow-offload-job,jobId=6074dfba7c454b09833cda4434708769,ow_action=guest_5g-media_vtranscoder_2_8_4,vim_id=15aef14d9f544d13aef14d9f546d13b1
  ```

  **Note:** 1/2 means that one of the VNFs had crashed.

* Print Logs
  For example, retrieving outputs of the failed VNF, invoke similar to the below supplying your pod ID
  ```
  kubectl logs offload-invoker-58f3b6d40a99411b8522c7799d2e79d5-49hqt -c ow-action
  
  ../../executables/transcoder_gpu: error while loading shared libraries: libcuda.so.1: cannot open shared object file: No such file or directory
  COMMAND TO BE EXECUTED: '$ export LD_LIBRARY_PATH=../../executables;../../executables/transcoder_gpu "{\"_VNF_IDX\": \"1\", \"gpu_node\": \"1\", \"metrics_broker_ip\": \"192.158.1.175\", \"metrics_broker_port\": \"9092\", \"metrics_broker_topic\": \"app.vtranscoder3d.metrics\", \"produce_profiles\": [1, 4], \"send_broker_ip\": \"0.0.0.0\", \"send_broker_port\": \"32768\", \"_VIM_VM_ID\": \"f3af61b2db2442a2af61b2db2482a26c\"}"'
  
  ```

  For example, retieving outputs of the other VNF
  ```
  kubectl logs offload-invoker-6074dfba7c454b09833cda4434708769-q74l2 -c ow-action

  NO "gpu_node" OPTION FOUND! FALLBACK TO DEFAULT SETTINGS...
  
  COMMAND TO BE EXECUTED: '$ export LD_LIBRARY_PATH=../../executables;../../executables/transcoder_cpu "{\"_VNF_IDX\": \"2\", \"_VIM_VM_ID\": \"15aef14d9f544d13aef14d9f546d13b1\"}"'
  
  TRANSCODER ON! (v2.8.4.5-CPU)
  
  NO STARTING SEND-BROKER CONNECTION INFORMATION FOUND! WAITING TO ARRIVE...
  ```

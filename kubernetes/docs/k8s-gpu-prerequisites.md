# Nvidia-GPU Node

Start with preparing your GPU host(s) to be installed with needed drivers so that they can function as Kubernetes GPU node(s).

You need to install nvidia drivers and nvidia-docker in each GPU node you have.

## Setup

Perform the below steps for every GPU host you have **until** (not including) [Install Nvidia k8s plugin](#install-nvidia-k8s-plugin) section

Start with a **fresh** Ubuntu 16.04 system, 4 CPU cores, 16 GB RAM, more then 100 GB disk and GeoForce (`GeForce GTX 1080 Ti`) GPU.

### Nvidia cuda drivers

Follow [cuda-installation-guide-linux](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html) instructions to install nvidia and cuda drive on your system

Then, reboot your host and verify cuda driver installation:

```
nvidia-smi
```

### Docker-CE 18.06.0

On your GPU nodes, install this specific version of [docker](https://docs.docker.com/install/linux/docker-ce/ubuntu/) verified to be working with Nvidia and Kubernetes.

The below commands are taken from the docker installation guide.

```
sudo apt-get update
```

Install some utilities
```
sudo apt-get install \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common
```

Add the key and ensure its fingerprint
```
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
```

Register docker repository
```
sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
sudo apt-get update
```

Install docker 18.06.0
```
sudo apt-get install docker-ce=18.06.0~ce~3-0~ubuntu containerd.io
```

Verify docker
```
sudo docker run hello-world
```

### nvidia-docker runtime

Your next step would be to install nvidia docker runtime. It should be matched with the docker version you installed. Refer to [nvidia-docker]([https://github.com/NVIDIA/nvidia-docker) for more information.

In short, follow the below instructions

Add the package repositories:
```
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | \
  sudo apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
```

Install the matched version. Command taken from [here](https://github.com/NVIDIA/nvidia-docker/wiki/Frequently-Asked-Questions#how-do-i-install-20-if-im-not-using-the-latest-docker-version)
```
sudo apt-get install -y nvidia-docker2=2.0.3+docker18.06.0-1 nvidia-container-runtime=2.0.0+docker18.06.0-1
```

Restart the daemon
```
sudo pkill -SIGHUP dockerd
```

Test nvidia-smi with the latest official CUDA image
```
sudo docker run --runtime=nvidia --rm nvidia/cuda:9.0-base nvidia-smi
```

You will need to enable the nvidia runtime as your default runtime on your node. We will be editing the docker daemon config file which
is usually present at /etc/docker/daemon.json

```
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
```

Restart docker
```
sudo service docker stop
sudo service docker start
```

### Join your host with Kubernetes cluster

[Turn swap off](kubernetes.md#turn-swap-off), continue with installing [kubelet, kubectl and kubeadm](kubernetes.md#kubelet-kubectl-kubeadm) finally, [join](kubernetes.md#kubeadm-join-working-nodes) your host


## Install Nvidia k8s plugin

Log into kubernetes master

Command taken from [enabling-gpu-support-in-kubernetes](https://github.com/NVIDIA/k8s-device-plugin#enabling-gpu-support-in-kubernetes)

```
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/1.0.0-beta/nvidia-device-plugin.yml
```

### Verify pod can consume GPU

Create the following pod definition yaml
```
cat <<EOF > pod-gpu.yaml
apiVersion: v1
kind: Pod
metadata:
  name: cuda-vector-add
spec:
  restartPolicy: OnFailure
  containers:
    - name: cuda-vector-add
      image: "k8s.gcr.io/cuda-vector-add:v0.1"
      resources:
        limits:
          nvidia.com/gpu: 1 # requesting 1 GPU
EOF
```

Create the POD
```
kubectl create -f pod-gpu.yaml
```

Wait for it to enter `Completed` state and verify its logs

```
kubectl logs cuda-vector-add
```

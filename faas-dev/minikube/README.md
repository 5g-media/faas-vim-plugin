# Minikube Installation

Follow the instructions below.

**Pay attention to** `--vm-driver=none` you will need to supply it later on.

* Log into your SDK VM

* Install kubectl v1.12.2  
  Tip: below instructions taken from [Install kubectl binary using curl](https://kubernetes.io/docs/tasks/tools/install-kubectl/#install-kubectl-binary-using-curl) **under  `Linux` tab**
  ```
  cd ~
  curl -LO https://storage.googleapis.com/kubernetes-release/release/v1.12.2/bin/linux/amd64/kubectl
  chmod +x ./kubectl
  sudo mv ./kubectl /usr/local/bin/kubectl
  ```
* Install minikube version 0.30.0
  ```
  curl -Lo minikube https://storage.googleapis.com/minikube/releases/v0.30.0/minikube-linux-amd64 && chmod +x minikube && sudo cp minikube /usr/local/bin/ && rm minikube
  ```
* Install socat
  ```
  sudo apt-get install socat
  ```

* Start minikube
  ```
  sudo minikube start --vm-driver=none
  ```

* Put the docker network in promiscuous mode. **Note:** Make sure to setup the Docker network each time after `minikube start` if you ran `minikube delete` as this configuration will be lost.
  ```
  sudo ip link set docker0 promisc on
  ```
* Ensure minikube properly works
  ```
  sudo minikube status
  ```

* Create the roles
  ```
  sudo kubectl create -f roles.yml
  ```

* Create the offload service
  ```
  sudo kubectl create -f offload.yml
  ```

* Ensure offload-service POD responds by retrieving the ipaddress and port and pasting it in curl
  ```
  sudo minikube ip
  sudo kubectl describe service ow-offloadservice | grep http-api | grep NodePort| awk '{print $3}' | cut -d'/' -f1
  curl <MINIKUBE IP>:<OFFLOAD PORT>/hello
  ```
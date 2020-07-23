# Lean Openwhisk
Log into your SDK VM

The below instructions inspired from [Openwhisk setup on ubuntu](https://github.com/apache/incubator-openwhisk/blob/master/tools/ubuntu-setup/README.md)

## Clone git repository
```bash
# Go to home directory
cd ~

# Install git if it is not installed
sudo apt-get install git -y

# Clone openwhisk
git clone https://github.com/apache/incubator-openwhisk.git openwhisk

# Change current directory to openwhisk
cd openwhisk
```

## Have installer script to install specific docker version (required by minikube)

```bash
vi ~/openwhisk/tools/ubuntu-setup/docker-xenial.sh
```

Replace `DOCKER` snippet with the below one. Ensure to *comment out:* `sudo apt-get install -y docker-ce`  

```bash
# DOCKER

# NOTE: For the moment, this script will use the latest stable version of
#       Docker CE.  When OpenWhisk locks down on a version of Docker CE to use,
#       it can then be locked in using the commented lines
sudo apt-get install -y docker-ce=17.09.1~ce-0~ubuntu
#sudo apt-mark hold docker-engine
#sudo apt-get install -y docker-ce  # Replace with lines above to lock in version
```

## Install Open JDK 8 and docker

```bash
# Install all required software
(cd tools/ubuntu-setup && ./all.sh)
```

## Ensure docker version is 17.09.1
```bash
sudo docker version
```
## Build openwhisk

```bash
cd ~/openwhisk
sudo ./gradlew distDocker
```

## Install pre-requisites needed for openwhisk deployment

```bash
sudo apt-get install npm
sudo apt-get install python-pip
sudo pip install ansible==2.5.2
sudo pip install jinja2==2.9.6
cd ~/openwhisk/ansible
sudo ansible-playbook setup.yml
sudo ansible-playbook prereq.yml
```

## Kickoff Lean Openwhisk installation

```bash
cd ~/openwhisk
sudo ./gradlew distDocker
cd ansible
sudo ansible-playbook couchdb.yml
sudo ansible-playbook initdb.yml
sudo ansible-playbook wipe.yml
sudo ansible-playbook openwhisk.yml -e lean=true
sudo ansible-playbook postdeploy.yml
sudo ansible-playbook apigateway.yml
sudo ansible-playbook routemgmt.yml
```

## Configure Openwhisk client

Create and edit `~/.wskprops` with the below replacing `ipaddress` with VM ipaddress

```
APIHOST=https://ipaddress:443
NAMESPACE=guest
AUTH=23bc46b1-71f6-4ed5-8c54-816aa4f8c502:123zO3xZCLrMN6v2BKK1dXYFpXlPkccOFqm12CdAsMgRU4VrNZ9lyGVCGuMDGIwP
```

### Verify openwhisk operation
```
~/openwhisk/bin/wsk -i list
~/openwhisk/bin/wsk -i package create test_package
~/openwhisk/bin/wsk -i action create test_package/hello-action ~/openwhisk/tests/dat/actions/hello.py
~/openwhisk/bin/wsk -i action invoke -r test_package/hello-action
```

### Restart Openwhisk
Openwhisk does not restart automatically during VM restart.

```
cd  ~/openwhisk/ansible
sudo ansible-playbook openwhisk.yml -e lean=true
```
Then, refer to [verify openwhisk operation](#verify-openwhisk-operation)
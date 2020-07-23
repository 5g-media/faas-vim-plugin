# Openwhisk installation

The below commands are taken from [Openwhisk installation guide](https://github.com/apache/openwhisk/blob/master/tools/ubuntu-setup/README.md)

Start with a fresh Ubuntu 18.04 VM (2vCPUs, 8GB RAM, 50GB disk)

Clone git repository

```
cd ~
git clone https://github.com/apache/openwhisk.git openwhisk
cd openwhisk
```

Install needed software

```
(cd tools/ubuntu-setup && ./all.sh)
```

## Install npm pre-requisite
```
sudo apt-get install npm
```

## Build openwhisk

```bash
cd ~/openwhisk
sudo ./gradlew distDocker
```

## Install pre-requisites needed for openwhisk deployment

```bash
sudo apt-get install python-pip
sudo pip install ansible==2.5.2
sudo pip install jinja2==2.9.6
cd ~/openwhisk/ansible
sudo ansible-playbook setup.yml
sudo ansible-playbook prereq.yml
```

## Kickoff Openwhisk installation

```bash
cd ~/openwhisk
sudo ./gradlew distDocker
cd ansible
sudo ansible-playbook couchdb.yml
sudo ansible-playbook initdb.yml
sudo ansible-playbook wipe.yml
sudo ansible-playbook openwhisk.yml
sudo ansible-playbook postdeploy.yml
sudo ansible-playbook apigateway.yml
sudo ansible-playbook routemgmt.yml
```


## Configure Openwhisk CLI

```
sudo cp ~/openwhisk/bin/wsk /usr/local/bin
```

Create and edit `~/.wskprops` with the below replacing `ipaddress` with VM ipaddress

```
APIHOST=https://ipaddress:443
NAMESPACE=guest
AUTH=23bc46b1-71f6-4ed5-8c54-816aa4f8c502:123zO3xZCLrMN6v2BKK1dXYFpXlPkccOFqm12CdAsMgRU4VrNZ9lyGVCGuMDGIwP
```

### Verify openwhisk operation
```
wsk -i list
wsk -i package create test_package
wsk -i action create test_package/hello-action ~/openwhisk/tests/dat/actions/hello.py
wsk -i action invoke -r test_package/hello-action
```

**Tip:** To reduce disk space delete unused runtime images

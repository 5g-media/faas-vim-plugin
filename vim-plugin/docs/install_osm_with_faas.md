# Open Source Mano Installation

This page contains installation instructions for OSM v5.0.5 with FaaS capabilities (verified with Ubuntu 16.04)

Log into the OSM host

### Prerequisites
* update/upgrade the packages
  ```
  sudo apt-get update
  sudo apt-get upgrade
  ```

* add your root username (e.g. `,localadmin`) to /etc/group, /etc/gshadow at `lxd` entries

## Download, modify and run the script
```bash
cd ~
wget https://osm-download.etsi.org/ftp/osm-5.0-five/install_osm.sh
chmod +x install_osm.sh
```
```
vi install_osm.sh
Comment line: #/usr/share/osm-devops/installers/full_install_osm.sh -R $RELEASE -r $REPOSITORY -u $REPOSITORY_BASE -D /usr/share/osm-devops -t latest "$@"
```
```
./install_osm.sh
```

## Update scripts to install specific docker version
```
sudo vi /usr/share/osm-devops/installers/full_install_osm.sh
```
Under `install_docker_ce()` replace `docker version` if statement with the below:
```
sudo apt-get install -y docker-ce=17.09.1~ce-0~ubuntu
```
```
vi install_osm.sh
Comment line: #sudo DEBIAN_FRONTEND=noninteractive apt-get install osm-devops
Uncomment line: /usr/share/osm-devops/installers/full_install_osm.sh -R $RELEASE -r $REPOSITORY -u $REPOSITORY_BASE -D /usr/share/osm-devops -t latest "$@"
```

## Install OSM from sources based on Git tag: v5.0.5
```
./install_osm.sh -b tags/v5.0.5 2>&1 | tee osm_install_log.txt
```

## Update OSM instance to use modified NBI, RO and Configuration images from docker5gmedia
**Note:** RO already contains required opennebula patches

```
sudo vi /etc/osm/docker/docker-compose.yaml
```
* Replace image tags.
  Update them from `latest` --> `v5.0.5` for the following services: `lcm`, `mon`, `pol`, `light-ui`

* Update image for keystone
  ```
  keystone:
    image: docker5gmedia/keystone:v5.0.5
  ```
* Update image for nbi
  ```
  nbi:
    image: docker5gmedia/nbi:v5.0.5
  ```
* Update image and add environment variable for ro
  ```
  ro:
    image: docker5gmedia/ro:git_220e83e_faas_f819706
    environment:
      ...
      FAAS_CONF_CONNECT: http://faas-configuration:5001
  ```

* Update image for FaaS configuration

```
  faas-configuration:
    image: docker5gmedia/faas-configuration-service:f819706
    networks:
      - netOSM
    environment:
      OSM_RO_HOSTNAME: ro
    ports:
      - "5001:5001"
```

## Restart OSM
**Important: If you perform an update/upgrade then delete all running NS and VIM accounts. Ensure they are properly deleted**

```bash
sudo docker stack rm osm && sleep 60
sudo docker stack deploy -c /etc/osm/docker/docker-compose.yaml osm
```

## Wait for the components to run
```bash
sudo docker stack ps osm | grep -i running
```

## Single VM that contains Lean and OSM
**Important: Lean, Minikube and OSM use some common ports. Change the ports of OSM components to solve port conflicts. Run the below whenever you restart OSM**

 ```bash
lxc config set core.https_address '[::]:8445' 
docker service update --publish-rm published=80,target=80 osm_light-ui
docker service update --publish-add published=8082,target=80 osm_light-ui
```

**Note:** OSM UI will be opened at IP:8082
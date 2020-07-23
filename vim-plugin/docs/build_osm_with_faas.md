# Open Source Mano Build

This page contains build instructions for OSM v5.0.5 (verified with Ubuntu 16.04)

### **Do this only during development**

Log into the OSM host

## Install OSM from sources based on Git tag: v5.0.5

```bash
cd ~
wget https://osm-download.etsi.org/ftp/osm-5.0-five/install_osm.sh
chmod +x install_osm.sh
./install_osm.sh -b tags/v5.0.5 2>&1 | tee osm_install_log.txt
```

## Add FaaS code to OSM and push images to dockerhub

### Modify NBI:

* Clone NBI
  ```bash
  cd ~
  git clone https://osm.etsi.org/gerrit/osm/NBI
  cd NBI
  git checkout tags/v5.0.5
  ```

* Add faas to `vim_type`
  ```bash
  vi osm_nbi/validation.py
  ```
  ```python
  "vim_type": {"enum": ["openstack", "openvim", "vmware", "opennebula", "aws", "faas"]},
  ```
* **Build and push image**
  ```bash
  sg docker -c "docker build ~/NBI -f ~/NBI/Dockerfile.local -t docker5gmedia/nbi:v5.0.5 --no-cache"
  sg docker -c "docker build ~/NBI/keystone -f ~/NBI/keystone/Dockerfile -t docker5gmedia/keystone:v5.0.5 --no-cache"
  sudo docker login --username docker5gmedia
  sudo docker push docker5gmedia/nbi:v5.0.5
  sudo docker push docker5gmedia/keystone:v5.0.5
  ```

### Modify RO:

* Clone RO
  ```
  cd ~
  git clone https://osm.etsi.org/gerrit/osm/RO
  cd RO
  git checkout 220e83e
  ```

* Add `faas` to `vim_module` plus the `import` statement
  ```
  vi osm_ro/vim_thread.py
  ```
  ```python
  ...
  import vimconn_faas
  ...
  vim_module = {
      ...  
      "faas": vimconn_faas,
  }
  ```
* Modify under `vim_thread` class, refresh rate to 30 seconds
  ```
  vi osm_ro/vim_thread.py
  ```
  ```python
  ...
  REFRESH_ACTIVE = 30    # 30 seconds
  ```
* Copy `vimconn_faas.py` from this repository to `RO/osm_ro/`

* **Build and push image**
  ```bash
  sg docker -c "docker build ~/RO -f ~/RO/docker/Dockerfile-local -t docker5gmedia/ro:git_220e83e_faas_f819706 --no-cache"
  sudo docker login --username docker5gmedia
  sudo docker push docker5gmedia/ro:git_220e83e_faas_f819706
  ```

### Build FaaS Configuration Service

```bash
cd ~/faas-vim-plugin/vim-plugin/configuration_service
sudo docker build --tag "docker5gmedia/faas-configuration-service:f819706" --force-rm=true .
sudo docker login --username=docker5gmedia
sudo docker push docker5gmedia/faas-configuration-service:f819706
```
  
# Kafka-Consumer service for FaaS configuration

**Instructions will be replaced with a dockerized version**

## Installation
Log into OSM host

### Install specific libs
It is necessary to install some specific system libs before installing Kafka-consumer service.

```
sudo apt-get install -y python-dev
sudo apt-get install -y python-setuptools
sudo apt-get install -y python-pip
```

### Install python packages
```
sudo pip install --upgrade pip
sudo pip install virtualenv
```

### Create virtual environment and activate it
```
virtualenv .my-virtenv
source .my-virtenv/bin/activate
```

### Install project dependencies
```
sudo pip install --upgrade pip
pip install -r requirements.txt
```

### Launch the service
```
source .my-virtenv/bin/activate
python kafka_consumer.py
```

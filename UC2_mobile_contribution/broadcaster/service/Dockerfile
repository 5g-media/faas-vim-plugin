FROM ubuntu:xenial

RUN apt-get update && apt-get install -y bash \
    bzip2 \
    vim \
    curl \
    gcc \
    libc-dev \
    python-pip

RUN pip install --upgrade pip setuptools six
RUN pip install --no-cache-dir gevent==1.2.1 flask>=1.0.0 requests==2.13.0 kafka-python==1.4.2 pyopenssl

RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 -subj "/C=EU/ST=5gmedia 5gmedia/L=5gmedia /O=5gmedia/OU=5gmedia/CN=5gmedia/emailAddress=5gmedia" -keyout /server.key -out /server.crt

ADD broadcaster_service.py /

CMD ["/bin/bash", "-c", "python -u broadcaster_service.py"]
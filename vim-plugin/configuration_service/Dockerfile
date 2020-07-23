FROM ubuntu:xenial

RUN apt-get update && apt-get install -y bash \
    bzip2 \
    vim \
    curl \
    gcc \
    libc-dev \
    python-pip

RUN pip install --upgrade pip setuptools six
RUN pip install --no-cache-dir gevent==1.2.1 flask==0.12 requests==2.13.0

ADD faas_configuration_service.py /

CMD ["/bin/bash", "-c", "python -u faas_configuration_service.py"]

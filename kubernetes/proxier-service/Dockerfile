FROM docker5gmedia/ow-offload-serverprereqs:0.1

RUN pip install \
    kubernetes==10.0.1

RUN mkdir -p /proxyServer
ADD server.py /proxyServer/

CMD ["/bin/bash", "-c", "cd proxyServer && python -u server.py"]

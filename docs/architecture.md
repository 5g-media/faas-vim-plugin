# Architecture

## Apache OpenWhisk VIM Overview

![faas-vim-serverless-orchestration](https://media.github.ibm.com/user/19909/files/678edb80-ca88-11ea-99d1-dca2b626c809)

* Serverless VNFs are marked not to be started upon regular OSM instantiation.
* VNFR for serverless VNFs initially contains a fabricated metadata (e.g., 0.0.0.0:0 as ip:port).
* A service containing a serverless VNF always has a Bootstrap VNF that contains CRs for Gateway and Sensor for this service.
* Gateway is a webhook gateway that simply relays HTTP requests to Sensor.
* Sensor is where conditional Argo workflow triggering is defined.
* A specific flow will be triggered based on the payload in the HTTP request.
* The payload on the HTTP request contains different operations, such as instantiate, delete, configure, etc., as well as the parameters required to complete the operation.
* Sensor is being programmed by the network service developer and constitutes an event-driven orchestration plane per service instance.
* When a new service instance is instantiated, Boostrap sets Gateway and Sensor and VNFR of Bootstrap contains the metadata of Gateway (URL), so that it will be used as an entry point for serverless orchestration.
* This way event driven orchestration coexists semlessly with OSM.


## Serverless Orchestration Overview

![serverless-orchestration-flow](https://media.github.ibm.com/user/19909/files/a4a79d80-ca89-11ea-8cae-c9ed763cbea2)

* Step A: an administrator or an automation script requests service package instantiation from MANO.
* Step B: FaaS VIM is used to instantiate VNFDs in the package one by one.
* Step C: Each time a VNFD is being requested for instantiation, FaaS VIM offloads an OpenWhisk action to K8s.
* Step 1: First VNF is Bootsrap.
* Step 2: Bootstrap applies CRs for Gateway and Sensor to K8s API Server
* Step 3: Argo Sensor controller and Argo Gateway Controller (collectively referred to as Argo Events Controller) create Gateway and Sensor pods.
* At this point the serverless orchestrator is ready for operation
* OSM executes periodic poll tasks to obtain the metadata on all VNFs that the VIM started (so far, just the Bootsrap has been started) and store it in the VNFR for that VNF. Gatewy URL is stored as part of the metadata in Bootsrap's VNFR.
* An administrator or a script retrieves the URL of the Gatewy to obtain the entry point to serverless orchestrator.
* Request 1 to instantiate VNF1 and VNF2 is issued against this URL.
* Step 4: Gatewy relays the HTTP request to Sensor. Sensor triggers Workflow 4 to instantiate VNF1 and VNF2
* The polling task by OSM eventually fills in the correct metadata for these VNFs.
* Request 2 to start VNF 3 arrives. A similar workflow triggering happens. 
* Upon instantiation Day 0 configuration obtained from the request is used.
* Day 2 configuration is performed similarly, but the operation on a request would demand configuration (see examples).

## Further reading
* [Specification of the 5G-MEDIA Serverless Computing Framework](http://www.5gmedia.eu/cms/wp-content/uploads/2018/09/5G-MEDIA-D3.2-Specification-of-the-5G-MEDIA-Serverless-Computing-Framework_v1.0.pdf)
* [5G-MEDIA Operations and Configuration Platform -- Section 4](http://www.5gmedia.eu/cms/wp-content/uploads/2020/01/5G-MEDIA-D3.4-5G-MEDIA-Operations-and-Configuration-Platform_v1.0_final.pdf)

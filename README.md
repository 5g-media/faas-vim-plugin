# 5G-MEDIA FaaS VIM
An implementation of FaaS VIM plugin for [OSM release 5](https://osm.etsi.org/wikipub/index.php/OSM_Release_FIVE)

### Openwhisk
Follow instructions to install [Openwhisk, CLI](openwhisk/docs/openwhisk.md) and [wskdeploy](openwhisk/docs/wskdeploy.md)

### Kubernetes
Follow instructions to setup [Kubernetes cluster](kubernetes/docs/kubernetes.md), [workflow Argo](kubernetes/docs/argo.md) and [monitoring framework](kubernetes/docs/monitoring.md)

### OSM and VIM plug-in
Follow instructions to install [OSM and FaaS VIM plug-in](vim-plugin/README.md)

### SVP Components

Follow [SVP Installation](https://github.com/5g-media/service-virtualization-platform#installation) steps skipping the first one: `Install the 5G-MEDIA Services orchestration`; you have already installed it.

## Use-cases

Following are the use-case scenarios that involve FaaS:

* [UC1: Immersive Game Service](UC1_immersive_game)
* [UC2: Mobile Contribution Service](UC2_mobile_contribution)
* [UC3: UltraHDOverCDN Service](UC3_uhd_over_vcdn)


## Acknowledgments
This project has received funding from the European Union’s Horizon 2020 research and innovation programme under grant agreement [No 761699](http://www.5gmedia.eu/). The dissemination of results herein reflects only the author’s view and the European Commission is not responsible for any use that may be made of the information it contains.

## License
[Apache 2.0](LICENSE)
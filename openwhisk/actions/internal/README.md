# Internal Openwhisk actions

These internal openwhisk actions are being used by the FaaS VIM. They are specified in the
manifest file and are pre-deployed via single execution using the `wskdeploy` tool. Internal actions are used to back the VNF  lifecycle management events initiated by MANO on the NBI of the OpenWhisk plugin.  

Log into OW host

### Invoke wskdeploy

```bash
wskdeploy -m manifest.yaml
```

### Check action existence

```bash
wsk -i package list
wsk -i action list
```

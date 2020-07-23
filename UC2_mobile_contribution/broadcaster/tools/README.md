# Broadcaster Tools
This folder contains the following tools

* Mobile Journalist App emulator. Script that automates end to end flow of journalist that contributes content to broadcasting premises.

* Metadata Merge. Utility to be used by the broadcaster entity to merge the produced metadata files into single one.


## Merging Metadata

Login to a host with docker installed that has a connectivity to 5G MEDIA SVP

### Prerequisites

Install jq. On ubuntu run
```
sudo apt-get install jq
```

### Invocation

```
./merge_metadata.sh <contribution url>
```
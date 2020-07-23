#!/bin/bash

curl --insecure -X DELETE \
  https://127.0.0.1:5003/broadcaster-management/broadcasters


curl --insecure -X DELETE \
  https://127.0.0.1:5003/mc-pop-management/cognitive-pops


curl --insecure -X POST \
  https://127.0.0.1:5003/broadcaster-management/broadcasters/irt \
  -H 'content-type: application/json' \
  -d '{
    "name": "Institut fur Rundfunktechnik",
    "description": "Public TV of Bayren"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/broadcaster-management/broadcasters/irt/endpoints \
  -H 'content-type: application/json' \
  -d '{
    "name": "safe-remote",
    "url": "193.96.226.197",
    "gps": "48.1860 N, 11.6282 E",
    "description": "A safe remote environment offered to the mobile journalists of IRT"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/broadcaster-management/broadcasters/irt/endpoints \
  -H 'content-type: application/json' \
  -d '{
    "name": "live-remote",
    "url": "https://live-remote.irt.de",
    "gps": "48.1860 N, 11.6282 E",
    "description": "A live remote environment offered to the mobile journalists of IRT"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/broadcaster-management/broadcasters/rtve \
  -H 'content-type: application/json' \
  -d '{
    "name": "Corporacion de Radio y Television Espanola",
    "description": "Public TV of Spain"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/broadcaster-management/broadcasters/rtve/endpoints \
  -H 'content-type: application/json' \
  -d '{
    "name": "safe-remote",
    "url": "https://safe-remote.rtve.se",
    "gps": "48.1860 N, 11.6282 E",
    "description": "A safe remote environment offered to the mobile journalists of RTVE"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/broadcaster-management/broadcasters/rtve/endpoints \
  -H 'content-type: application/json' \
  -d '{
    "name": "live-remote",
    "url": "https://live-remote.rtve.se",
    "gps": "18.1860 N, 10.6282 E",
    "description": "A live remote environment offered to the mobile journalists of RTVE"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/mc-pop-management/cognitive-pops/ncsrd \
  -H 'content-type: application/json' \
  -d '{
    "name": "Demokritos",
    "url": "http://10.30.2.56:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502",
    "gps": "37.9992 N, 23.8194 E",
    "broadcasters": ["irt", "rtve"],
    "description": "A safe local environment at Demokritos 5G edge"
   }'

curl --insecure -X POST \
  https://127.0.0.1:5003/mc-pop-management/cognitive-pops/tid \
  -H 'content-type: application/json' \
  -d '{
    "name": "Telefonica",
    "url": "http://192.168.83.77:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502",
    "gps": "40.4168 N, 3.7038 W",
    "broadcasters": ["irt", "rtve"],
    "description": "A safe local environment at Telefonica 5G edge"
   }'

#curl --insecure -X POST \
#  https://127.0.0.1:5003/mc-pop-management/cognitive-pops/ote \
#  -H 'content-type: application/json' \
#  -d '{
#    "name": "Cosmote",
#    "url": "http://195.167.80.32:9001/api/23bc46b1-71f6-4ed5-8c54-816aa4f8c502",
#    "gps": "37.9754 N, 23.7239 W",
#    "broadcasters": ["irt", "rtve"],
#    "description": "A safe local environment at OTE Athens Centre 5G edge"
#   }'
#!/bin/bash

CNO=true

BR_EDGE=192.158.1.175
BR_ID=irt
GPS="40.4268 N, 3.2405 W"
FUNCTION=vspeech_vdetection
MODE=safe-remote
STREAM_TIME=90

BETWEEN=3


generate_post_edge_selection_cno()
{
  cat <<EOF
{
  "gps": "$GPS",
  "function": "$1",
  "mode": "$2"
}
EOF
}

generate_post_edge_selection()
{
  cat <<EOF
{
  "gps": "$GPS"
}
EOF
}



generate_post_instantiate_cno()
{
  cat <<EOF
{
  "session-uuid": "$1",
  "br-id": "$2",
  "function": "$3",
  "mode": "$4",
  "broadcaster-endpoint-ip": "$5"
}
EOF
}


generate_post_instantiate()
{
  cat <<EOF
{
  "br-id": "$1",
  "function": "$2",
  "mode": "$3",
  "broadcaster-endpoint-ip": "$4"
}
EOF
}


generate_post_initialize_cno()
{
  cat <<EOF
{
  "session-uuid": "$1",
  "br-id": "$2",
  "function": "$3",
  "mode": "$4",
  "broadcaster-endpoint-ip": "$5",
  "resource": $6
}
EOF
}


generate_post_initialize()
{
  cat <<EOF
{
  "session-uuid": "$1",
  "br-id": "$2",
  "function": "$3",
  "mode": "$4",
  "broadcaster-endpoint-ip": "$5"
}
EOF
}


generate_post_data2()
{
  cat <<EOF
{
  "br-edge-ip": "$1",
  "br-id": "$2",
  "session-uuid": "$3",
  "event-uuid": "$4"
}
EOF
}

clear

if [ $MODE = "safe-remote" ]; then
   broadcaster_entry="$(curl --insecure https://$BR_EDGE:5003/broadcaster-management/broadcasters/$BR_ID 2>/dev/null)"
   br_ip="$(echo $broadcaster_entry  | jq -r '.endpoints[] | select(.name=="safe-remote") | .url')"
   if [ ${DEBUG:-false} == "true" ]; then
     echo "[debug] br_ip: $br_ip"
   fi
fi


sleep $BETWEEN
echo "-=-=-=-=-=-= TRACE 1 -=-=-=-=-=-=-=-=-=-"
echo "Locate nearest edge.."
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"
sleep $BETWEEN

if [ ${CNO:-false} == "true" ]; then
  edge="$(curl --insecure -X POST https://$BR_EDGE:5003/broadcaster-management/broadcasters/$BR_ID/edge-selection --data "$(generate_post_edge_selection_cno $FUNCTION $MODE)" 2>/dev/null)"
  session_uuid="$(echo $edge | jq -r '.session_uuid')"
  i=0

  # -=-=-=-=-=-=-=-=-=-=--
  # Poll it
  #-=-=-=-=-=-=-=-=-=-=-=-=
  attempts=20
  edge="$(curl --insecure "https://$BR_EDGE:5003/broadcaster-management/broadcasters/$BR_ID/edge-selection/$session_uuid" 2>/dev/null)"
  until [ "$(echo $edge | jq -r '.status')" = "READY" -o $i -gt $attempts ]; do
    sleep 10
    i=$((i+1))
    # tput cup 50 0
    if [ ${DEBUG:-false} == "true" ]; then
      echo "[debug] ** Wait attempt $i"
    fi
    edge="$(curl --insecure "https://$BR_EDGE:5003/broadcaster-management/broadcasters/$BR_ID/edge-selection/$session_uuid" 2>/dev/null)"
  done
  if [ $i -gt $attempts ]; then
    echo "edge-selector TIMEOUT"
    exit 1
  fi

  edge_name="$(echo $edge | jq -r '.name')"
  edge_resource="$(echo $edge | jq -c -r '.resource')"
  edge_url="$(echo $edge | jq -r '.url')"
  if [ ${DEBUG:-false} == "true" ]; then
    echo "[debug] edge_resource: $edge_resource"
  fi
else
  edge="$(curl --insecure -X POST https://$BR_EDGE:5003/broadcaster-management/broadcasters/$BR_ID/edge-selection --data "$(generate_post_edge_selection)" 2>/dev/null)"
  edge_name="$(echo $edge | jq -r '.name')"
  edge_url="$(echo $edge | jq -r '.url')"
fi


echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 2 -=-=-=-=-=-=-=-=-=-"
echo "Selected Edge is: $edge_name"
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"

sleep $BETWEEN
echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 3 -=-=-=-=-=-=-=-=-=-"
echo "Contact edge to instantiate session.."
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"


# -=-=-=-=-=-=-=-=-=-=--
# Pass session-uuid in case of CNO
#-=-=-=-=-=-=-=-=-=-=-=-=
if [ ${CNO:-false} == "true" ]; then
  instantiate_result="$(curl --insecure -X POST $edge_url/session/instantiate -H 'Content-Type: application/json' -d "$(generate_post_instantiate_cno $session_uuid $BR_ID $FUNCTION $MODE ${br_ip:-na})" 2>/dev/null)"
else
  instantiate_result="$(curl --insecure -X POST $edge_url/session/instantiate -H 'Content-Type: application/json' -d "$(generate_post_instantiate $BR_ID $FUNCTION $MODE ${br_ip:-na})" 2>/dev/null)"
  session_uuid="$(echo $instantiate_result | jq -r '."session-uuid"')"
fi

echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 4 -=-=-=-=-=-=-=-=-=-"
echo "Session ID:"
echo $session_uuid
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"

sleep $BETWEEN
echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 5 -=-=-=-=-=-=-=-=-=-"
echo "Wait for session to become ready.."
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"


i=0
attempts=6
until [ "$(curl --insecure "$edge_url/session/instantiate_poll?session-uuid=$session_uuid" 2>/dev/null | jq -r '.status')" = "INGRESS_FOUND" -o $i -gt $attempts ]; do
   sleep 10
   i=$((i+1))
   # tput cup 50 0
   if [ ${DEBUG:-false} == "true" ]; then
     echo "[debug] ** Wait attempt $i"
   fi
done
if [ $i -gt $attempts ]; then
  echo "instantiate_poll TIMEOUT"
  exit 1
fi

# -=-=-=-=-=-=-=-=-=-=--
# Initialize the session
#-=-=-=-=-=-=-=-=-=-=-=-=

if [ ${CNO:-false} == "true" ]; then
  initialize_result="$(curl --insecure -X POST $edge_url/session/initialize -H 'Content-Type: application/json' -d "$(generate_post_initialize_cno $session_uuid $BR_ID $FUNCTION $MODE ${br_ip:-na} $edge_resource)" 2>/dev/null)"
else
  initialize_result="$(curl --insecure -X POST $edge_url/session/initialize -H 'Content-Type: application/json' -d "$(generate_post_initialize $session_uuid $BR_ID $FUNCTION $MODE ${br_ip:-na})" 2>/dev/null)"
fi
session_uuid="$(echo $initialize_result| jq -r '."session-uuid"')"
event_uuid="$(echo $initialize_result | jq -r '."event-uuid"')"


# -=-=-=-=-=-=-=-=-=-=--
# Poll it
#-=-=-=-=-=-=-=-=-=-=-=-=
i=0
attempts=6
until [ "$(curl --insecure "$edge_url/session/initialize_poll?br-id=$BR_ID&session-uuid=$session_uuid&event-uuid=$event_uuid" 2>/dev/null | jq -r '.phase')" = "Succeeded" -o $i -gt $attempts ]; do
   sleep 10
   i=$((i+1))
   # tput cup 50 0
   if [ ${DEBUG:-false} == "true" ]; then
     echo "[debug] ** Wait attempt $i"
   fi
done
if [ $i -gt $attempts ]; then
  echo "initialize_poll TIMEOUT"
  exit 1
fi

initialize_poll_result="$(curl --insecure "$edge_url/session/initialize_poll?br-id=$BR_ID&session-uuid=$session_uuid&event-uuid=$event_uuid" 2>/dev/null)"
ipaddress="$(echo $initialize_poll_result | jq -r '.ipaddress')"
port="$(echo $initialize_poll_result | jq -r '.port')"

echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 6 -=-=-=-=-=-=-=-=-=-"
echo "Stream content to edge:"
echo "($ipaddress:$port)"
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"


if [ ${GPU_SLOW_START:-false} == "true" ]; then
  sleep 60
fi

container_id="$(sudo docker run -d docker5gmedia/srtx -fflags +genpts -re -i https://www.dropbox.com/s/scdv2ibc1eb9zkw/time.mp4?raw=1 -c copy -y -f mpegts srt://$ipaddress:$port?pkt_size=1316 2>/dev/null)"

sleep $STREAM_TIME
echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 7 -=-=-=-=-=-=-=-=-=-"
echo "Stream is completed"
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"

cid="$(sudo docker rm -f $container_id 2>/dev/null)"

sleep $BETWEEN
echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 8 -=-=-=-=-=-=-=-=-=-"
echo "Finalize session .."
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"

# -=-=-=-=-=-=-=-=-=-=--
# Poll it
#-=-=-=-=-=-=-=-=-=-=-=-=
i=0
attempts=60
finalize_result="$(curl --insecure -X POST $edge_url/session/finalize -H 'Content-Type: application/json' -d "$(generate_post_data2 $BR_EDGE $BR_ID $session_uuid $event_uuid)" 2>/dev/null)"
until [ "$(echo $finalize_result | jq -r '.status')" = "OK" -o $i -gt $attempts ]; do
   sleep 10
   i=$((i+1))
   # tput cup 50 0
   if [ ${DEBUG:-false} == "true" ]; then
     echo "[debug] ** Wait attempt $i"
   fi
   finalize_result="$(curl --insecure -X POST $edge_url/session/finalize -H 'Content-Type: application/json' -d "$(generate_post_data2 $BR_EDGE $BR_ID $session_uuid $event_uuid)" 2>/dev/null)"
done
if [ $i -gt $attempts ]; then
  echo "finalize TIMEOUT"
  exit 1
fi

contribute_url="$(echo $finalize_result | jq -r '."cotribute-url"')"

echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 9 -=-=-=-=-=-=-=-=-=-"
echo "Contribution URL:"
echo $contribute_url
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"

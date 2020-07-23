#!/bin/bash

CONTRIBUTION_URL=$1

if [ ${DEBUG:-false} == "true" ]; then
  echo "[debug] contribution_url: $CONTRIBUTION_URL"
fi

echo ""
echo ""
echo "-=-=-=-=-=-= TRACE 1 -=-=-=-=-=-=-=-=-=-"
echo "Contact contribution URL.."
echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"
contribution="$(curl --insecure $CONTRIBUTION_URL 2>/dev/null)"
# echo $contribution
vspeech_url="$(echo $contribution | jq -r '.req_url_vspeech')"
vdetection_url="$(echo $contribution | jq -r '.req_url_vdetection')"
if [ ${DEBUG:-false} == "true" ]; then
  echo "[debug] ** $vspeech_url $vdetection_url"
fi

if [[ "$vspeech_url" != "null" && "$vdetection_url" != "null" ]]; then
  echo ""
  echo ""
  echo "-=-=-=-=-=-= TRACE 2 -=-=-=-=-=-=-=-=-=-"
  echo "Merging metadata.."
  echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"
  wget $vspeech_url 2>/dev/null
  wget $vdetection_url 2>/dev/null
  vspeech_file="${vspeech_url##*/}"
  vdetection_file="${vdetection_url##*/}"
  session_uuid="$(echo $vspeech_file | awk -F. '{print $1}')"
  if [ ${DEBUG:-false} == "true" ]; then
    echo "[debug] session_uuid: $session_uuid"
  fi

  if [ ${DEBUG:-false} == "true" ]; then
    echo "[debug] ** vspeech file: ${vspeech_url##*/}"
    echo "[debug] ** vdetection file: ${vdetection_url##*/}"
  fi

  result="$(sudo docker run  --rm  -v $PWD:/mnt --entrypoint ffmpeg docker5gmedia/srtx -i /mnt/$vspeech_file /mnt/$session_uuid.speech.ass 2>/dev/null)"
  result="$(cp -f ./$vdetection_file ./$session_uuid.all.ass 2>/dev/null)"
  grep -A$(cat ./$session_uuid.speech.ass | wc -l) '\[Events\]' ./$session_uuid.speech.ass | grep -v '\[Events\]' >> ./$session_uuid.all.ass

  if [ ${DEBUG:-false} == "true" ]; then
    echo "[debug] remove temporary files"
  fi

  rm -f $vspeech_file
  rm -f $vdetection_file
  rm -f $session_uuid.speech.ass

  echo ""
  echo ""
  echo "-=-=-=-=-=-= TRACE 3 -=-=-=-=-=-=-=-=-=-"
  echo "Produced merge file: $session_uuid.all.ass"
  echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"
else
  echo ""
  echo ""
  echo "-=-=-=-=-=-= TRACE 3 -=-=-=-=-=-=-=-=-=-"
  echo "Nothing to merge"
  echo "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-"

fi

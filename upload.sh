source upload.sh.user
JQ=jq

MEDIA_WASM="11467372-23fb-4d45-818b-fc78edf889a6"
MEDIA_RICK="ef083197-9811-4332-9d87-50982eea5ccc"
MEDIA_PLAY="f6c9cfc5-7244-4e94-a264-3e0fe7e932fb"

curl_api() {
  METHOD=$1
  shift
  API=$1
  shift
  if [ -z "$TOKEN" ]; then
    #curl -s -X $METHOD https://www.zpqrtbnk.net/umbraco/management/api/v1/$API $*
    echo "oops"
  else
    curl -s -H "Authorization: Bearer $TOKEN" -X $METHOD https://www.zpqrtbnk.net/umbraco/management/api/v1/$API "$@"
  fi
}

TOKEN=$(curl -s https://www.zpqrtbnk.net/umbraco/management/api/v1/security/back-office/token -d "client_id=$CLIENT_ID" -d "client_secret=$CLIENT_SECRET" -d 'grant_type=client_credentials' | ./jq -r .access_token)
# echo "TOKEN=$TOKEN"

USER=$(curl_api GET user/current | ./jq -r .name)
echo "USER=$USER"

upload() {
  MEDIA_ID=$1
  FILE=$2
  echo
  echo "GET MEDIA ID=$MEDIA_ID"
  MEDIA=$(curl_api GET media/$MEDIA_ID)
  echo "RC=$?"
  echo "MEDIA=$MEDIA"
  MEDIA_NAME=$(echo "$MEDIA" | $JQ -r .variants[0].name)
  echo "NAME=$MEDIA_NAME"
  echo
  echo "POST TEMPORARY FILE $FILE"
  UUID=$(pwsh -Command 'write-output "GUID=$([guid]::NewGuid().toString())"' | grep GUID | cut -c6-)
  echo "UUID=$UUID"
  curl_api POST temporary-file -F "Id=$UUID" -F "File=@./$FILE"
  echo "RC=$?"
  echo
  echo "CLEAR MEDIA"
  curl_api PUT media/$MEDIA_ID -H "Content-Type: application/json" -d "{\"id\":\"$MEDIA_ID\",\"values\":[{\"alias\":\"umbracoFile\",\"culture\":null,\"segment\":null,\"value\":{}}],\"variants\":[{\"culture\":null,\"segment\":null,\"name\":\"$MEDIA_NAME\"}]}"
  echo "PUT MEDIA"
  curl_api PUT media/$MEDIA_ID -H "Content-Type: application/json" -d "{\"id\":\"$MEDIA_ID\",\"values\":[{\"alias\":\"umbracoFile\",\"culture\":null,\"segment\":null,\"value\":{\"src\":\"\",\"temporaryFileId\":\"$UUID\"}}],\"variants\":[{\"culture\":null,\"segment\":null,\"name\":\"$MEDIA_NAME\"}]}"
  echo "RC=$?"
}

upload $MEDIA_RICK xrick/build/web/xrick.js
upload $MEDIA_PLAY xrick/build/web/player.js
upload $MEDIA_WASM xrick/build/web/xrick.wasm

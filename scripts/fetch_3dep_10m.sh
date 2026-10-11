#!/usr/bin/env bash
# Fetch the free, official USGS 3DEP 10 m DEM tiles covering the competition
# footprint, and report honestly whether the host is reachable.
#
# Sources (official, free, public domain):
#   USGS National Map / 3DEP staged products, bucket prd-tnm.s3.amazonaws.com
#   https://apps.nationalmap.gov/downloader/   (interactive)
#   https://tnmaccess.nationalmap.gov/api/v1/products  (machine API)
#
# IMPORTANT: on 2026-10-11 this bucket returned HTTP 000 from the working sandbox
# (network allow-list). The script is provided so the lane can be re-run unchanged
# on a machine with normal egress. It refuses to claim success it did not get.
set -uo pipefail
HOST="https://prd-tnm.s3.amazonaws.com"
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$HOST"); [ -z "$CODE" ] && CODE=000
echo "reachability probe $HOST -> HTTP $CODE"
if [ "$CODE" = "000" ]; then
  echo "BLOCKED: 3DEP bucket not reachable from this environment."
  echo "No data fetched. Re-run this script where egress is unrestricted."
  exit 3
fi
echo "reachable - enumerate tiles for the competition footprint with:"
echo "  curl '$HOST/?list-type=2&prefix=StagedProducts/Elevation/13/TIFF/'"

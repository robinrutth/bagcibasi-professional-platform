#!/bin/bash
set -e
echo "Türkiye OSM verisi indiriliyor..."
curl -L -o osrm-data/turkey-latest.osm.pbf \
  https://download.geofabrik.de/europe/turkey-latest.osm.pbf

echo "OSRM graph işleniyor (extract)..."
docker run -t -v "$(pwd)/osrm-data:/data" \
  osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/turkey-latest.osm.pbf

echo "OSRM graph işleniyor (partition)..."
docker run -t -v "$(pwd)/osrm-data:/data" \
  osrm/osrm-backend osrm-partition /data/turkey-latest.osrm

echo "OSRM graph işleniyor (customize)..."
docker run -t -v "$(pwd)/osrm-data:/data" \
  osrm/osrm-backend osrm-customize /data/turkey-latest.osrm

echo "✅ OSRM hazır! docker-compose --profile routing up -d ile başlatın."

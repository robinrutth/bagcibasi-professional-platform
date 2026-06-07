Write-Host "Türkiye OSM verisi indiriliyor..."
Invoke-WebRequest -Uri "https://download.geofabrik.de/europe/turkey-latest.osm.pbf" `
  -OutFile "osrm-data\turkey-latest.osm.pbf"

Write-Host "OSRM graph işleniyor (extract)..."
docker run -t -v "${PWD}\osrm-data:/data" `
  osrm/osrm-backend `
  osrm-extract -p /opt/car.lua /data/turkey-latest.osm.pbf

Write-Host "OSRM graph işleniyor (partition)..."
docker run -t -v "${PWD}\osrm-data:/data" `
  osrm/osrm-backend osrm-partition /data/turkey-latest.osrm

Write-Host "OSRM graph işleniyor (customize)..."
docker run -t -v "${PWD}\osrm-data:/data" `
  osrm/osrm-backend osrm-customize /data/turkey-latest.osrm

Write-Host "✅ OSRM hazır!"

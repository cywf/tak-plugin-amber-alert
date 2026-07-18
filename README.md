# TAK AMBER Alert Plugin

**Real-time AMBER Alert monitoring and mapping for TAK-Server.**

Integrates with FEMA IPAWS and state-level alert systems to provide situational awareness of active child abductions.

---

## Features

- ✅ **FEMA IPAWS Integration** - Federal alert system monitoring
- ✅ **State-Level APIs** - California, Texas, Florida feeds
- ✅ **Geofence Filtering** - Only show alerts within your AO
- ✅ **CoT Alert Generation** - Real-time TAK map markers
- ✅ **Persistent Tracking** - Avoids duplicate alerts
- ✅ **mTLS Security** - Certificate-based TAK-Server auth
- ✅ **Docker Deployment** - Standalone containerized service

---

## Quick Start

```bash
git clone https://github.com/cywf/tak-plugin-amber-alert
cd tak-plugin-amber-alert
./setup.sh
docker-compose build
docker-compose up -d
```

---

## Configuration

Edit `.env` after running `./setup.sh`:

### Alert Sources
```bash
AMBER_ENABLE_IPAWS=true        # Federal IPAWS system
AMBER_ENABLE_STATES=true       # State-level feeds
AMBER_STATES=CA,TX,FL          # Which states to monitor
```

### Geofence Filtering
```bash
AMBER_GEOFENCE_FILTER=true           # Enable radius filtering
AMBER_GEOFENCE_RADIUS_MILES=100      # Radius around center point
AMBER_ALERT_LAT=37.7749              # Center latitude
AMBER_ALERT_LON=-122.4194            # Center longitude
```

### Update Intervals
```bash
AMBER_CHECK_INTERVAL=300  # Check every 5 minutes
```

---

## Use Cases

### Executive Protection
- Real-time awareness of abductions in client's area
- Route planning to avoid incident zones
- Enhanced security posture during active threats

### SAR Operations
- Coordinate search efforts with law enforcement
- Optimize resource deployment
- Timeline reconstruction

### Private Security
- Client briefings on local threats
- Enhanced situational awareness
- Emergency response coordination

---

## How It Works

1. **Poll Alert Sources** - Every 5 minutes, fetch alerts from FEMA IPAWS and configured state feeds
2. **Geofence Filter** - Calculate distance from alert location to configured center point
3. **Deduplication** - Check against seen alerts database to avoid duplicates
4. **CoT Generation** - Create TAK-compatible alert marker with suspect vehicle, location, child details
5. **TAK Distribution** - Send via mTLS to TAK-Server, appears on all connected clients

---

## Alert Details

Each AMBER Alert CoT message includes:
- **Title** - "AMBER ALERT"
- **Child Information** - Name, age, description
- **Suspect Information** - Name, vehicle, license plate
- **Location** - Last known location (if available)
- **Issue Time** - When alert was issued
- **Expiration** - 24-hour stale time

---

## Troubleshooting

### No Alerts Appearing

**Check logs:**
```bash
docker-compose logs -f
```

**Verify sources:**
- IPAWS feed may be empty (no active alerts)
- State feeds may require VPN or be rate-limited
- Increase geofence radius if filtering is too aggressive

### Certificate Errors

**Regenerate certs** from TAK-Server:
```bash
cd /opt/tak/certs
./makeCert.sh client amber-alert-plugin
```

---

## Development

**Local testing:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp -r ../tak-plugin-gateway/src/takgateway src/
export $(cat .env | xargs)
python src/amber_alert.py
```

---

## Security Notes

- **Never commit** `.env` or certificates to Git
- **Rotate certificates** regularly per your org policy
- **Limit API access** - State feeds may have rate limits or require authentication
- **PII handling** - AMBER Alert data contains sensitive child/suspect information

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) file.

---

## Related Projects

- [tak-plugin-gateway](https://github.com/cywf/tak-plugin-gateway) - Shared TAK library
- [tak-plugin-sat-alerts](https://github.com/cywf/tak-plugin-sat-alerts) - Satellite pass alerts
- [tak-plugin-crime-heatmap](https://github.com/cywf/tak-plugin-crime-heatmap) - Crime data overlays

---

**Built for operational security professionals.**  
Executive protection · Private security · SAR · Law enforcement coordination

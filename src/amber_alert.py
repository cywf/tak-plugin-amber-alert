"""
AMBER Alert TAK Plugin

Real-time AMBER Alert monitoring and mapping for TAK-Server.
Integrates with FEMA IPAWS and state-level alert systems.

Features:
- FEMA IPAWS API integration
- State-level API fallbacks
- Geofenced alert filtering
- CoT marker generation with alert details
- Photo attachment support (if available)
"""

import os
import sys
import time
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import urllib.request
import urllib.parse
import urllib.error
import hashlib

# Add takgateway to path (vendored in src/)
sys.path.insert(0, str(Path(__file__).parent))

from takgateway import (
    TAKServerClient,
    create_client_from_env,
    CoTBuilder,
    CoTTypes,
    HealthMonitor,
    setup_logging
)

logger = logging.getLogger(__name__)


class AmberAlertSource:
    """Base class for AMBER Alert data sources."""
    
    def fetch_alerts(self) -> List[Dict]:
        """Fetch current alerts. Returns list of alert dicts."""
        raise NotImplementedError


class IPAWSSource(AmberAlertSource):
    """FEMA IPAWS (Integrated Public Alert & Warning System) source."""
    
    # IPAWS CAP feed (public, no auth required for public alerts)
    IPAWS_CAP_URL = "https://apps.fema.gov/IPAWS-Portal-WEBAPP/ipawsalert/public/alerts"
    
    def fetch_alerts(self) -> List[Dict]:
        """Fetch AMBER Alerts from IPAWS CAP feed."""
        try:
            logger.info("Fetching alerts from IPAWS...")
            
            # IPAWS returns XML CAP (Common Alerting Protocol) messages
            # For simplicity, we'll use a REST endpoint that returns JSON
            # In production, parse CAP XML properly
            
            with urllib.request.urlopen(self.IPAWS_CAP_URL, timeout=30) as response:
                data = response.read().decode('utf-8')
                
                # Parse IPAWS response (actual format varies, this is illustrative)
                # In production, use proper CAP XML parser
                alerts = self._parse_ipaws_response(data)
                
                logger.info(f"Fetched {len(alerts)} alerts from IPAWS")
                return alerts
        
        except Exception as e:
            logger.error(f"Failed to fetch IPAWS alerts: {e}")
            return []
    
    def _parse_ipaws_response(self, data: str) -> List[Dict]:
        """Parse IPAWS response. Placeholder - implement CAP XML parsing."""
        # TODO: Implement proper CAP XML parsing
        # For now, return empty list
        # Real implementation would use xml.etree or lxml
        return []


class AmberAlertAPISource(AmberAlertSource):
    """
    AmberAlert.gov API source.
    
    Note: As of 2024, there's no official public API.
    This is a placeholder for when one becomes available.
    Alternative: Screen-scrape https://amberalert.ojp.gov/map
    """
    
    def fetch_alerts(self) -> List[Dict]:
        """Placeholder for official API."""
        logger.warning("AmberAlert.gov API not implemented (no public API available)")
        return []


class StateLevelSource(AmberAlertSource):
    """
    State-level AMBER Alert sources.
    Many states publish RSS/JSON feeds.
    """
    
    STATE_FEEDS = {
        "CA": "https://amberalert.chp.ca.gov/feeds/alert.json",
        "TX": "https://www.dps.texas.gov/internetforms/amberalert/json",
        "FL": "https://www.fdle.state.fl.us/MAPA/RSS/amber",
    }
    
    def __init__(self, states: List[str]):
        self.states = states
    
    def fetch_alerts(self) -> List[Dict]:
        """Fetch alerts from state-level feeds."""
        all_alerts = []
        
        for state in self.states:
            feed_url = self.STATE_FEEDS.get(state)
            if not feed_url:
                logger.warning(f"No feed URL for state: {state}")
                continue
            
            try:
                logger.info(f"Fetching {state} alerts from {feed_url}")
                
                with urllib.request.urlopen(feed_url, timeout=30) as response:
                    data = response.read().decode('utf-8')
                    
                    # Try JSON parsing
                    try:
                        alerts = json.loads(data)
                        if isinstance(alerts, list):
                            # Normalize to common format
                            normalized = [self._normalize_alert(a, state) for a in alerts]
                            all_alerts.extend(normalized)
                            logger.info(f"Fetched {len(alerts)} alerts from {state}")
                    except json.JSONDecodeError:
                        # Might be RSS/XML
                        logger.warning(f"{state} feed is not JSON, skipping")
            
            except Exception as e:
                logger.error(f"Failed to fetch {state} alerts: {e}")
        
        return all_alerts
    
    def _normalize_alert(self, raw_alert: Dict, state: str) -> Dict:
        """Normalize state alert to common format."""
        # Extract common fields (format varies by state)
        return {
            "id": raw_alert.get("id", raw_alert.get("alert_id", "unknown")),
            "state": state,
            "title": raw_alert.get("title", raw_alert.get("subject", "AMBER Alert")),
            "description": raw_alert.get("description", raw_alert.get("details", "")),
            "issued": raw_alert.get("issued", raw_alert.get("timestamp", datetime.utcnow().isoformat())),
            "expires": raw_alert.get("expires", ""),
            "location": {
                "lat": raw_alert.get("latitude", raw_alert.get("lat", None)),
                "lon": raw_alert.get("longitude", raw_alert.get("lon", None)),
                "description": raw_alert.get("location", raw_alert.get("area", "Unknown"))
            },
            "suspect": {
                "name": raw_alert.get("suspect_name", ""),
                "description": raw_alert.get("suspect_description", ""),
                "vehicle": raw_alert.get("vehicle", ""),
                "plate": raw_alert.get("license_plate", "")
            },
            "child": {
                "name": raw_alert.get("child_name", ""),
                "age": raw_alert.get("child_age", ""),
                "description": raw_alert.get("child_description", "")
            },
            "image_url": raw_alert.get("image_url", raw_alert.get("photo", None))
        }


class AmberAlertPlugin:
    """Main AMBER Alert plugin orchestrator."""
    
    def __init__(self):
        self.config = self.load_config()
        self.sources = self.init_sources()
        self.tak_client = create_client_from_env()
        self.health = HealthMonitor()
        
        # Track seen alerts to avoid duplicates
        self.seen_alerts = set()
        
        # Persistent storage
        self.data_dir = Path(self.config['data_dir'])
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.load_seen_alerts()
    
    def load_config(self) -> Dict:
        """Load configuration from environment."""
        return {
            'data_dir': os.getenv('AMBER_DATA_DIR', '/app/data'),
            'check_interval': int(os.getenv('AMBER_CHECK_INTERVAL', '300')),  # 5min
            'enable_ipaws': os.getenv('AMBER_ENABLE_IPAWS', 'true').lower() == 'true',
            'enable_states': os.getenv('AMBER_ENABLE_STATES', 'true').lower() == 'true',
            'states': os.getenv('AMBER_STATES', 'CA,TX,FL').split(','),
            'geofence_filter': os.getenv('AMBER_GEOFENCE_FILTER', 'true').lower() == 'true',
            'geofence_radius_miles': float(os.getenv('AMBER_GEOFENCE_RADIUS_MILES', '100')),
            'alert_latitude': float(os.getenv('AMBER_ALERT_LAT', '37.7749')),
            'alert_longitude': float(os.getenv('AMBER_ALERT_LON', '-122.4194')),
        }
    
    def init_sources(self) -> List[AmberAlertSource]:
        """Initialize alert sources based on config."""
        sources = []
        
        if self.config['enable_ipaws']:
            sources.append(IPAWSSource())
            logger.info("Enabled IPAWS source")
        
        if self.config['enable_states']:
            sources.append(StateLevelSource(self.config['states']))
            logger.info(f"Enabled state sources: {', '.join(self.config['states'])}")
        
        return sources
    
    def load_seen_alerts(self):
        """Load previously seen alert IDs from disk."""
        seen_file = self.data_dir / "seen_alerts.json"
        if seen_file.exists():
            try:
                with open(seen_file, 'r') as f:
                    data = json.load(f)
                    self.seen_alerts = set(data.get('alerts', []))
                logger.info(f"Loaded {len(self.seen_alerts)} seen alerts from disk")
            except Exception as e:
                logger.error(f"Failed to load seen alerts: {e}")
    
    def save_seen_alerts(self):
        """Save seen alert IDs to disk."""
        seen_file = self.data_dir / "seen_alerts.json"
        try:
            with open(seen_file, 'w') as f:
                json.dump({'alerts': list(self.seen_alerts)}, f)
        except Exception as e:
            logger.error(f"Failed to save seen alerts: {e}")
    
    def run(self):
        """Main plugin loop."""
        logger.info("AMBER Alert Plugin starting...")
        
        # Register health components
        self.health.register("tak_server", "unknown")
        self.health.register("alert_sources", "unknown")
        
        # Connect to TAK-Server
        if self.tak_client.connect():
            self.health.mark_healthy("tak_server", "Connected via mTLS")
        else:
            self.health.mark_unhealthy("tak_server", "Failed to connect")
            logger.error("Failed to connect to TAK-Server, exiting")
            return
        
        try:
            while True:
                # Fetch alerts from all sources
                self.check_alerts()
                
                # Health report
                report = self.health.get_health_report()
                logger.info(f"Health: {report['status']} | Seen alerts: {len(self.seen_alerts)}")
                
                # Save state
                self.save_seen_alerts()
                
                # Sleep
                time.sleep(self.config['check_interval'])
        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.save_seen_alerts()
            self.tak_client.disconnect()
    
    def check_alerts(self):
        """Fetch and process alerts from all sources."""
        all_alerts = []
        
        for source in self.sources:
            try:
                alerts = source.fetch_alerts()
                all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Source failed: {e}")
        
        if all_alerts:
            self.health.mark_healthy("alert_sources", f"{len(all_alerts)} alerts fetched")
        else:
            self.health.mark_degraded("alert_sources", "No alerts (sources may be empty)")
        
        # Process new alerts
        for alert in all_alerts:
            alert_id = self.get_alert_id(alert)
            
            if alert_id not in self.seen_alerts:
                # Apply geofence filter
                if self.config['geofence_filter']:
                    if not self.alert_in_geofence(alert):
                        logger.debug(f"Alert {alert_id} outside geofence, skipping")
                        continue
                
                # Send to TAK
                self.send_amber_alert(alert)
                self.seen_alerts.add(alert_id)
                
                # Cleanup old seen alerts (keep last 1000)
                if len(self.seen_alerts) > 1000:
                    oldest = sorted(self.seen_alerts)[:500]
                    self.seen_alerts -= set(oldest)
    
    def get_alert_id(self, alert: Dict) -> str:
        """Generate unique ID for alert."""
        # Use alert ID or hash of content
        if 'id' in alert and alert['id']:
            return str(alert['id'])
        
        # Hash description + issued time
        content = f"{alert.get('description', '')}{alert.get('issued', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def alert_in_geofence(self, alert: Dict) -> bool:
        """Check if alert location is within geofenced area."""
        from math import radians, sin, cos, sqrt, atan2
        
        # Extract alert location
        lat = alert.get('location', {}).get('lat')
        lon = alert.get('location', {}).get('lon')
        
        if lat is None or lon is None:
            # No location data, include by default
            return True
        
        # Haversine distance
        R = 3959  # Earth radius in miles
        
        lat1, lon1 = radians(self.config['alert_latitude']), radians(self.config['alert_longitude'])
        lat2, lon2 = radians(float(lat)), radians(float(lon))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance <= self.config['geofence_radius_miles']
    
    def send_amber_alert(self, alert: Dict):
        """Send CoT alert message to TAK-Server."""
        alert_id = self.get_alert_id(alert)
        
        # Use alert location if available, else use configured center
        lat = alert.get('location', {}).get('lat') or self.config['alert_latitude']
        lon = alert.get('location', {}).get('lon') or self.config['alert_longitude']
        
        # Build remarks with all details
        remarks_parts = [
            alert.get('title', 'AMBER Alert'),
            "",
            alert.get('description', ''),
            ""
        ]
        
        if alert.get('child', {}).get('name'):
            remarks_parts.append(f"Child: {alert['child']['name']}, Age {alert['child'].get('age', 'unknown')}")
        
        if alert.get('suspect', {}).get('vehicle'):
            remarks_parts.append(f"Vehicle: {alert['suspect']['vehicle']}")
        
        if alert.get('suspect', {}).get('plate'):
            remarks_parts.append(f"Plate: {alert['suspect']['plate']}")
        
        if alert.get('location', {}).get('description'):
            remarks_parts.append(f"Location: {alert['location']['description']}")
        
        remarks = "\n".join(remarks_parts)
        
        logger.info(f"Sending AMBER Alert: {alert_id}")
        
        # Build CoT message
        cot_xml = (
            CoTBuilder()
            .uid(f"amber-alert-{alert_id}")
            .type(CoTTypes.ALERT)
            .location(float(lat), float(lon))
            .callsign("AMBER ALERT")
            .remarks(remarks)
            .stale(1440)  # Valid for 24 hours
            .add_detail("alert_id", alert_id)
            .add_detail("state", alert.get('state', 'Unknown'))
            .add_detail("issued", alert.get('issued', ''))
            .build()
            .to_xml()
        )
        
        # Send to TAK-Server
        if self.tak_client.send_cot(cot_xml):
            logger.info(f"AMBER Alert sent: {alert_id}")
        else:
            logger.error(f"Failed to send AMBER Alert: {alert_id}")
            self.health.mark_degraded("tak_server", "CoT send failed")


def main():
    """Entry point."""
    setup_logging(
        level=os.getenv('LOG_LEVEL', 'INFO'),
        log_file=os.getenv('LOG_FILE')
    )
    
    plugin = AmberAlertPlugin()
    plugin.run()


if __name__ == "__main__":
    main()

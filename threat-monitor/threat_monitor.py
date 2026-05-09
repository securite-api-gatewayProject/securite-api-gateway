#!/usr/bin/env python3
"""
Threat Monitor: Automatic IP blocking based on Suricata alerts
Parses eve.json and adds malicious IPs to Kong ip-restriction plugin
"""

import json
import time
import requests
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

# Configuration
EVE_LOG_PATH = "/var/log/suricata/eve.json"
KONG_ADMIN_URL = os.getenv("KONG_ADMIN_URL", "http://kong:8001")
BLOCKED_IPS_FILE = "/tmp/blocked_ips.json"
ALERT_THRESHOLD = 5  # Number of alerts before blocking an IP
TIME_WINDOW = 300  # Time window in seconds (5 minutes)

class ThreatMonitor:
    def __init__(self):
        self.blocked_ips = self.load_blocked_ips()
        self.ip_alerts = defaultdict(list)
        self.file_position = 0
        
    def load_blocked_ips(self):
        """Load previously blocked IPs"""
        if os.path.exists(BLOCKED_IPS_FILE):
            try:
                with open(BLOCKED_IPS_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading blocked IPs: {e}")
        return {}
    
    def save_blocked_ips(self):
        """Save blocked IPs to file"""
        try:
            with open(BLOCKED_IPS_FILE, 'w') as f:
                json.dump(self.blocked_ips, f, indent=2)
        except Exception as e:
            print(f"Error saving blocked IPs: {e}")
    
    def parse_eve_log(self):
        """Parse eve.json file and extract new alerts"""
        try:
            if not os.path.exists(EVE_LOG_PATH):
                print(f"Waiting for {EVE_LOG_PATH}...")
                return
            
            with open(EVE_LOG_PATH, 'r') as f:
                f.seek(self.file_position)
                
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        self.process_event(event)
                    except json.JSONDecodeError:
                        continue
                
                self.file_position = f.tell()
        except Exception as e:
            print(f"Error parsing eve.json: {e}")
    
    def process_event(self, event):
        """Process a single event from eve.json"""
        # Only process alert events
        if event.get("event_type") != "alert":
            return
        
        # Extract source IP
        src_ip = event.get("src_ip")
        if not src_ip:
            return
        
        # Extract alert message
        alert_msg = event.get("alert", {}).get("signature", "Unknown")
        timestamp = event.get("timestamp")
        
        # Record alert for this IP
        self.ip_alerts[src_ip].append({
            "timestamp": timestamp,
            "message": alert_msg
        })
        
        # Clean old alerts outside time window
        self.clean_old_alerts(src_ip)
        
        # Check if IP should be blocked
        if len(self.ip_alerts[src_ip]) >= ALERT_THRESHOLD:
            self.block_ip(src_ip, alert_msg)
    
    def clean_old_alerts(self, ip):
        """Remove alerts older than TIME_WINDOW"""
        now = datetime.utcnow()
        valid_alerts = []
        
        for alert in self.ip_alerts[ip]:
            try:
                timestamp_str = alert.get("timestamp", "")
                # Parse ISO format timestamp
                alert_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if (now - alert_time).total_seconds() < TIME_WINDOW:
                    valid_alerts.append(alert)
            except:
                pass
        
        self.ip_alerts[ip] = valid_alerts
    
    def block_ip(self, ip, reason="Suspicious activity detected"):
        """Add IP to Kong ip-restriction plugin"""
        # Check if already blocked
        if ip in self.blocked_ips:
            return
        
        try:
            # Get all Kong services
            services_resp = requests.get(f"{KONG_ADMIN_URL}/services")
            services = services_resp.json().get("data", [])
            
            for service in services:
                service_name = service.get("name")
                service_id = service.get("id")
                
                # Get or create ip-restriction plugin for this service
                self.apply_ip_restriction(service_id, service_name, ip)
            
            # Record as blocked
            self.blocked_ips[ip] = {
                "blocked_at": datetime.utcnow().isoformat(),
                "reason": reason
            }
            self.save_blocked_ips()
            
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BLOCKED: {ip} - {reason}")
            
        except Exception as e:
            print(f"Error blocking IP {ip}: {e}")
    
    def apply_ip_restriction(self, service_id, service_name, ip):
        """Apply or update ip-restriction plugin on a service"""
        try:
            # Get existing ip-restriction plugin or create new one
            plugins_url = f"{KONG_ADMIN_URL}/services/{service_id}/plugins"
            plugins_resp = requests.get(plugins_url)
            plugins = plugins_resp.json().get("data", [])
            
            # Find or create ip-restriction plugin
            ip_restriction_plugin = None
            for plugin in plugins:
                if plugin.get("name") == "ip-restriction":
                    ip_restriction_plugin = plugin
                    break
            
            if ip_restriction_plugin:
                # Update existing plugin
                plugin_id = ip_restriction_plugin.get("id")
                current_deny = ip_restriction_plugin.get("config", {}).get("deny", [])
                
                if ip not in current_deny:
                    current_deny.append(ip)
                    update_url = f"{KONG_ADMIN_URL}/services/{service_id}/plugins/{plugin_id}"
                    requests.patch(update_url, json={"config": {"deny": current_deny}})
                    print(f"  Updated ip-restriction on {service_name}: added {ip}")
            else:
                # Create new plugin
                create_url = f"{KONG_ADMIN_URL}/services/{service_id}/plugins"
                requests.post(create_url, json={
                    "name": "ip-restriction",
                    "config": {
                        "deny": [ip]
                    }
                })
                print(f"  Created ip-restriction on {service_name}: blocking {ip}")
        
        except Exception as e:
            print(f"Error applying ip-restriction to {service_name}: {e}")
    
    def run(self):
        """Main loop"""
        print(f"Threat Monitor started")
        print(f"Monitoring: {EVE_LOG_PATH}")
        print(f"Kong Admin: {KONG_ADMIN_URL}")
        print(f"Alert threshold: {ALERT_THRESHOLD} alerts in {TIME_WINDOW}s")
        print(f"Blocked IPs file: {BLOCKED_IPS_FILE}")
        print("-" * 60)
        
        while True:
            try:
                self.parse_eve_log()
                time.sleep(2)  # Check every 2 seconds
            except KeyboardInterrupt:
                print("\nThreat Monitor stopped")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    monitor = ThreatMonitor()
    monitor.run()

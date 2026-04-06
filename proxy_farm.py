#!/usr/bin/env python3
"""
Proxy Farm Core Engine - The "Brain"
Orchestrates the T-Mobile NAT64 Exploit via ADB to a Rooted Android "Antenna"
"""

import os
import re
import time
import json
import logging
import sqlite3
import threading
import subprocess
import sys
import socket
import ssl
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

# Third-party imports
try:
    import socks
    import requests
except ImportError as e:
    print(f"CRITICAL ERROR: Missing dependency: {e}")
    print("Please run: pip install PySocks requests")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger('proxy_farm')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

os.makedirs('logs', exist_ok=True)
file_handler = logging.FileHandler('logs/proxy_farm.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# ─────────────────────────────────────────────────────────────
# DATA MODELS & ENUMS
# ─────────────────────────────────────────────────────────────
class KeepaliveStrategy(Enum):
    DRIFT = "drift"
    SESSION_HTTPS = "session_https"
    SSE_STREAM = "sse_stream"
    SIM_BROWSING = "sim_browsing"
    TCP_NULL_DRIP = "tcp_null_drip"
    UDP_DRIP = "udp_drip"
    OS_KEEPALIVE = "os_keepalive"
    ICMP_PING6 = "icmp_ping6"

@dataclass
class Node:
    node_id: int
    internal_port: int
    external_port: int
    ipv6_address: str
    pid: Optional[int] = None
    public_ipv4: Optional[str] = None
    is_alive: bool = False
    consecutive_failures: int = 0
    deployed_at: Optional[datetime] = None
    strategy: str = KeepaliveStrategy.DRIFT.value
    latency_ms: int = 0
    success_rate: float = 0.0
    pulse_count: int = 0
    bytes_sent: int = 0
    strategy_gen: int = 0

    def to_dict(self):
        d = self.__dict__.copy()
        if d['deployed_at']:
            d['deployed_at'] = d['deployed_at'].isoformat()
        return d

# ─────────────────────────────────────────────────────────────
# DATABASE MANAGER (Simplified for UI compatibility)
# ─────────────────────────────────────────────────────────────
class DatabaseManager:
    def __init__(self, db_path="database/proxy_farm.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        
    def _create_tables(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS ip_history (
            ip_address TEXT PRIMARY KEY,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            occurrences INTEGER
        )
        ''')
        self.conn.commit()

    def record_ip(self, ip_address):
        now = datetime.now().isoformat()
        self.cursor.execute("SELECT * FROM ip_history WHERE ip_address = ?", (ip_address,))
        if self.cursor.fetchone():
            self.cursor.execute("UPDATE ip_history SET last_seen = ?, occurrences = occurrences + 1 WHERE ip_address = ?", (now, ip_address))
        else:
            self.cursor.execute("INSERT INTO ip_history (ip_address, first_seen, last_seen, occurrences) VALUES (?, ?, ?, ?)", (ip_address, now, now, 1))
        self.conn.commit()

    def get_keepalive_results(self, limit=50): return []
    def close(self): self.conn.close()

# ─────────────────────────────────────────────────────────────
# ADB CONTROLLER (The Bridge to the Antenna)
# ─────────────────────────────────────────────────────────────
class ADBController:
    def __init__(self):
        self.device_id = None

    def run_shell(self, command: str, root: bool = False, timeout: int = 15) -> str:
        """Executes a shell command on the phone. Uses su -c if root is required."""
        if root:
            # We wrap the command in quotes for su -c
            cmd_safe = command.replace("'", "'\\''")
            full_cmd = ['adb', 'shell', 'su', '-c', f"'{cmd_safe}'"]
        else:
            full_cmd = ['adb', 'shell'] + command.split()
            
        try:
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0 and "kill" not in command:
                logger.debug(f"ADB Command returned non-zero: {command} -> {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"ADB command timed out: {command}")
            return ""
        except Exception as e:
            logger.error(f"ADB execution error: {e}")
            return ""

    def toggle_airplane_mode(self):
        """Forces the phone to drop its connection and acquire a new IPv6 /64 prefix."""
        logger.info("✈️ Toggling Airplane Mode to acquire new Carrier Prefix...")
        self.run_shell("cmd connectivity airplane-mode enable", root=True)
        time.sleep(4)
        self.run_shell("cmd connectivity airplane-mode disable", root=True)
        logger.info("Waiting 10 seconds for LTE/5G radio to stabilize...")
        time.sleep(10)

    def forward_port(self, local_port: int, remote_port: int):
        subprocess.run(['adb', 'forward', f'tcp:{local_port}', f'tcp:{remote_port}'], capture_output=True)

    def remove_all_forwards(self):
        subprocess.run(['adb', 'forward', '--remove-all'], capture_output=True)

    def get_device_temperature(self) -> float:
        out = self.run_shell('dumpsys battery | grep temperature')
        try:
            return int(out.split(':')[1].strip()) / 10.0
        except:
            return 0.0

# ─────────────────────────────────────────────────────────────
# NETWORK DISCOVERY (Unmasking the Secret Tables)
# ─────────────────────────────────────────────────────────────
class NetworkDiscovery:
    def discover(self, adb: ADBController) -> dict:
        logger.info("🔍 Discovering Cellular Network Topology (Smart Mode)...")
        
        # 1. Get ALL IPv6 addresses across all interfaces without root
        ip_out = adb.run_shell("ip -6 addr")
        
        best_iface = None
        best_prefix = None
        current_iface = None
        
        # 2. Parse the output to find the true active cellular interface
        for line in ip_out.split('\n'):
            # Match interface name, e.g., "15: rmnet_data2@rmnet_mhi0: <..."
            iface_match = re.match(r'^\d+:\s+([\w-]+)(?:@[\w-]+)?:', line)
            if iface_match:
                current_iface = iface_match.group(1)
                continue
                
            # Look for global IPv6 addresses on cellular interfaces
            if current_iface and (current_iface.startswith('rmnet') or current_iface.startswith('ccmni')):
                if 'inet6' in line and 'scope global' in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ip_full = parts[1].split('/')[0]
                        blocks = ip_full.split(':')
                        if len(blocks) >= 4:
                            prefix = ':'.join(blocks[:4])
                            if prefix != "fe80":
                                best_iface = current_iface
                                best_prefix = prefix
                                break # Found the active one!
        
        if not best_iface or not best_prefix:
            logger.error("CRITICAL: No cellular interface with a global IPv6 prefix found!")
            logger.error(f"--- FULL IPV6 DUMP START ---\n{ip_out}\n--- FULL IPV6 DUMP END ---")
            return {'cell_interface': 'rmnet_data0', 'table_id': '1015', 'nat64_prefix': 'UNKNOWN'}
            
        logger.info(f"Smart Discovery selected active interface: {best_iface}")
        
        # 3. Find the routing table ID tied to this specific interface
        # We MUST check IPv6 routes because the interface might be IPv6-only
        table_out = adb.run_shell(f"ip -6 route show table all", root=True)
        table_id = "1015" # Default
        current_table = "1015"
        for line in table_out.split('\n'):
            # Handle "table 1015:" format
            if line.startswith('table '):
                current_table = line.split()[1].replace(':', '')
            
            if 'default' in line and best_iface in line:
                # Handle inline "table 1015" format
                table_match = re.search(r'table\s+(\d+)', line)
                if table_match:
                    table_id = table_match.group(1)
                else:
                    table_id = current_table
                break

        # 4. Resolve api.ipify.org using the phone's DNS to get the DNS64 synthesized IPv6 address
        # This is critical because Termux's microsocks might use 8.8.8.8 and fail to resolve IPv6
        ping_out = adb.run_shell("ping6 -c 1 api.ipify.org")
        dns64_ip = None
        for line in ping_out.split('\n'):
            if 'PING' in line:
                # PING api.ipify.org(64:ff9b::...) 56 data bytes
                match = re.search(r'\((.*?)\)', line)
                if match:
                    dns64_ip = match.group(1)
                    break

        logger.info(f"✅ Topology Found -> Interface: {best_iface} | Table: {table_id} | Prefix: {best_prefix}::/64 | DNS64: {dns64_ip}")
        return {
            'cell_interface': best_iface,
            'table_id': table_id,
            'nat64_prefix': best_prefix,
            'dns64_ip': dns64_ip
        }

# ─────────────────────────────────────────────────────────────
# NODE MANAGER (The Exploit Injector)
# ─────────────────────────────────────────────────────────────
class NodeManager:
    def deploy_exploit(self, adb: ADBController, count: int, net_info: dict) -> List[Node]:
        logger.info(f"🚀 Injecting NAT64 Exploit Script for {count} nodes...")
        
        prefix = net_info.get('nat64_prefix', 'UNKNOWN')
        interface = net_info.get('cell_interface', 'rmnet_data0')
        table_id = net_info.get('table_id', '1015')
        
        # We write the bash script locally, push it to the phone, and execute it as root.
        # This avoids all quoting/escaping nightmares over ADB.
        script = f"""#!/system/bin/sh
# T-Mobile NAT64 Hardware Spoofing Exploit

# 0. Drop Kernel Shields
setenforce 0
echo 1 > /proc/sys/net/ipv4/ip_forward

# 1. Purge old routes
pkill -9 microsocks 2>/dev/null
iptables -t nat -F
ip rule flush pref 1 2>/dev/null
ip -6 rule flush pref 1 2>/dev/null

# 2. Deploy Fleet
for i in $(seq 1 {count}); do
    PORT=$((8000 + i))
    VIP4="192.168.100.$i"
    VIP6="{prefix}::100$i"

    # Internal IPv4 Routing
    ip addr add $VIP4/32 dev lo 2>/dev/null
    ip rule add from $VIP4/32 pref 1 table {table_id}

    # External IPv6 Hardware Spoofing
    ip -6 addr add $VIP6/128 dev lo 2>/dev/null
    ip -6 rule add from $VIP6/128 pref 1 table {table_id}

    # Masquerade
    iptables -t nat -I POSTROUTING 1 -s $VIP4/32 -o {interface} -j MASQUERADE

    # Bind Proxy Engine (with logging for debugging)
    nohup /data/data/com.termux/files/usr/bin/microsocks -i 127.0.0.1 -p $PORT -b $VIP6 > /data/local/tmp/microsocks_$PORT.log 2>&1 &
done
echo "EXPLOIT DEPLOYED"
"""
        # Write locally
        with open("farm_master.sh", "w") as f:
            f.write(script)
            
        # Push and Execute
        subprocess.run(["adb", "push", "farm_master.sh", "/data/local/tmp/farm_master.sh"], capture_output=True)
        adb.run_shell("chmod +x /data/local/tmp/farm_master.sh", root=True)
        adb.run_shell("/data/local/tmp/farm_master.sh", root=True)
        
        # Bridge the ports to the Ubuntu Laptop
        adb.remove_all_forwards()
        nodes = []
        for i in range(1, count + 1):
            port = 8000 + i
            vip6 = f"{prefix}::100{i}"
            adb.forward_port(port, port)
            nodes.append(Node(
                node_id=i, 
                internal_port=port, 
                external_port=port, 
                ipv6_address=vip6,
                deployed_at=datetime.now()
            ))
            
        logger.info(f"✅ {count} Proxies Bridged to Ubuntu via USB.")
        return nodes

    def cleanup(self, adb: ADBController):
        logger.info("🧹 Cleaning up proxy processes and routing tables...")
        adb.run_shell("pkill -9 microsocks", root=True)
        adb.run_shell("iptables -t nat -F", root=True)
        adb.run_shell("ip rule flush pref 1", root=True)
        adb.run_shell("ip -6 rule flush pref 1", root=True)
        adb.remove_all_forwards()

# ─────────────────────────────────────────────────────────────
# HEALTH CHECKER & SEEKER (The Harvester)
# ─────────────────────────────────────────────────────────────
class HealthChecker:
    def check_node(self, port: int, dns64_ip: str = None):
        """Uses curl via subprocess to test the SOCKS5 proxy and get the external IPv4."""
        try:
            # If we have a DNS64 IP, use --resolve to bypass Termux DNS issues while keeping HTTPS
            if dns64_ip:
                cmd = [
                    'curl', '-s', '--max-time', '5', 
                    '--socks5', f'127.0.0.1:{port}',
                    '--resolve', f'api.ipify.org:443:{dns64_ip}',
                    'https://api.ipify.org'
                ]
            else:
                cmd = [
                    'curl', '-s', '--max-time', '5', 
                    '--socks5', f'127.0.0.1:{port}',
                    'https://api.ipify.org'
                ]
            
            start = time.time()
            res = subprocess.run(cmd, capture_output=True, text=True)
            latency = int((time.time() - start) * 1000)
            
            ip = res.stdout.strip()
            # Validate it's a real IPv4 address
            if res.returncode == 0 and re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                return ip, latency
                
            # If it failed, let's grab the microsocks log for debugging
            log_out = subprocess.run(['adb', 'shell', 'su', '-c', f'cat /data/local/tmp/microsocks_{port}.log'], capture_output=True, text=True)
            if log_out.stdout.strip():
                logger.error(f"Node {port} failed. Microsocks log: {log_out.stdout.strip()}")
                
            return None, 0
        except Exception as e:
            return None, 0

class SeekerAndBucket:
    def __init__(self, core_ref):
        self.core = core_ref
        self.health_checker = HealthChecker()
        self.db = core_ref.db_manager
        self.active = False
        self.thread = None
        self.logs = []
        self.seen_ips = set()
        self.unique_count = 0
        self.stats = {'avg_time_per_find': 0, 'total_checks': 0}

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")
        if len(self.logs) > 100:
            self.logs.pop(0)
        logger.info(msg)

    def start(self):
        self.active = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        self.log("Seeker & Keep-Alive Monitor Active.")

    def stop(self):
        self.active = False
        if self.thread:
            self.thread.join(timeout=2)

    def monitor_loop(self):
        self.log("Seeker Thread Started. Harvesting IPs...")
        from concurrent.futures import ThreadPoolExecutor
        
        strategies = [
            KeepaliveStrategy.SESSION_HTTPS.value,
            KeepaliveStrategy.SSE_STREAM.value,
            KeepaliveStrategy.SIM_BROWSING.value,
            KeepaliveStrategy.TCP_NULL_DRIP.value,
            KeepaliveStrategy.UDP_DRIP.value,
            KeepaliveStrategy.OS_KEEPALIVE.value,
            KeepaliveStrategy.ICMP_PING6.value
        ]
        strategy_idx = 0
        
        while self.active:
            current_unique = set()
            
            # Battle Royale: Assign different strategies to each node for testing
            strategies = [
                KeepaliveStrategy.SESSION_HTTPS.value,
                KeepaliveStrategy.SSE_STREAM.value,
                KeepaliveStrategy.SIM_BROWSING.value,
                KeepaliveStrategy.TCP_NULL_DRIP.value,
                KeepaliveStrategy.UDP_DRIP.value,
                KeepaliveStrategy.ICMP_PING6.value
            ]
            
            for i, node in enumerate(self.core.nodes):
                if node.strategy == KeepaliveStrategy.DRIFT.value:
                    strat = strategies[i % len(strategies)]
                    self.core.lab_manager.engine.start_strategy(node, strat, concurrency=3)

            dns64_ip = self.core.net_info.get('dns64_ip') if self.core.net_info else None
            
            def check_and_update(node):
                ip, latency = self.health_checker.check_node(node.external_port, dns64_ip)
                node.public_ipv4 = ip
                node.is_alive = bool(ip)
                node.latency_ms = latency
                return node, ip

            with ThreadPoolExecutor(max_workers=6) as executor:
                results = list(executor.map(check_and_update, self.core.nodes))

            for node, ip in results:
                self.stats['total_checks'] += 1
                if ip:
                    current_unique.add(ip)
                    if ip not in self.seen_ips:
                        self.seen_ips.add(ip)
                        self.db.record_ip(ip)
                        self.log(f"Node {node.node_id} ► {ip} [UNIQUE]")
                    else:
                        self.log(f"Node {node.node_id} ► {ip} [DUPLICATE]")
                        
                    # AUTO-ANCHOR LOGIC
                    if getattr(self.core, 'auto_anchor', True):
                        if node.strategy == KeepaliveStrategy.DRIFT.value:
                            if ip not in active_anchors:
                                strat = strategies[strategy_idx % len(strategies)]
                                strategy_idx += 1
                                self.log(f"⚓ AUTO-ANCHOR: Locking Node {node.node_id} to {ip} via {strat}")
                                self.core.lab_manager.assign_strategy(node.node_id, strat)
                                active_anchors.add(ip)
                else:
                    node.consecutive_failures += 1
                    self.log(f"Node {node.node_id} ► CONNECTION FAILED")
                    if getattr(self.core, 'auto_anchor', True) and node.strategy != KeepaliveStrategy.DRIFT.value:
                        self.log(f"⚠️ Node {node.node_id} lost anchor. Reverting to DRIFT mode.")
                        self.core.lab_manager.assign_strategy(node.node_id, KeepaliveStrategy.DRIFT.value)

            self.unique_count = len(current_unique)
            time.sleep(15) # 15s refresh as requested

    def get_hunting_status(self):
        return {
            'hunters': {1: {'active': self.active}}, 
            'seen_ips': len(self.seen_ips), 
            'logs': self.logs
        }
        
    def get_hunter_stats(self):
        return self.stats

# ─────────────────────────────────────────────────────────────
# CORE ORCHESTRATOR
# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# KEEP-ALIVE ENGINE (The Lab)
# ─────────────────────────────────────────────────────────────
class KeepAliveEngine:
    def __init__(self):
        self.running = True
        self._dns_cache = {}

    def start_strategy(self, node: Node, strategy: str, concurrency: int = 3):
        """Starts the strategy with multiple concurrent threads using Generation Locking."""
        node.strategy = strategy
        node.strategy_gen += 1 # Increment generation to kill old threads
        node.pulse_count = 0
        node.bytes_sent = 0
        
        current_gen = node.strategy_gen
        logger.info(f"🚀 Starting NUCLEAR Keep-Alive [{strategy}] on Node {node.node_id} (Gen {current_gen})")
        
        for i in range(concurrency):
            t = threading.Thread(
                target=self._run_strategy, 
                args=(node, strategy, i, current_gen), 
                daemon=True
            )
            t.start()

    def stop_strategy(self, node_id: int):
        # We don't need to do anything here, the threads will die when strategy_gen increments
        pass

    def stop_all(self):
        self.running = False

    def _resolve_dns64(self, adb: ADBController, hostname: str) -> str:
        """Resolves a hostname to its DNS64 IPv6 address using the phone's native DNS with caching."""
        if hostname in self._dns_cache:
            return self._dns_cache[hostname]
            
        out = adb.run_shell(f"ping6 -c 1 {hostname}")
        for line in out.split('\n'):
            if 'PING' in line:
                match = re.search(r'\((.*?)\)', line)
                if match:
                    res = match.group(1)
                    self._dns_cache[hostname] = res
                    return res
        return hostname

    def _run_strategy(self, node: Node, strategy: str, thread_idx: int, gen: int):
        """Executes the selected keep-alive strategy with Generation Locking and Deep Logging."""
        adb = ADBController()
        node_log = lambda m: logger.info(f"Node {node.node_id} [T{thread_idx}][G{gen}]: {m}")
        
        while self.running and node.strategy_gen == gen:
            try:
                if strategy == KeepaliveStrategy.SESSION_HTTPS.value:
                    target_ip = self._resolve_dns64(adb, "api.ipify.org")
                    
                    node_log(f"Connecting to Proxy 127.0.0.1:{node.external_port}...")
                    s = socks.socksocket()
                    s.set_proxy(socks.SOCKS5, "127.0.0.1", node.external_port)
                    s.settimeout(15)
                    
                    try:
                        s.connect((target_ip, 443))
                        node_log("Proxy Connection Established. Starting SSL Handshake...")
                        
                        ctx = ssl.create_default_context()
                        ss = ctx.wrap_socket(s, server_hostname="api.ipify.org")
                        node_log("Nuclear SSL Session Active. Pulsing...")
                        
                        while self.running and node.strategy_gen == gen:
                            try:
                                req = b"GET / HTTP/1.1\r\nHost: api.ipify.org\r\nConnection: keep-alive\r\n\r\n"
                                ss.sendall(req)
                                node.bytes_sent += len(req)
                                
                                ss.settimeout(5)
                                resp = ss.recv(1024)
                                if resp:
                                    node.pulse_count += 1
                                
                                time.sleep(1)
                            except Exception as e:
                                node_log(f"Pulse error: {e}")
                                break
                        ss.close()
                    except Exception as e:
                        node_log(f"Connection/SSL error: {e}")
                        time.sleep(2)
                    finally:
                        s.close()

                elif strategy == KeepaliveStrategy.SSE_STREAM.value:
                    target_ip = self._resolve_dns64(adb, "stream.wikimedia.org")
                    url = f"https://[{target_ip}]/v2/stream/recentchange"
                    # Use curl through the proxy to keep the downstream open
                    cmd = ['curl', '-g', '-N', '-s', '--socks5', f'127.0.0.1:{node.external_port}', '-H', 'Host: stream.wikimedia.org', url]
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    while self.running and node.strategy_gen == gen:
                        line = proc.stdout.readline()
                        if line:
                            node.pulse_count += 1
                            node.bytes_sent += len(line)
                        if proc.poll() is not None: break
                    if proc.poll() is None: proc.terminate()

                elif strategy == KeepaliveStrategy.SIM_BROWSING.value:
                    hosts = ["api.ipify.org", "www.google.com", "www.wikipedia.org"]
                    while self.running and node.strategy_gen == gen:
                        host = random.choice(hosts)
                        target_ip = self._resolve_dns64(adb, host)
                        s = socks.socksocket()
                        s.set_proxy(socks.SOCKS5, "127.0.0.1", node.external_port)
                        s.settimeout(10)
                        try:
                            s.connect((target_ip, 80))
                            req = f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
                            s.sendall(req)
                            node.bytes_sent += len(req)
                            if s.recv(1024): node.pulse_count += 1
                        except: pass
                        finally: s.close()
                        time.sleep(random.randint(2, 5))

                elif strategy == KeepaliveStrategy.TCP_NULL_DRIP.value:
                    target_ip = self._resolve_dns64(adb, "8.8.8.8")
                    s = socks.socksocket()
                    s.set_proxy(socks.SOCKS5, "127.0.0.1", node.external_port)
                    s.settimeout(10)
                    try:
                        s.connect((target_ip, 53))
                        while self.running and node.strategy_gen == gen:
                            s.sendall(b'\x00')
                            node.bytes_sent += 1
                            node.pulse_count += 1
                            time.sleep(2)
                    except: pass
                    finally: s.close()

                elif strategy == KeepaliveStrategy.UDP_DRIP.value:
                    target_ip = self._resolve_dns64(adb, "8.8.8.8")
                    s = socks.socksocket(socket.AF_INET6, socket.SOCK_DGRAM)
                    s.set_proxy(socks.SOCKS5, "127.0.0.1", node.external_port)
                    while self.running and node.strategy_gen == gen:
                        try:
                            s.sendto(b'\x00', (target_ip, 53, 0, 0))
                            node.bytes_sent += 1
                            node.pulse_count += 1
                            time.sleep(1)
                        except: break
                    s.close()

                elif strategy == KeepaliveStrategy.OS_KEEPALIVE.value:
                    # Target api.ipify.org via Proxy with OS-level keep-alives
                    target_ip = self._resolve_dns64(adb, "api.ipify.org")
                    s = socks.socksocket()
                    s.set_proxy(socks.SOCKS5, "127.0.0.1", node.external_port)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    try:
                        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
                        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
                        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 10)
                    except: pass
                    try:
                        s.connect((target_ip, 80))
                        while self.running and node.strategy_gen == gen:
                            time.sleep(5)
                    except: pass
                    finally: s.close()

                elif strategy == KeepaliveStrategy.ICMP_PING6.value:
                    target_ip = self._resolve_dns64(adb, "api.ipify.org")
                    cmd = ['adb', 'shell', 'su', '-c', f"ping6 -I {node.ipv6_address} -i 0.5 {target_ip}"]
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    while self.running and node.strategy_gen == gen:
                        line = proc.stdout.readline()
                        if line:
                            node.pulse_count += 1
                            node.bytes_sent += 64 # ICMP packet size
                        if proc.poll() is not None: break
                    if proc.poll() is None: proc.terminate()

                else:
                    time.sleep(5)
            except Exception as e:
                node_log(f"Strategy Error: {str(e)}")
                time.sleep(5)

class KeepAliveLabManager:
    def __init__(self, core_ref):
        self.core = core_ref
        self.engine = KeepAliveEngine()
        
    def assign_strategy(self, node_id: int, strategy: str):
        for node in self.core.nodes:
            if node.node_id == node_id:
                self.engine.start_strategy(node, strategy)
                return True
        return False
        
    def is_test_running(self): 
        return len(self.engine.active_threads) > 0

class ProxyFarmCore:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.adb = ADBController()
        self.network_discovery = NetworkDiscovery()
        self.node_manager = NodeManager()
        self.seeker = SeekerAndBucket(self)
        self.lab_manager = KeepAliveLabManager(self)
        
        self.net_info = None
        self.nodes: List[Node] = []
        self.monitoring = False
        self.auto_rotate = True
        self.auto_anchor = True
        self.node_count = 6  # CHANGED: Default to 6 nodes to test all strategies
        
    def initialize(self):
        # Verify ADB connection
        out = self.adb.run_shell("echo alive")
        if "alive" not in out:
            logger.error("ADB device not found or unauthorized!")
            return False
        return True
        
    def deploy_nodes(self, node_count=6, target_unique=None): # CHANGED: Default to 6
        self.node_count = node_count
        try:
            self.net_info = self.network_discovery.discover(self.adb)
            self.nodes = self.node_manager.deploy_exploit(self.adb, node_count, self.net_info)
            return True
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False
            
    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.seeker.start()
        return True
        
    def stop_monitoring(self):
        self.monitoring = False
        self.seeker.stop()
        return True
        
    def cleanup(self):
        self.stop_monitoring()
        self.lab_manager.engine.stop_all()
        self.node_manager.cleanup(self.adb)
        self.nodes = []
        return True
        
    def force_rotation(self):
        """The master rotation sequence."""
        logger.info("🔄 Executing Master Rotation Sequence...")
        was_monitoring = self.monitoring
        if was_monitoring:
            self.stop_monitoring()
            
        self.node_manager.cleanup(self.adb)
        self.adb.toggle_airplane_mode()
        
        try:
            self.net_info = self.network_discovery.discover(self.adb)
            self.nodes = self.node_manager.deploy_exploit(self.adb, self.node_count, self.net_info)
        except Exception as e:
            logger.error(f"Rotation deployment failed: {e}")
            
        if was_monitoring:
            self.start_monitoring()
        return True

    def toggle_auto_rotation(self, enabled):
        self.auto_rotate = enabled
        return True

    def get_system_status(self):
        alive = sum(1 for n in self.nodes if n.is_alive)
        dead = len(self.nodes) - alive
        
        return {
            "phone_temperature": self.adb.get_device_temperature(),
            "adb_connected": True,
            "net_info": self.net_info,
            "nodes": [n.to_dict() for n in self.nodes],
            "alive_nodes": alive,
            "dead_nodes": dead,
            "unique_ips": self.seeker.unique_count if self.seeker else 0,
            "monitoring_active": self.monitoring,
            "hunting_status": self.seeker.get_hunting_status() if self.seeker else {},
            "hunter_stats": self.seeker.get_hunter_stats() if self.seeker else {},
            "lab_test_running": len(self.lab_manager.engine.active_threads) > 0 if self.lab_manager else False,
            "timestamp": datetime.now().isoformat()
        }

    # Stubs for UI compatibility
    def get_detailed_node(self, node_id): return None
    def check_keepalive_test(self): return {}
    def get_ip_explorer_data(self): return {}
    def get_configuration(self): return {}
    def update_configuration(self, data): return True

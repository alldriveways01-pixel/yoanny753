import time
import sys
import os
from proxy_farm import ProxyFarmCore, KeepaliveStrategy
from colorama import init, Fore

# Initialize colorama for pretty terminal output
init(autoreset=True)

def print_banner():
    print(Fore.CYAN + "=" * 80)
    print(Fore.CYAN + " " * 25 + "🎯 SNIPER KEEP-ALIVE TEST 🎯")
    print(Fore.CYAN + " " * 22 + "1 NODE | 1 STRATEGY | 30s REFRESH")
    print(Fore.CYAN + "=" * 80)
    print()

def main():
    print_banner()
    
    core = ProxyFarmCore()
    
    print(Fore.BLUE + "[*] Initializing ADB and Network Discovery...")
    if not core.initialize():
        print(Fore.RED + "[!] Failed to initialize. Is the phone connected?")
        return

    # Deploy ONLY 1 node
    print(Fore.BLUE + "[*] Deploying 1 Sniper Node on Port 8001...")
    if not core.deploy_nodes(node_count=1):
        print(Fore.RED + "[!] Deployment failed.")
        return

    # Force the most successful strategy: SESSION_HTTPS (Now in NUCLEAR MODE)
    node = core.nodes[0]
    strategy = KeepaliveStrategy.SESSION_HTTPS.value
    print(Fore.BLUE + f"[*] Forcing {Fore.RED}NUCLEAR{Fore.BLUE} Strategy: {Fore.MAGENTA}{strategy} (3 Threads)")
    
    # Start the keep-alive engine for this node with 3 concurrent threads
    core.lab_manager.engine.start_strategy(node, strategy, concurrency=3)
    
    print(Fore.GREEN + "[+] Sniper Node Active. Monitoring every 15 seconds...")
    print(Fore.YELLOW + "[!] Press Ctrl+C to stop.")
    print("-" * 80)
    
    try:
        start_ip = None
        start_time = time.time()
        
        while True:
            # Perform a manual health check
            dns64_ip = core.net_info.get('dns64_ip')
            ip, latency = core.seeker.health_checker.check_node(node.external_port, dns64_ip)
            
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            timer_str = f"{mins:02d}:{secs:02d}"
            
            # Traffic Accounting
            pulses = node.pulse_count
            kb_sent = node.bytes_sent / 1024
            
            if ip:
                if not start_ip:
                    start_ip = ip
                    print(Fore.MAGENTA + f"[{time.strftime('%H:%M:%S')}] ⚓ TARGET LOCKED: {Fore.WHITE}{ip}")
                
                if ip == start_ip:
                    status_color = Fore.GREEN
                    status_text = "STABLE"
                else:
                    status_color = Fore.RED
                    status_text = "ROTATED!"
                    # Update start_ip to the new one to track the next rotation
                    start_ip = ip
                
                traffic_info = f"Pulses: {Fore.CYAN}{pulses:<4}{Fore.WHITE} | Sent: {Fore.CYAN}{kb_sent:.1f}KB"
                print(f"[{time.strftime('%H:%M:%S')}] [{timer_str}] IP: {ip:<15} | {traffic_info} | Status: {status_color}{status_text}")
            else:
                print(Fore.RED + f"[{time.strftime('%H:%M:%S')}] [{timer_str}] Node 1 ► CONNECTION FAILED")
            
            # Sleep for exactly 15 seconds as ordered
            time.sleep(15)
            
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[!] Stopping Sniper Test...")
        core.cleanup()
        print(Fore.GREEN + "[+] Done.")

if __name__ == "__main__":
    main()

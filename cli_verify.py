import time
import sys
import os
from proxy_farm import ProxyFarmCore, KeepaliveStrategy
from colorama import init, Fore, Style

# Initialize colorama for pretty terminal output
init(autoreset=True)

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def print_banner():
    local_ip = get_local_ip()
    print(Fore.CYAN + "=" * 80)
    print(Fore.CYAN + " " * 20 + "🚀 T-MOBILE NAT64 PROXY FARM - VERIFICATION CLI 🚀")
    print(Fore.CYAN + "=" * 80)
    print(Fore.WHITE + f"[*] Local Controller IP: {Fore.GREEN}{local_ip}")
    print(Fore.WHITE + f"[*] To test from another laptop, use SOCKS5: {Fore.GREEN}{local_ip}:[PORT]")
    print(Fore.CYAN + "=" * 80)
    print()

def print_status_table(nodes):
    # Clear screen (optional, but makes it look like a dashboard)
    # os.system('cls' if os.name == 'nt' else 'clear')
    
    print(Fore.YELLOW + f"{'ID':<4} | {'PORT':<6} | {'IPV6 (LOCAL)':<20} | {'IPV4 (PUBLIC)':<15} | {'LATENCY':<8} | {'STRATEGY':<15} | {'STATUS':<8}")
    print("-" * 85)
    
    for node in nodes:
        status_color = Fore.GREEN if node.is_alive else Fore.RED
        status_text = "ALIVE" if node.is_alive else "DEAD"
        
        ipv6_short = (node.ipv6_address[:17] + "...") if len(node.ipv6_address) > 20 else node.ipv6_address
        ipv4_text = node.public_ipv4 if node.public_ipv4 else "PENDING..."
        latency_text = f"{node.latency_ms}ms" if node.latency_ms > 0 else "N/A"
        
        print(f"{node.node_id:<4} | {node.external_port:<6} | {ipv6_short:<20} | {ipv4_text:<15} | {latency_text:<8} | {node.strategy:<15} | {status_color}{status_text}")

def main():
    print_banner()
    
    core = ProxyFarmCore()
    
    print(Fore.BLUE + "[*] Initializing ADB and Network Discovery...")
    if not core.initialize():
        print(Fore.RED + "[!] Failed to initialize. Is the phone connected via ADB?")
        return

    print(Fore.BLUE + f"[*] Deploying {core.node_count} nodes with NAT64 Exploit...")
    if not core.deploy_nodes(node_count=6):
        print(Fore.RED + "[!] Deployment failed. Check logs for details.")
        return

    print(Fore.GREEN + "[+] Nodes deployed successfully!")
    print(Fore.BLUE + "[*] Starting Seeker and Keep-Alive Engine...")
    core.start_monitoring()

    print(Fore.YELLOW + "[!] Entering Monitoring Loop. Press Ctrl+C to stop.")
    print()

    try:
        while True:
            # Print the table
            print_status_table(core.nodes)
            
            # Print unique IP count
            unique_ips = len(core.seeker.seen_ips)
            print(f"\n{Fore.MAGENTA}Total Unique IPs Discovered: {unique_ips}")
            
            # Print recent logs from the seeker
            if core.seeker.logs:
                print(f"\n{Fore.CYAN}Recent Activity:")
                for log in core.seeker.logs[-5:]:
                    print(f"  {log}")
            
            print("\n" + Fore.CYAN + "=" * 80 + "\n")
            
            time.sleep(10)
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[!] Stopping Farm...")
        core.seeker.stop()
        core.lab_manager.engine.stop_all()
        print(Fore.GREEN + "[+] Done.")

if __name__ == "__main__":
    main()

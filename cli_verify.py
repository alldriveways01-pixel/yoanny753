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
    
    print(Fore.YELLOW + f"{'ID':<4} | {'PORT':<6} | {'IPV4 (PUBLIC)':<15} | {'PULSES':<8} | {'SENT (KB)':<10} | {'STRATEGY':<15} | {'STATUS':<8}")
    print("-" * 85)
    
    for node in nodes:
        status_color = Fore.GREEN if node.is_alive else Fore.RED
        status_text = "ALIVE" if node.is_alive else "DEAD"
        
        ipv4_text = node.public_ipv4 if node.public_ipv4 else "PENDING..."
        kb_sent = node.bytes_sent / 1024
        
        print(f"{node.node_id:<4} | {node.external_port:<6} | {ipv4_text:<15} | {node.pulse_count:<8} | {kb_sent:<10.1f} | {node.strategy:<15} | {status_color}{status_text}")

def main():
    print_banner()
    
    core = ProxyFarmCore()
    
    print(Fore.BLUE + "[*] Initializing ADB and Network Discovery...")
    if not core.initialize():
        print(Fore.RED + "[!] Failed to initialize. Is the phone connected via ADB?")
        return

    print(Fore.BLUE + f"[*] Deploying {core.node_count} nodes with NAT64 Exploit...")
    if not core.deploy_nodes(node_count=10):
        print(Fore.RED + "[!] Deployment failed. Check logs for details.")
        return

    print(Fore.GREEN + "[+] Nodes deployed successfully!")
    print(Fore.BLUE + "[*] Starting Seeker and Keep-Alive Engine...")
    core.start_monitoring()

    print(Fore.YELLOW + "[!] Entering Monitoring Loop. Press 'L' for Lab Mode (Stop Seeker), or Ctrl+C to stop all.")
    print()

    lab_mode = False
    try:
        import select
        while True:
            # Check for keyboard input to toggle Lab Mode
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()
                if line.strip().lower() == 'l':
                    lab_mode = not lab_mode
                    if lab_mode:
                        print(Fore.MAGENTA + "\n[🧪] LAB MODE ACTIVE: Stopping Seeker. Keep-Alives will run in silence.")
                        core.seeker.stop()
                    else:
                        print(Fore.BLUE + "\n[🔍] SEEKER RESUMED: Monitoring active.")
                        core.start_monitoring()

            # Print the table
            print_status_table(core.nodes)
            
            # Print unique IP count
            unique_ips = len(core.seeker.seen_ips)
            print(f"\n{Fore.MAGENTA}Total Unique IPs Discovered: {unique_ips} | Lab Mode: {'ON' if lab_mode else 'OFF'}")
            
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

import subprocess
import sys

def run_adb(cmd):
    try:
        return subprocess.check_output(['adb', 'shell', cmd], stderr=subprocess.STDOUT).decode()
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    print("--- Microsocks Logs ---")
    for port in range(1081, 1087):
        print(f"Node on port {port}:")
        print(run_adb(f"cat /data/local/tmp/microsocks_{port}.log"))
        print("-" * 20)

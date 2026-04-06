# Proxy Farm OS

This is the complete, production-ready Proxy Farm OS. It includes a Python backend that communicates with your physical Android device via ADB, and a React frontend for monitoring and control.

## Prerequisites

1. **Python 3.8+** installed on your computer.
2. **Node.js 18+** installed on your computer.
3. **ADB (Android Debug Bridge)** installed and added to your system PATH.
4. An **Android Phone** (with a T-Mobile SIM, as per the script) connected to your computer via USB.
5. **USB Debugging** enabled on the phone, and authorized for your computer.
6. The phone must be **rooted** (required for `su -c` commands in the script).
7. `microsocks` installed on the phone at `/data/data/com.termux/files/usr/bin/microsocks` (or update the path in `proxy_farm.py`).

## Setup Instructions

### 1. Start the Python Backend

Open a terminal in this directory and run:

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run the Flask server
python app.py
```

The backend will start on `http://localhost:5000`.

### 2. Start the React Frontend

Open a **second terminal** in this directory and run:

```bash
# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```

The frontend will start on `http://localhost:5173` (or similar). Open that URL in your browser.

## Usage

1. Click **START** in the dashboard to initialize the ADB connection and deploy the proxy nodes.
2. The system will automatically discover your network interfaces, generate IPv6 addresses, and start hunting for unique IPv4 addresses.
3. You can monitor the live seeker activity, temperature, and proxy health directly from the dashboard.
4. Click **ROTATE IPs** to force an airplane mode toggle on the physical device.

## Troubleshooting

- **ADB Not Found**: Ensure `adb` is in your system PATH and you can run `adb devices` from your terminal.
- **Unauthorized Device**: Check your phone screen for an RSA fingerprint prompt and click "Allow".
- **SELinux Errors**: The script attempts to set SELinux to permissive (`setenforce 0`). This requires root. Ensure your phone is rooted and grants root access to ADB.

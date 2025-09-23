#!/bin/bash
# Setup script for Raspberry Pi Zero to create a captive portal with Flask app
# This script should be run as root (sudo)

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

echo "Setting up TerrE Robot Captive Portal on Raspberry Pi Zero"
echo "=========================================================="

# Install required packages
echo "Installing required packages..."
apt update
apt install -y hostapd dnsmasq python3-pip python3-smbus iptables wireless-tools

# Comprehensive WiFi hardware check
echo "Performing comprehensive WiFi hardware check..."

# Check if the Pi has WiFi hardware
echo "Checking for WiFi hardware..."
if ! lsusb | grep -q -i "wireless\|wifi\|802.11\|wlan\|rtl\|ath\|bcm"; then
  if ! lspci | grep -q -i "wireless\|wifi\|802.11\|wlan\|rtl\|ath\|bcm"; then
    if ! dmesg | grep -q -i "wireless\|wifi\|802.11\|wlan\|rtl\|ath\|bcm"; then
      echo "WARNING: No WiFi hardware detected! This Pi Zero may not have built-in WiFi."
      echo "You may need a USB WiFi adapter or a Pi Zero W with built-in WiFi."
    fi
  fi
fi

# Check if rfkill is blocking WiFi
echo "Checking if WiFi is blocked by rfkill..."
if command -v rfkill > /dev/null; then
  if rfkill list | grep -q "Soft blocked: yes"; then
    echo "WiFi is soft-blocked. Unblocking..."
    rfkill unblock wifi
    sleep 2
  fi
fi

# Try loading various WiFi drivers
echo "Attempting to load WiFi drivers..."
for driver in brcmfmac brcmutil cfg80211 mac80211 rtl8192cu rtl8xxxu; do
  echo "Loading $driver module..."
  modprobe $driver 2>/dev/null
done
sleep 3

# Check for WiFi interfaces
echo "Checking for WiFi interfaces..."
if ! iw dev | grep -q "Interface"; then
  # Check if firmware is missing
  if dmesg | grep -q "firmware"; then
    echo "Possible missing firmware detected. Installing additional firmware packages..."
    apt install -y firmware-brcm80211 firmware-realtek
    sleep 2
  fi
  
  # Last attempt - restart networking
  echo "Restarting networking services..."
  systemctl restart networking
  sleep 5
fi

# Final check for WiFi interfaces
if ! iw dev | grep -q "Interface"; then
  echo "ERROR: No WiFi interfaces found after multiple attempts."
  echo "This Pi Zero might not have WiFi capability or the hardware might be damaged."
  echo "Options:"
  echo "  1. Use a Pi Zero W with built-in WiFi"
  echo "  2. Connect a USB WiFi adapter"
  echo "  3. Continue without WiFi (the hotspot will not work)"
  echo ""
  echo "Do you want to continue anyway? (y/n)"
  read -r response
  if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Setup aborted."
    exit 1
  fi
  WIFI_IFACE="wlan0"  # Default even though it doesn't exist
else
  # Get the actual WiFi interface name
  WIFI_IFACE=$(iw dev | grep Interface | awk '{print $2}' | head -n1)
  echo "Found WiFi interface: $WIFI_IFACE"
fi

# Install Python packages
echo "Installing Python packages..."
pip3 install flask flask-socketio

# Configure static IP for WiFi interface
echo "Configuring static IP for $WIFI_IFACE..."
cat > /etc/dhcpcd.conf << EOF
interface $WIFI_IFACE
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

# Disable NetworkManager for WiFi interface
echo "Disabling NetworkManager for $WIFI_IFACE..."
mkdir -p /etc/NetworkManager/conf.d/
cat > /etc/NetworkManager/conf.d/10-unmanaged-devices.conf << EOF
[keyfile]
unmanaged-devices=interface-name:$WIFI_IFACE
EOF

# Configure dnsmasq for DNS spoofing (captive portal)
echo "Configuring dnsmasq for $WIFI_IFACE..."
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null
cat > /etc/dnsmasq.conf << EOF
interface=$WIFI_IFACE
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=wlan
address=/#/192.168.4.1
EOF

# Configure hostapd
echo "Configuring hostapd for $WIFI_IFACE..."
cat > /etc/hostapd/hostapd.conf << EOF
interface=$WIFI_IFACE
driver=nl80211
ssid=TerrE_Robot
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=YourPassword
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Tell hostapd where to find the config
sed -i 's/#DAEMON_CONF=""/DAEMON_CONF="\/etc\/hostapd\/hostapd.conf"/' /etc/default/hostapd

# Set up IP forwarding
echo "Configuring IP forwarding..."
sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf

# Create iptables rules
echo "Setting up iptables rules..."
cat > /etc/iptables.ipv4.nat << EOF
*nat
:PREROUTING ACCEPT [0:0]
:INPUT ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
-A PREROUTING -i $WIFI_IFACE -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 8080
-A PREROUTING -i $WIFI_IFACE -p tcp -m tcp --dport 443 -j REDIRECT --to-ports 8080
COMMIT
EOF

# Check if the user exists and get the username
echo "Checking for user account..."
CURRENT_USER=$(logname 2>/dev/null || echo "pi")

# If we couldn't determine the user, check if drak exists
if [ "$CURRENT_USER" = "pi" ] && id -u drak >/dev/null 2>&1; then
    CURRENT_USER="drak"
fi

echo "Using user account: $CURRENT_USER"

# Determine the correct path to the project
if [ -d "/home/$CURRENT_USER/myrepos/terrE-pi-socket-py" ]; then
    PROJECT_PATH="/home/$CURRENT_USER/myrepos/terrE-pi-socket-py"
elif [ -d "/home/$CURRENT_USER/terrE-pi-socket-py" ]; then
    PROJECT_PATH="/home/$CURRENT_USER/terrE-pi-socket-py"
else
    echo "Cannot find project directory. Please enter the full path to the terrE-pi-socket-py directory:"
    read -r PROJECT_PATH
fi

echo "Using project path: $PROJECT_PATH"

# Check if virtual environment exists
if [ -d "$PROJECT_PATH/venv" ]; then
    VENV_PATH="$PROJECT_PATH/venv"
else
    echo "Virtual environment not found at $PROJECT_PATH/venv"
    echo "Creating a new virtual environment..."
    python3 -m venv "$PROJECT_PATH/venv"
    VENV_PATH="$PROJECT_PATH/venv"
    
    # Install required packages in the virtual environment
    echo "Installing required Python packages in virtual environment..."
    "$VENV_PATH/bin/pip" install flask flask-socketio smbus
fi

# Create systemd service for Flask app
echo "Creating systemd service..."
cat > /etc/systemd/system/terre-flask.service << EOF
[Unit]
Description=TerrE Flask Control Server
After=network-online.target hostapd.service dnsmasq.service
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_PATH
ExecStartPre=/bin/sleep 30
ExecStart=/bin/bash -c 'source $VENV_PATH/bin/activate && python $PROJECT_PATH/flask-direct-server.py'
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=terre-flask
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

# Create startup script
echo "Creating startup script..."
cat > /usr/local/bin/start-terre.sh << EOF
#!/bin/bash

# Log function
log() {
  echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$1" >> /var/log/terre-startup.log
}

log "Starting TerrE Robot startup script"

# Wait for system to fully boot (Pi Zero needs more time)
log "Waiting for system to fully boot..."
sleep 30

# Load WiFi drivers if needed
log "Checking for WiFi interfaces..."
if ! iw dev | grep -q "Interface"; then
  log "No WiFi interfaces found, attempting to load drivers..."
  modprobe brcmfmac
  sleep 5
  
  # Check again
  if ! iw dev | grep -q "Interface"; then
    log "ERROR: Still no WiFi interfaces found. Check hardware connection."
  else
    log "WiFi interface detected after loading driver"
  fi
fi

# Get the actual WiFi interface name
WIFI_IFACE=\$(iw dev | grep Interface | awk '{print \$2}' | head -n1)
if [ -z "\$WIFI_IFACE" ]; then
  log "ERROR: Could not determine WiFi interface name"
  WIFI_IFACE="$WIFI_IFACE"  # Use the one detected during setup
fi
log "Using WiFi interface: \$WIFI_IFACE"

# Start hostapd and dnsmasq if not already running
log "Starting hostapd..."
systemctl start hostapd
sleep 5

log "Starting dnsmasq..."
systemctl start dnsmasq
sleep 5

# Apply iptables rules
log "Applying iptables rules..."
iptables-restore < /etc/iptables.ipv4.nat

# Wait for hotspot to be established
log "Waiting for hotspot to be established..."
sleep 15

# Initialize I2C if needed
log "Initializing I2C..."
if ! ls /dev/i2c-0 > /dev/null 2>&1; then
  log "Loading I2C kernel module"
  modprobe i2c-dev
  sleep 2
fi

# Make sure I2C permissions are correct
log "Setting I2C permissions..."
chmod 666 /dev/i2c-0 2>/dev/null

# Start the Flask server
log "Starting Flask server..."
systemctl start terre-flask.service

log "Startup script completed"
EOF

# Make startup script executable
chmod +x /usr/local/bin/start-terre.sh

# Create or modify rc.local
echo "Configuring rc.local..."
if [ ! -f /etc/rc.local ]; then
  cat > /etc/rc.local << EOF
#!/bin/bash
# rc.local
#
# This script is executed at the end of each multiuser runlevel.
# Make sure that the script will "exit 0" on success or any other
# value on error.
#
# By default this script does nothing.

# Run our startup script
/usr/local/bin/start-terre.sh &

exit 0
EOF
  chmod +x /etc/rc.local
else
  # Add our script before exit 0
  sed -i '/exit 0/i /usr/local/bin/start-terre.sh &' /etc/rc.local
fi

# Disable and stop wpa_supplicant with timeout
echo "Disabling wpa_supplicant..."

# Use timeout to prevent hanging
timeout 10s systemctl stop wpa_supplicant.service || echo "Warning: Timeout while stopping wpa_supplicant"
timeout 10s systemctl disable wpa_supplicant.service || echo "Warning: Timeout while disabling wpa_supplicant"
timeout 10s systemctl mask wpa_supplicant.service || echo "Warning: Timeout while masking wpa_supplicant"

# Force kill any remaining wpa_supplicant processes
echo "Checking for remaining wpa_supplicant processes..."
pkill -9 wpa_supplicant 2>/dev/null || echo "No wpa_supplicant processes found"

# Disable rpi-connect-wayvnc service if it exists
echo "Checking for rpi-connect-wayvnc service..."
if systemctl list-unit-files | grep -q rpi-connect-wayvnc; then
  echo "Disabling rpi-connect-wayvnc service..."
  systemctl stop rpi-connect-wayvnc.service
  systemctl disable rpi-connect-wayvnc.service
  systemctl mask rpi-connect-wayvnc.service
fi

# Remove any existing WiFi configurations
echo "Removing existing WiFi configurations..."
rm -f /etc/wpa_supplicant/wpa_supplicant.conf

# Enable our services
echo "Enabling services..."
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq
systemctl enable terre-flask.service

# Add swap file for better performance on Pi Zero
echo "Setting up swap file..."
dphys-swapfile swapoff
sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
dphys-swapfile setup
dphys-swapfile swapon

echo "Setup complete!"
echo "You can customize the WiFi name and password by editing /etc/hostapd/hostapd.conf"
echo "After rebooting, connect to the 'TerrE_Robot' WiFi network"
echo "Your phone should automatically open the control interface"
echo "If not, navigate to any website and you'll be redirected"
echo ""
echo "Would you like to reboot now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  reboot
fi

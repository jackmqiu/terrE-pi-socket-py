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
apt install -y hostapd dnsmasq python3-pip python3-smbus iptables

# Install Python packages
echo "Installing Python packages..."
pip3 install flask flask-socketio

# Configure static IP for wlan0
echo "Configuring static IP..."
cat > /etc/dhcpcd.conf << EOF
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

# Configure dnsmasq for DNS spoofing (captive portal)
echo "Configuring dnsmasq..."
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig 2>/dev/null
cat > /etc/dnsmasq.conf << EOF
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=wlan
address=/#/192.168.4.1
EOF

# Configure hostapd
echo "Configuring hostapd..."
cat > /etc/hostapd/hostapd.conf << EOF
interface=wlan0
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
-A PREROUTING -i wlan0 -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 8080
-A PREROUTING -i wlan0 -p tcp -m tcp --dport 443 -j REDIRECT --to-ports 8080
COMMIT
EOF

# Create systemd service for Flask app
echo "Creating systemd service..."
cat > /etc/systemd/system/terre-flask.service << EOF
[Unit]
Description=TerrE Flask Control Server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/terrE-pi-socket-py
ExecStart=/usr/bin/python3 /home/pi/terrE-pi-socket-py/flask-direct-server.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=terre-flask

[Install]
WantedBy=multi-user.target
EOF

# Create startup script
echo "Creating startup script..."
cat > /usr/local/bin/start-terre.sh << EOF
#!/bin/bash
# Wait for network interfaces to be up (Pi Zero needs more time)
sleep 30

# Start hostapd and dnsmasq if not already running
systemctl start hostapd
systemctl start dnsmasq

# Apply iptables rules
iptables-restore < /etc/iptables.ipv4.nat

# Wait for hotspot to be established
sleep 15

# Start the Flask server
systemctl start terre-flask.service
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

# Enable services
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

#!/bin/bash
# Undo script for TerrE Robot Captive Portal setup
# This script reverses all changes made by setup-pi-zero.sh

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

echo "Undoing TerrE Robot Captive Portal Setup"
echo "========================================="
echo ""
echo "This will restore your Pi Zero to normal WiFi client mode."
echo "Are you sure you want to continue? (y/n)"
read -r response
if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  echo "Undo aborted."
  exit 0
fi

# Stop and disable services
echo "Stopping and disabling services..."
systemctl stop terre-flask.service 2>/dev/null
systemctl disable terre-flask.service 2>/dev/null
systemctl stop hostapd 2>/dev/null
systemctl disable hostapd 2>/dev/null
systemctl stop dnsmasq 2>/dev/null
systemctl disable dnsmasq 2>/dev/null

# Remove service files
echo "Removing service files..."
rm -f /etc/systemd/system/terre-flask.service
systemctl daemon-reload

# Unmask and re-enable wpa_supplicant
echo "Re-enabling wpa_supplicant..."
systemctl unmask wpa_supplicant.service 2>/dev/null
systemctl enable wpa_supplicant.service 2>/dev/null

# Unmask rpi-connect-wayvnc if it was masked
echo "Re-enabling rpi-connect-wayvnc if it exists..."
if systemctl list-unit-files | grep -q rpi-connect-wayvnc; then
  systemctl unmask rpi-connect-wayvnc.service 2>/dev/null
  systemctl enable rpi-connect-wayvnc.service 2>/dev/null
fi

# Restore original dnsmasq configuration
echo "Restoring dnsmasq configuration..."
if [ -f /etc/dnsmasq.conf.orig ]; then
  mv /etc/dnsmasq.conf.orig /etc/dnsmasq.conf
else
  rm -f /etc/dnsmasq.conf
fi

# Remove hostapd configuration
echo "Removing hostapd configuration..."
rm -f /etc/hostapd/hostapd.conf

# Restore default hostapd settings
echo "Restoring default hostapd settings..."
sed -i 's/DAEMON_CONF="\/etc\/hostapd\/hostapd.conf"/#DAEMON_CONF=""/' /etc/default/hostapd 2>/dev/null

# Remove NetworkManager unmanaged devices configuration
echo "Removing NetworkManager configuration..."
rm -f /etc/NetworkManager/conf.d/10-unmanaged-devices.conf

# Restore dhcpcd configuration
echo "Restoring dhcpcd configuration..."
# Remove the static IP configuration we added
sed -i '/interface wlan0/,/nohook wpa_supplicant/d' /etc/dhcpcd.conf 2>/dev/null
sed -i '/interface wlan1/,/nohook wpa_supplicant/d' /etc/dhcpcd.conf 2>/dev/null

# Remove iptables rules
echo "Removing iptables rules..."
rm -f /etc/iptables.ipv4.nat

# Restore IP forwarding setting
echo "Restoring IP forwarding setting..."
sed -i 's/net.ipv4.ip_forward=1/#net.ipv4.ip_forward=1/' /etc/sysctl.conf 2>/dev/null

# Remove startup script
echo "Removing startup script..."
rm -f /usr/local/bin/start-terre.sh

# Remove startup script from rc.local
echo "Removing startup script from rc.local..."
if [ -f /etc/rc.local ]; then
  sed -i '/start-terre.sh/d' /etc/rc.local
fi

# Remove log file
echo "Removing log file..."
rm -f /var/log/terre-startup.log

# Restore swap file settings (optional)
echo "Restoring swap file settings..."
if [ -f /etc/dphys-swapfile ]; then
  sed -i 's/CONF_SWAPSIZE=512/CONF_SWAPSIZE=100/' /etc/dphys-swapfile 2>/dev/null
  dphys-swapfile swapoff
  dphys-swapfile setup
  dphys-swapfile swapon
fi

# Restart networking services
echo "Restarting networking services..."
systemctl restart dhcpcd
systemctl restart NetworkManager 2>/dev/null

echo ""
echo "========================================="
echo "Undo complete!"
echo ""
echo "Your Pi Zero has been restored to normal WiFi client mode."
echo "You can now connect to WiFi networks normally."
echo ""
echo "Note: You may need to reconfigure your WiFi connection."
echo "Use 'sudo raspi-config' to set up WiFi or edit /etc/wpa_supplicant/wpa_supplicant.conf"
echo ""
echo "Would you like to reboot now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  echo "Rebooting..."
  reboot
else
  echo "Please reboot manually for all changes to take effect."
fi

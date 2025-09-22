# terrE-pi-socket-py
Code that runs onboard the terrE robot

## Overview
This repository contains Python code for controlling the terrE robot using a PCA9685 servo controller connected to a Raspberry Pi via I2C.

## Files
- `webserver.py`: Connects to a remote socket.io server to receive control commands
- `direct-webserver.py`: Runs a standalone HTTP server that serves a control webpage directly from the Pi
- `flask-direct-server.py`: Runs a Flask server with WebSockets for more responsive control

## Setup Options

### Option 1: Simple HTTP Server (direct-webserver.py)

#### Requirements
```
pip install adafruit-circuitpython-pca9685
```

#### Usage
1. Make sure your Pi Zero is configured in hotspot/access point mode
2. Run the server (may require root privileges for port 80):
   ```
   sudo python3 direct-webserver.py
   ```
3. Connect your phone to the Pi's WiFi network
4. Open a browser on your phone and navigate to the Pi's IP address (typically 192.168.4.1:8080)
5. Use the touch controls to drive the robot

### Option 2: Flask Server with WebSockets (flask-direct-server.py)

#### Requirements
```
pip install smbus flask flask-socketio
```

#### Usage
1. Make sure your Pi Zero is configured in hotspot/access point mode
2. Run the server:
   ```
   python3 flask-direct-server.py
   ```
3. Connect your phone to the Pi's WiFi network
4. Open a browser on your phone and navigate to the Pi's IP address (typically 192.168.4.1:8080)
5. Use the touch controls to drive the robot

#### Advantages of WebSockets
- More responsive control with real-time communication
- Immediate feedback when connection is lost
- Better touch response for mobile devices

### Notes
- Both servers run on port 8080 by default
- To run on port 80 (standard HTTP), edit the port in the script and run with sudo
- The PCA9685 is configured for 50Hz PWM frequency (standard for servos)
- All servos are initialized to neutral/stop positions on startup
- Wheel servos are on channels 0-3, lift servo is on channel 4

import smbus
import threading
import time
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO

# PCA9685 registers
PCA9685_ADDRESS = 0x40
MODE1 = 0x00
MODE2 = 0x01
SUBADR1 = 0x02
SUBADR2 = 0x03
SUBADR3 = 0x04
PRESCALE = 0xFE
LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09
ALL_LED_ON_L = 0xFA
ALL_LED_ON_H = 0xFB
ALL_LED_OFF_L = 0xFC
ALL_LED_OFF_H = 0xFD

# Initialize I2C bus
bus = smbus.SMBus(1)  # Use 1 for Raspberry Pi 2/3/4, use 0 for Pi 1

# Constants for servo control
SERVO_MIN_PULSE = 150  # Min pulse width (out of 4096)
SERVO_MAX_PULSE = 600  # Max pulse width (out of 4096)
SERVO_NEUTRAL = 375    # Neutral position (~1.5ms)

# PCA9685 helper functions
def pca9685_init():
    """Initialize the PCA9685 device"""
    try:
        # Reset the device
        bus.write_byte_data(PCA9685_ADDRESS, MODE1, 0x00)
        time.sleep(0.05)  # Wait for reset to complete
        
        # Set PWM frequency to 50Hz
        set_pwm_freq(50)
        
        # Initialize all channels to zero
        for i in range(16):
            set_pwm(i, 0, 0)
            
        print("PCA9685 initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing PCA9685: {e}")
        return False

def set_pwm_freq(freq_hz):
    """Set the PWM frequency in Hz (default: 50Hz for servos)"""
    freq_val = 25000000.0  # 25MHz internal oscillator
    prescale_val = round(freq_val / (4096.0 * freq_hz)) - 1
    
    # Get the current mode
    oldmode = bus.read_byte_data(PCA9685_ADDRESS, MODE1)
    
    # Put the device to sleep to set the prescaler
    newmode = (oldmode & 0x7F) | 0x10  # Sleep
    bus.write_byte_data(PCA9685_ADDRESS, MODE1, newmode)
    
    # Set the prescaler
    bus.write_byte_data(PCA9685_ADDRESS, PRESCALE, int(prescale_val))
    
    # Restore the previous mode
    bus.write_byte_data(PCA9685_ADDRESS, MODE1, oldmode)
    time.sleep(0.005)  # Wait for oscillator
    
    # Enable auto-increment
    bus.write_byte_data(PCA9685_ADDRESS, MODE1, oldmode | 0xA0)

def set_pwm(channel, on, off):
    """Set the PWM output for a channel"""
    if channel < 0 or channel > 15:
        raise ValueError("Channel must be between 0 and 15 inclusive")
        
    # Set the on and off times for the specified channel
    bus.write_byte_data(PCA9685_ADDRESS, LED0_ON_L + 4 * channel, on & 0xFF)
    bus.write_byte_data(PCA9685_ADDRESS, LED0_ON_H + 4 * channel, on >> 8)
    bus.write_byte_data(PCA9685_ADDRESS, LED0_OFF_L + 4 * channel, off & 0xFF)
    bus.write_byte_data(PCA9685_ADDRESS, LED0_OFF_H + 4 * channel, off >> 8)

def set_servo_pulse(channel, pulse):
    """Set servo pulse width (0-4095)"""
    pulse = max(SERVO_MIN_PULSE, min(SERVO_MAX_PULSE, pulse))
    set_pwm(channel, 0, pulse)

# Function to convert throttle (-1 to 1) to pulse width
def throttle_to_pulse(throttle):
    throttle = max(-1.0, min(1.0, throttle))  # Clamp between -1 and 1
    return int(SERVO_NEUTRAL + throttle * (SERVO_MAX_PULSE - SERVO_NEUTRAL) / 2)

# Function to convert angle (0-180) to pulse width
def angle_to_pulse(angle):
    angle = max(0, min(180, angle))  # Clamp between 0 and 180
    return int(SERVO_MIN_PULSE + (angle / 180) * (SERVO_MAX_PULSE - SERVO_MIN_PULSE))

# Initialize the PCA9685
pca9685_init()

movement = False
movement_thread = None
current_direction = None
wheel_thresholds = [0, 0, 0, 0]
stop_timer = None

def move_loop():
    global movement, current_direction, wheel_thresholds
    while movement:
        if current_direction and wheel_thresholds:
            # Apply the thresholds directly to the PCA9685 channels
            for i in range(4):
                if wheel_thresholds[i] == 0:
                    set_pwm(i, 0, 0)
                else:
                    pulse = throttle_to_pulse(wheel_thresholds[i])
                    set_servo_pulse(i, pulse)
        time.sleep(0.01)

def start_movement(direction, thresholds=None):
    global movement, movement_thread, current_direction, wheel_thresholds
    if thresholds:
        wheel_thresholds = thresholds
    if not movement:
        movement = True
        current_direction = direction
        movement_thread = threading.Thread(target=move_loop)
        movement_thread.start()
    else:
        current_direction = direction  # Switch direction while moving

def stop_movement():
    global movement, movement_thread, stop_timer
    movement = False
    # Stop all continuous servo channels
    for i in range(4):
        set_pwm(i, 0, 0)
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    
    # Clear the timer reference
    if stop_timer:
        stop_timer.cancel()
    stop_timer = None

# Movement presets
def move_forward():
    # Adjust these values based on your robot's configuration
    start_movement('forward', [0.5, -0.5, 0.5, -0.5])
    
def move_backward():
    start_movement('backward', [-0.5, 0.5, -0.5, 0.5])
    
def turn_left():
    start_movement('left', [0.5, 0.5, 0.5, 0.5])
    
def turn_right():
    start_movement('right', [-0.5, -0.5, -0.5, -0.5])

def set_lift(angle):
    angle = max(0, min(180, angle))
    pulse = angle_to_pulse(angle)
    set_servo_pulse(4, pulse)

# Create Flask app and SocketIO instance
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Create templates directory if it doesn't exist
import os
if not os.path.exists('templates'):
    os.makedirs('templates')

# Create the HTML template file
with open('templates/index.html', 'w') as f:
    f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>TerrE Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
            touch-action: manipulation;
        }
        .container {
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #333;
        }
        .controls {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-gap: 10px;
            margin: 20px 0;
        }
        .btn {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 15px 0;
            text-align: center;
            text-decoration: none;
            font-size: 16px;
            cursor: pointer;
            border-radius: 5px;
            user-select: none;
            touch-action: manipulation;
        }
        .btn:active {
            background-color: #3e8e41;
        }
        .btn-stop {
            background-color: #f44336;
            grid-column: 2;
        }
        .btn-stop:active {
            background-color: #d32f2f;
        }
        .btn-forward {
            grid-column: 2;
        }
        .btn-left {
            grid-column: 1;
            grid-row: 2;
        }
        .btn-right {
            grid-column: 3;
            grid-row: 2;
        }
        .btn-backward {
            grid-column: 2;
            grid-row: 3;
        }
        .lift-controls {
            margin-top: 30px;
        }
        .slider {
            width: 100%;
            margin: 10px 0;
        }
        .status {
            margin-top: 20px;
            padding: 10px;
            background-color: #ddd;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>TerrE Control</h1>
        
        <div class="controls">
            <button class="btn btn-forward" id="forward">Forward</button>
            <button class="btn btn-left" id="left">Left</button>
            <button class="btn btn-stop" id="stop">STOP</button>
            <button class="btn btn-right" id="right">Right</button>
            <button class="btn btn-backward" id="backward">Backward</button>
        </div>
        
        <div class="lift-controls">
            <h2>Lift Control</h2>
            <input type="range" min="0" max="180" value="90" class="slider" id="liftSlider">
            <p>Angle: <span id="liftValue">90</span>°</p>
        </div>
        
        <div class="status" id="status">
            Status: Connected
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        // Connect to the Socket.IO server
        const socket = io();
        const statusDiv = document.getElementById('status');
        
        // Connection status events
        socket.on('connect', () => {
            statusDiv.textContent = 'Status: Connected';
            statusDiv.style.backgroundColor = '#d4edda';
        });
        
        socket.on('disconnect', () => {
            statusDiv.textContent = 'Status: Disconnected';
            statusDiv.style.backgroundColor = '#f8d7da';
        });
        
        // Movement controls
        const forwardBtn = document.getElementById('forward');
        const backwardBtn = document.getElementById('backward');
        const leftBtn = document.getElementById('left');
        const rightBtn = document.getElementById('right');
        const stopBtn = document.getElementById('stop');
        
        // Add touch events for movement buttons
        forwardBtn.addEventListener('touchstart', () => socket.emit('move', 'forward'));
        forwardBtn.addEventListener('touchend', () => socket.emit('move', 'stop'));
        forwardBtn.addEventListener('mousedown', () => socket.emit('move', 'forward'));
        forwardBtn.addEventListener('mouseup', () => socket.emit('move', 'stop'));
        
        backwardBtn.addEventListener('touchstart', () => socket.emit('move', 'backward'));
        backwardBtn.addEventListener('touchend', () => socket.emit('move', 'stop'));
        backwardBtn.addEventListener('mousedown', () => socket.emit('move', 'backward'));
        backwardBtn.addEventListener('mouseup', () => socket.emit('move', 'stop'));
        
        leftBtn.addEventListener('touchstart', () => socket.emit('move', 'left'));
        leftBtn.addEventListener('touchend', () => socket.emit('move', 'stop'));
        leftBtn.addEventListener('mousedown', () => socket.emit('move', 'left'));
        leftBtn.addEventListener('mouseup', () => socket.emit('move', 'stop'));
        
        rightBtn.addEventListener('touchstart', () => socket.emit('move', 'right'));
        rightBtn.addEventListener('touchend', () => socket.emit('move', 'stop'));
        rightBtn.addEventListener('mousedown', () => socket.emit('move', 'right'));
        rightBtn.addEventListener('mouseup', () => socket.emit('move', 'stop'));
        
        stopBtn.addEventListener('click', () => socket.emit('move', 'stop'));
        
        // Lift control
        const liftSlider = document.getElementById('liftSlider');
        const liftValue = document.getElementById('liftValue');
        
        liftSlider.addEventListener('input', () => {
            liftValue.textContent = liftSlider.value;
        });
        
        liftSlider.addEventListener('change', () => {
            socket.emit('lift', parseInt(liftSlider.value));
        });
    </script>
</body>
</html>
""")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    stop_movement()  # Safety measure: stop all movement when client disconnects

@socketio.on('move')
def handle_move(direction):
    global stop_timer
    print(f"Move: {direction}")
    
    if direction == 'forward':
        move_forward()
        # Set a timer to stop movement after a short period for safety
        if stop_timer:
            stop_timer.cancel()
        stop_timer = threading.Timer(0.6, stop_movement)
        stop_timer.start()
    
    elif direction == 'backward':
        move_backward()
        if stop_timer:
            stop_timer.cancel()
        stop_timer = threading.Timer(0.6, stop_movement)
        stop_timer.start()
    
    elif direction == 'left':
        turn_left()
        if stop_timer:
            stop_timer.cancel()
        stop_timer = threading.Timer(0.6, stop_movement)
        stop_timer.start()
    
    elif direction == 'right':
        turn_right()
        if stop_timer:
            stop_timer.cancel()
        stop_timer = threading.Timer(0.6, stop_movement)
        stop_timer.start()
    
    elif direction == 'stop':
        stop_movement()

@socketio.on('lift')
def handle_lift(angle):
    print(f"Lift: {angle}")
    set_lift(angle)

if __name__ == '__main__':
    try:
        # Use 0.0.0.0 to make the server accessible from other devices on the network
        # Port 8080 is used by default, change to 80 if running with sudo
        print("Starting Flask-SocketIO server on 0.0.0.0:8080...")
        socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop_movement()
        print("Server stopped.")

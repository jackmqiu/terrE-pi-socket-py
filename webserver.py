import board
import busio
import adafruit_pca9685
import socketio
import threading
import time

sio = socketio.Client(
  reconnection=True,
  reconnection_attempts=5,
  reconnection_delay=1,
  reconnection_delay_max=5
)

# Initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialize PCA9685
pca = adafruit_pca9685.PCA9685(i2c)

# Set PWM frequency to 50Hz (standard for servos)
pca.frequency = 50

# Constants for servo control
SERVO_MIN_PULSE = 1000  # Min pulse length in microseconds
SERVO_MAX_PULSE = 2000  # Max pulse length in microseconds
SERVO_NEUTRAL = 1500    # Neutral position (1.5ms)

# Function to convert pulse width in microseconds to 16-bit value
def pulse_to_bits(pulse_us):
    pulse_us = max(SERVO_MIN_PULSE, min(SERVO_MAX_PULSE, pulse_us))
    return int((pulse_us / 1000000 * 50 * 65535))

# Function to convert throttle (-1 to 1) to pulse width
def throttle_to_pulse(throttle):
    throttle = max(-1.0, min(1.0, throttle))  # Clamp between -1 and 1
    return int(SERVO_NEUTRAL + throttle * (SERVO_MAX_PULSE - SERVO_NEUTRAL))

# Function to convert angle (0-180) to pulse width
def angle_to_pulse(angle):
    angle = max(0, min(180, angle))  # Clamp between 0 and 180
    return int(SERVO_MIN_PULSE + (angle / 180) * (SERVO_MAX_PULSE - SERVO_MIN_PULSE))

# Initialize all servo channels to neutral/stop position
for i in range(16):
    pca.channels[i].duty_cycle = 0

movement = False
movement_thread = None
current_direction = None
wheel_thresholds = [0, 0, 0, 0]
stop_timer = None

def move_loop():
  global movement, current_direction, wheel_thresholds
  while movement:
    if current_direction == 'move' and wheel_thresholds:
      # Apply the thresholds directly to the PCA9685 channels
      for i in range(4):
        if wheel_thresholds[i] == 0:
          pca.channels[i].duty_cycle = 0
        else:
          pulse = throttle_to_pulse(wheel_thresholds[i])
          pca.channels[i].duty_cycle = pulse_to_bits(pulse)

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
    pca.channels[i].duty_cycle = 0
  if movement_thread:
    movement_thread.join()
    movement_thread = None
  
  # Clear the timer reference
  stop_timer = None

@sio.event
def connect():
  print("connected to socket server")
  sio.emit('initializeDevice', {'deviceType': 'terrE', 'unit': '0.1'})

@sio.event
def disconnect():
  print("disconnected from server")

@sio.on('move')
def on_move(thresholds):
  global stop_timer
  print(f"move with thresholds: {thresholds}")
  start_movement('move', thresholds)
  
  # Cancel any existing timer to prevent jerky movement
  if stop_timer:
    stop_timer.cancel()
  
  # Create a new timer
  stop_timer = threading.Timer(0.6, stop_movement)
  stop_timer.start()

@sio.on('lift')
def on_lift(angle):
  print(f"lift servo to angle: {angle}")
  # Standard servos use angle values from 0 to 180 degrees
  # Ensure angle is within valid range
  angle = max(0, min(180, angle))
  pulse = angle_to_pulse(angle)
  pca.channels[4].duty_cycle = pulse_to_bits(pulse)

@sio.on('stop')
def on_stop():
  print("stop")
  stop_movement()

# Diagnostic handlers for individual servos
@sio.on('0')
def on_servo_0(value):
    global movement, movement_thread
    print(f"servo 0 throttle {value}")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    # Set all to 0
    for i in range(4):
        pca.channels[i].duty_cycle = 0
    if value == 0:
        pca.channels[0].duty_cycle = 0
    else:
        pulse = throttle_to_pulse(value)
        pca.channels[0].duty_cycle = pulse_to_bits(pulse)
    time.sleep(1)
    for i in range(4):
        pca.channels[i].duty_cycle = 0

@sio.on('1')
def on_servo_1(value):
    global movement, movement_thread
    print(f"servo 1 throttle {value}")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    for i in range(4):
        pca.channels[i].duty_cycle = 0
    if value == 0:
        pca.channels[1].duty_cycle = 0
    else:
        pulse = throttle_to_pulse(value)
        pca.channels[1].duty_cycle = pulse_to_bits(pulse)
    time.sleep(1)
    for i in range(4):
        pca.channels[i].duty_cycle = 0

@sio.on('2')
def on_servo_2(value):
    global movement, movement_thread
    print(f"servo 2 throttle {value}")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    for i in range(4):
        pca.channels[i].duty_cycle = 0
    if value == 0:
        pca.channels[2].duty_cycle = 0
    else:
        pulse = throttle_to_pulse(value)
        pca.channels[2].duty_cycle = pulse_to_bits(pulse)
    time.sleep(1)
    for i in range(4):
        pca.channels[i].duty_cycle = 0

@sio.on('3')
def on_servo_3(value):
    global movement, movement_thread
    print(f"servo 3 throttle {value}")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    for i in range(4):
        pca.channels[i].duty_cycle = 0
    if value == 0:
        pca.channels[3].duty_cycle = 0
    else:
        pulse = throttle_to_pulse(value)
        pca.channels[3].duty_cycle = pulse_to_bits(pulse)
    time.sleep(1)
    for i in range(4):
        pca.channels[i].duty_cycle = 0

if __name__ == '__main__':
  try:
    sio.connect('http://192.168.86.34:3000')
    sio.wait()
  except Exception as e:
    print(f"connect error: {e}")
  finally:
    stop_movement()
    if sio.connected:
      sio.disconnect()

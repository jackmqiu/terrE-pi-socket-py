import board
import busio
import adafruit_pca9685
import socketio
import threading
import time

from adafruit_servokit import ServoKit

sio = socketio.Client(
  reconnection=True,
  reconnection_attempts=5,
  reconnection_delay=1,
  reconnection_delay_max=5
)

i2c = board.I2C()
hat = adafruit_pca9685.PCA9685(i2c)
kit = ServoKit(channels=16)

movement = False
movement_thread = None
current_direction = None
wheel_thresholds = [0, 0, 0, 0]

def move_loop():
  global movement, current_direction, wheel_thresholds
  while movement:
    if current_direction == 'move' and wheel_thresholds:
      # Apply the thresholds directly, with wheel 0 and 1 reversed
      kit.continuous_servo[0].throttle = -wheel_thresholds[0]  # reversed
      kit.continuous_servo[1].throttle = -wheel_thresholds[1]  # reversed
      kit.continuous_servo[2].throttle = wheel_thresholds[2]
      kit.continuous_servo[3].throttle = wheel_thresholds[3]
    elif current_direction == 'forward':
      kit.continuous_servo[0].throttle = -1  # reversed
      kit.continuous_servo[1].throttle = -1  # reversed
      kit.continuous_servo[2].throttle = 1
      kit.continuous_servo[3].throttle = 1

    elif current_direction == 'backward':
      kit.continuous_servo[0].throttle = 1  # reversed
      kit.continuous_servo[1].throttle = 1  # reversed
      kit.continuous_servo[2].throttle = -1
      kit.continuous_servo[3].throttle = -1

    elif current_direction == 'left':
      kit.continuous_servo[0].throttle = -0.5  # reversed
      kit.continuous_servo[1].throttle = -1   # reversed
      kit.continuous_servo[2].throttle = 0.5
      kit.continuous_servo[3].throttle = 1

    elif current_direction == 'right':
      kit.continuous_servo[0].throttle = -1   # reversed
      kit.continuous_servo[1].throttle = -0.5 # reversed
      kit.continuous_servo[2].throttle = 1
      kit.continuous_servo[3].throttle = 0.5

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
  global movement, movement_thread
  movement = False
  kit.continuous_servo[0].throttle = 0
  kit.continuous_servo[1].throttle = 0
  kit.continuous_servo[2].throttle = 0
  kit.continuous_servo[3].throttle = 0
  if movement_thread:
    movement_thread.join()
    movement_thread = None

@sio.event
def connect():
  print("connected to socket server")
  sio.emit('initializeDevice', {'deviceType': 'terrE', 'unit': '0.1'})

@sio.event
def disconnect():
  print("disconnected from server")

@sio.on('forward')
def on_forward():
  print("forward")
  start_movement('forward')
  threading.Timer(0.6, stop_movement).start()

@sio.on('backward')
def on_backward():
  print("backward")
  start_movement('backward')
  threading.Timer(0.6, stop_movement).start()

@sio.on('left')
def on_left():
  print("left")
  start_movement('left')
  threading.Timer(0.6, stop_movement).start()

@sio.on('right')
def on_right():
  print("right")
  start_movement('right')
  threading.Timer(0.6, stop_movement).start()

@sio.on('move')
def on_move(thresholds):
  print(f"move with thresholds: {thresholds}")
  start_movement('move', thresholds)
  threading.Timer(0.6, stop_movement).start()

@sio.on('stop')
def on_stop():
  print("stop")
  stop_movement()

# Diagnostic handlers for individual servos
@sio.on('0')
def on_servo_0():
    global movement, movement_thread
    print("diagnostic: servo 0 throttle 1 for 1s, others 0")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    # Set all to 0
    for i in range(4):
        kit.continuous_servo[i].throttle = 0
    kit.continuous_servo[0].throttle = .5
    time.sleep(1)
    for i in range(4):
        kit.continuous_servo[i].throttle = 0

@sio.on('1')
def on_servo_1():
    global movement, movement_thread
    print("diagnostic: servo 1 throttle 1 for 1s, others 0")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    for i in range(4):
        kit.continuous_servo[i].throttle = 0
    kit.continuous_servo[1].throttle = .5
    time.sleep(1)
    for i in range(4):
        kit.continuous_servo[i].throttle = 0

@sio.on('2')
def on_servo_2():
    global movement, movement_thread
    print("diagnostic: servo 2 throttle 1 for 1s, others 0")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    for i in range(4):
        kit.continuous_servo[i].throttle = 0
    kit.continuous_servo[2].throttle = .5
    time.sleep(1)
    for i in range(4):
        kit.continuous_servo[i].throttle = 0

@sio.on('3')
def on_servo_3():
    global movement, movement_thread
    print("diagnostic: servo 3 throttle 1 for 1s, others 0")
    movement = False
    if movement_thread:
        movement_thread.join()
        movement_thread = None
    for i in range(4):
        kit.continuous_servo[i].throttle = 0
    kit.continuous_servo[3].throttle = .5
    time.sleep(1)
    for i in range(4):
        kit.continuous_servo[i].throttle = 0

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

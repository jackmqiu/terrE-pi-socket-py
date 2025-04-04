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

i2c = busio.I2C(board.SCL, board.SDA)
hat = adafruit_pca9685.PCA9685(i2c)
kit = ServoKit(channels=16)

movement = False
movement_thread = None
current_direction = None

def move_loop():
  global movement, current_direction
  while movement:
    if current_direction == 'forward':
      kit.continuous_servo[0].throttle = 1
      kit.continuous_servo[1].throttle = 1
      kit.continuous_servo[2].throttle = 1
      kit.continuous_servo[3].throttle = 1

    elif current_direction == 'backward':
      kit.continuous_servo[0].throttle = -1
      kit.continuous_servo[1].throttle = -1
      kit.continuous_servo[2].throttle = -1
      kit.continuous_servo[3].throttle = -1

    elif current_direction == 'left':
      kit.continuous_servo[0].throttle = 0.5
      kit.continuous_servo[1].throttle = 1
      kit.continuous_servo[2].throttle = 0.5
      kit.continuous_servo[3].throttle = 1

    elif current_direction == 'right':
      kit.continuous_servo[0].throttle = 1
      kit.continuous_servo[1].throttle = 0.5
      kit.continuous_servo[2].throttle = 1
      kit.continuous_servo[3].throttle = 0.5

    time.sleep(0.01)

def start_movement(direction):
  global movement, movement_thread, current_direction
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
  sio.emit('initializeDevice', {'deviceType': 'sword', 'swordName': 'yellow'})

@sio.event
def disconnect():
  print("disconnected from server")

@sio.on('forward')
def on_forward():
  start_movement('forward')

@sio.on('backward')
def on_backward():
  start_movement('backward')

@sio.on('left')
def on_left():
  start_movement('left')

@sio.on('right')
def on_right():
  start_movement('right')

@sio.on('stop')
def on_stop():
  stop_movement()

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

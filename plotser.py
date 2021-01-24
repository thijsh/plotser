import Tkinter as tk
from random import random
import RPi.GPIO as GPIO
import time
import math
import sys
import atexit

# Dimensions of plotter in mm (from stepper motors axes)
width = 1000
height = 1000
min_x = 100
min_y = 100
max_x = 900
max_y = 900
grid_small = 10
grid_large = 50
grid_background = "gray90" 
grid_small_color = "gray80"
grid_large_color = "gray70"
line_color = "gray50"
line_active_color = "forest green"
line_done_color = "magenta2"

# Stepper has 512x8 steps in one revolution = 0.184078 mm per 8 step cycle of 30 mm spool
spool_diameter = 30
cycle_mm = math.pi * spool_diameter / 512 # 0.184078 mm
step_mm = cycle_mm / 8 # 0.023 mm

steppers = [
  [12, 16, 18, 22], # GPIO 18, 23, 24, 25
  [32, 36, 38, 40], # GPIO 12, 16, 20, 21 
  [29, 31, 33, 35], # GPIO 5, 6, 13, 19
  [7, 11, 13, 15], #  GPIO 4, 17, 27, 22
]

steps = [
  [1,0,0,0],
  [1,1,0,0],
  [0,1,0,0],
  [0,1,1,0],
  [0,0,1,0],
  [0,0,1,1],
  [0,0,0,1],
  [1,0,0,1]
]

substep = [0, 0, 0, 0]
stepper_rate = 1500
stepper_delay = 1.0 / stepper_rate

# Test drawing
spiral_factor = 50.0
spiral_scale = 0.1
points = []
print("Calculating stepper motor movement")
for i in range(0, 10000):
  # todo: improve bounding box so line point moves to intersect instead of just min/max
  points.append([ 
    max(min(math.sin(i / spiral_factor) * i * spiral_scale + width / 2, max_x), min_x),
    max(min(math.cos(i / spiral_factor) * i * spiral_scale + height / 2, max_x), min_x),
  ])

# Set up GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
for pins in steppers:
  for pin in pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

# Set up clean exit
def exit_handler():
  print("Returning to home point")
  target = pythagoras([width/2, height/2])
  move_to(pos, target)
  print("Turning off stepper motors")
  GPIO.cleanup()
atexit.register(exit_handler)

# Init GUI
try:
  gui = tk.Tk()
except:
  print("GUI disabled, running headless")
if gui:
  print("GUI enabled, drawing stepper motor movement")
  canvas = tk.Canvas(gui, width=width, height=height)
  canvas.config(background=grid_background)
  canvas.pack()
  for x in range(0, width, grid_small):
    canvas.create_line(x, 0, x, height, fill=grid_large_color if x % grid_large == 0 else grid_small_color)
  for y in range(0, height, grid_small):
    canvas.create_line(0, y, width, y, fill=grid_large_color if y % grid_large == 0 else grid_small_color)
  for i in range(len(points) - 1):
    canvas.create_line(points[i][0], height - points[i][1], points[i+1][0], height - points[i+1][1], fill=line_color)
  canvas.create_line(min_x - 1, min_y - 1, max_x + 1, min_y - 1, fill=line_color, dash=(3,5), width=2)
  canvas.create_line(min_x - 1, min_y - 1, min_x - 1, max_y + 1, fill=line_color, dash=(3,5), width=2)
  canvas.create_line(max_x + 1, max_y + 1, max_x + 1, min_y - 1, fill=line_color, dash=(3,5), width=2)
  canvas.create_line(max_x + 1, max_y + 1, min_x - 1, max_y + 1, fill=line_color, dash=(3,5), width=2)
  gui.update()

def move_cycle(stepper, speed):
  for i in range(abs(speed)):
    for step in range(8) if speed > 0 else reversed(range(8)):
      for pin in range(4):
        GPIO.output(steppers[stepper][pin], steps[step][pin])
      time.sleep(stepper_delay)

def move_step(stepper, direction):
  if direction not in (1, -1): raise ValueError
  substep[stepper] = (substep[stepper] + direction) % 8
  for pin in range(4):
    GPIO.output(steppers[stepper][pin], steps[substep[stepper]][pin])

def get_directions(pos, target):
  directions = []
  for i in range(4):
    directions.append(
      1 if pos[i] < target[i] - cycle_mm else 
      -1 if pos[i] > target[i] + cycle_mm else 0
    )
  return directions

def pythagoras(xy):
  b = xy[1] ** 2
  l = xy[0] ** 2
  t = (height - xy[1]) ** 2
  r = (width - xy[0]) ** 2
  return [
    math.sqrt(b + l),
    math.sqrt(l + t),
    math.sqrt(t + r),
    math.sqrt(r + b),
  ]

def move_to(pos, target):
  directions = get_directions(pos, target)
  while directions != [0, 0, 0, 0]:
    for d in range(4):
      pos[d] += cycle_mm * directions[d]
    move_all(directions)
    directions = get_directions(pos, target)

def move_all(directions):
  for step in range(8):
    for stepper in range(4):
      if directions[stepper] is not 0:
        for pin in range(4):
          GPIO.output(steppers[stepper][pin], steps[ step if directions[stepper]==1 else 7 - step ][pin])
    time.sleep(stepper_delay)

# Follow points line with stepper motors, translate X,Y to BL,TL,TR,BR
pos = pythagoras(points[0])
for i in range(1, len(points)):
  target = pythagoras(points[i])
  if gui:
    canvas.create_line(
      points[i-1][0],
      height - points[i-1][1],
      points[i][0],
      height - points[i][1],
      fill=line_active_color,
      width=3
    )
    gui.update()
  print(
    # "Point:", i, "/", len(points),
    "- X:", round(points[i][0], 1), 
    "- Y:", round(points[i][1], 1), 
    "- BL:", round(target[0], 1),
    "- TL:", round(target[1], 1),
    "- TR:", round(target[2], 1),
    "- BR:", round(target[3], 1)
  )
  move_to(pos, target)
  if gui:
    canvas.create_line(
      points[i-1][0],
      height - points[i-1][1],
      points[i][0],
      height - points[i][1],
      fill=line_done_color,
      width=3
    )


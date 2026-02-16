""" go2_movement.py - Move the Go2 robot in a straight line for a specified distance and time.
Created on 17.01.2026 by Christopher Kania for Forschungsseminar, TH Köln."""

__author__      = "Christopher Kania"
__license__   = "Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)"
__version__ = "1.0"
__maintainer__ = "Christopher Kania"
__email__ = "kania.christopher@web.de"

from ikpy.chain import Chain
from ikpy.link import OriginLink, URDFLink
import matplotlib.pyplot
from mpl_toolkits.mplot3d import Axes3D
import math
import numpy as np
import time
import d1_servo_arm.arm_control as ac
import sys, pathlib
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
import threading

# get network interface name from terminal command: ifconfig
interface = "eno1"
ChannelFactoryInitialize(0, interface)

sport_client = SportClient()
sport_client.SetTimeout(10.0)
sport_client.Init()

D1_DIR = (pathlib.Path.cwd() / "d1_servo_arm")
if str(D1_DIR) not in sys.path:
    sys.path.insert(0, str(D1_DIR))

p = pathlib.Path("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_servo_arm")
sys.path.insert(0, str(p))
print("OK")

d1_550 = Chain.from_urdf_file("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_550_description/urdf/d1.urdf",active_links_mask=[True, True, True, True, True, True, True, False])


# Grabbing sequence 2, arm and go2: x and y difference

speed_x = 0.35  # m/s
speed_y = 0.5  # m/s
speed_yaw = 2.5  # rad/s

go2_x_distance = 0 #1.0 # meters
go2_y_distance = -1.0  # meters
go2_yaw_distance = 0 #math.pi/2  # radians

move_time = max(abs(go2_x_distance / speed_x), abs(go2_y_distance / speed_y), abs(go2_yaw_distance / speed_yaw))  # seconds
speed_x = go2_x_distance / move_time  # m/s
speed_y = go2_y_distance / move_time  # m/s
speed_yaw = go2_yaw_distance / move_time  # rad/s
print("Calculated move_time: %.2f seconds" % move_time)
print("Using speeds - X: %.2f m/s, Y: %.2f m/s, YAW: %.2f rad/s" % (speed_x, speed_y, speed_yaw))

def safe_rest(sport, settle_s=0.8):
    """Sauber parken: stoppen, hinlegen und Dämpfung aktivieren."""
    try: sport.StopMove()
    except Exception: pass
    time.sleep(0.1)
    try:
        sport.StandDown(); time.sleep(1.0)
    except Exception: pass
    time.sleep(settle_s)
    try:
        sport.Damp()
    except Exception: pass
    print("🛌 Roboter liegt in Dämpfungsmodus.")

def prepare_for_motion(sport, settle_s=0.8):
    try: sport.StopMove()
    except Exception: pass
    sport.RecoveryStand()
    time.sleep(settle_s)

# Function for Go2 movement
def move_go2():
    #pass
    #sport_client.StopMove()
    prepare_for_motion(sport_client)
    time.sleep(2)
    t_end = time.time() + move_time
    while time.time() < t_end:
        sport_client.Move(speed_x, speed_y, speed_yaw)
        time.sleep(0.1)
    sport_client.StopMove()
    time.sleep(2)
    safe_rest(sport_client)
            
#timer_start = time.time() # start timer before movement

move_go2()

# timer_end = time.time() # end timer after movement is complete
# print("Time to complete pick and place process: %.2f seconds" % (timer_end - timer_start))
# print("Both movements completed!")
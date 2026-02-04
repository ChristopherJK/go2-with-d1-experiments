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

# go2 movements 
speed_x = 0.35  # m/s
speed_y = 0.5  # m/s
speed_yaw = 0.0  # rad/s

go2_x_distance = 0.2  # meters
go2_y_distance = 0.0  # meters

move_time = max(abs(go2_x_distance / speed_x), abs(go2_y_distance / speed_y))  # seconds
speed_x = go2_x_distance / move_time  # m/s
speed_y = go2_y_distance / move_time  # m/s
print("Calculated move_time: %.2f seconds" % move_time)
print("Using speeds - X: %.2f m/s, Y: %.2f m/s" % (speed_x, speed_y))


# target positions d1 arm
target_position_1 = [0.3, 0.0, -0.02]
target_position_2 = [0.3, 0.0, 0.2]

# gripper positions
gripper_open = 20
gripper_closed = 0

# target orientations
target_orientation = [0, 0, -1]
orientation_axis = "Y"

# target poses
pose_1 = [target_position_1, gripper_open]
pose_2 = [target_position_1, gripper_closed]
pose_3 = [target_position_2, gripper_closed]
pose_4 = [target_position_2, gripper_open]
default_pose = [ d1_550.forward_kinematics(ac.STOW_ANGLES)[:3, 3], gripper_open ]

target_poses = [pose_1, pose_2, pose_3, pose_4, default_pose]     # target poses for full grabbing sequence

# Function for Go2 movement
def move_go2():
    t_end = time.time() + move_time
    while time.time() < t_end:
        sport_client.Move(speed_x, speed_y, speed_yaw)
        time.sleep(0.1)
    sport_client.StopMove()

# Function for arm movement
def move_arm():
    current_position = [0., 0., 0.]
    ac.torque_lock(60000)
    time.sleep(.5)
    for pose in target_poses:
        # calculate inverse kinematics for target pose
        joint_angles = d1_550.inverse_kinematics(pose[0], target_orientation, orientation_mode=orientation_axis)
        joint_angles_deg = np.degrees(joint_angles)
        joint_angles_formatted = [float(round(w, 2)) for w in joint_angles_deg]

        # delete first and last value, add gripper value
        joint_angles_formatted.pop(0) # delete first value (base)
        joint_angles_formatted.pop(-1) # delete last value (end-effector)
        joint_angles_formatted.append(pose[1]) # add gripper value

        # plot for safety check
        # ax = matplotlib.pyplot.figure().add_subplot(111, projection='3d')
        # d1_550.plot(joint_angles, ax, target=pose[0])
        # ax.set_xlabel('X')
        # ax.set_ylabel('Y')
        # ax.set_zlabel('Z')
        # matplotlib.pyplot.show()

        # check if position is reached and move to target position
        while not ac.compare_angles(joint_angles_formatted):
            ac.move_multi(joint_angles_formatted, mode=1)
            time.sleep(0.1)
            
timer_start = time.time() # start timer before movement
# Create threads for simultaneous execution
go2_thread = threading.Thread(target=move_go2)
arm_thread = threading.Thread(target=move_arm)

# Start both threads
go2_thread.start()
arm_thread.start()

# Wait for both threads to complete
go2_thread.join()
arm_thread.join()

timer_end = time.time() # end timer after movement is complete
print("Time to complete pick and place process: %.2f seconds" % (timer_end - timer_start))
print("Both movements completed!")
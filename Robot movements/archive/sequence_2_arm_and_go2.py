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

x_positions = [1., 0.4]
y_positions = [0.0, 0.2]
z_positions = [-0.13, 0.3]

x, y = 0, 0  # choose position index

# go2 movements 
# speed und time sind variablen die in Studien variieren können
# speed_constant = True
# time_constant = False
#
# move_time = 5  # seconds
# speed_x = 0.35  # m/s
# speed_y = 0.5  # m/s
# speed_yaw = 0  # rad/s
#
# go2_x_distance = x_positions[x]  # meters
# go2_y_distance = y_positions[y]  # meters
#
# def safe_rest(sport, settle_s=0.8):
#     """Sauber parken: stoppen, hinlegen und Dämpfung aktivieren."""
#     try: sport.StopMove()
#     except Exception: pass
#     time.sleep(0.1)
#     try:
#         sport.StandDown(); time.sleep(1.0)
#     except Exception: pass
#     time.sleep(settle_s)
#     try:
#         sport.Damp()
#     except Exception: pass
#     print("🛌 Roboter liegt in Dämpfungsmodus.")
#
# def prepare_for_motion(sport, settle_s=0.8):
#     try: sport.StopMove()
#     except Exception: pass
#     sport.RecoveryStand()
#     time.sleep(settle_s)
#
# if speed_constant and not time_constant:
#     move_time = max(abs(go2_x_distance / speed_x), abs(go2_y_distance / speed_y))  # seconds
#     speed_x = go2_x_distance / move_time  # m/s
#     speed_y = go2_y_distance / move_time  # m/s
#     print("Calculated move_time: %.2f seconds" % move_time)
#     print("Using speeds - X: %.2f m/s, Y: %.2f m/s" % (speed_x, speed_y))
# elif time_constant and not speed_constant:
#     speed_x = go2_x_distance / move_time  # m/s
#     speed_y = go2_y_distance / move_time  # m/s
#     print("Calculated speeds - X: %.2f m/s, Y: %.2f m/s" % (speed_x, speed_y))

# prepare_for_motion(sport_client)
# time.sleep(2)
# t_end = time.time() + move_time  # move for 'move_time' seconds
# while time.time() < t_end:
#     sport_client.Move(speed_x, speed_y, speed_yaw)
#     time.sleep(1)
# sport_client.StopMove()
# time.sleep(2)
# safe_rest(sport_client)
#
# ac.torque_lock(60000)
# time.sleep(.5)
#target positions

target_position_1 = [0.2, 0.0, z_positions[0]]
target_position_2 = [0.2, 0.0, z_positions[1]]
target_position_3 = [0., 0.2, 0.3]

# gripper positions
gripper_open = 20
gripper_closed = 0

# target orientations
target_orientation = [0, 0, -1]
orientation_axis = "Y"

# target poses
pose_1 = [target_position_1, gripper_open]
pose_2 = [target_position_1, gripper_closed]
pose_3 = [target_position_2, gripper_open]
pose_4 = [target_position_3, gripper_open]

target_poses = [pose_1, pose_3, pose_4]

current_position = [0., 0., 0.]
ac.torque_lock(60000)
time.sleep(.5)
timer_start = time.time() # start timer before movement
for pose in target_poses:

    #ac.torque_lock(60000)
    joint_angles = d1_550.inverse_kinematics(pose[0], target_orientation, orientation_mode=orientation_axis)
    joint_angles_deg = np.degrees(joint_angles)
    print(joint_angles_deg)
    joint_angles_formatted = [float(round(w, 2)) for w in joint_angles_deg]
    print(joint_angles_formatted)

    # delete first and last value, add gripper value
    joint_angles_formatted.pop(0) # delete first value (base)
    joint_angles_formatted.pop(-1) # delete last value (end-effector)
    joint_angles_formatted.append(pose[1]) # add gripper value
    print(joint_angles_formatted)

    # plot for safety check
    ax = matplotlib.pyplot.figure().add_subplot(111, projection='3d')
    d1_550.plot(joint_angles, ax, target=pose[0])
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    matplotlib.pyplot.show()

    #ac.torque_lock(60000)
    #check if position is reached and move to target position
    while not ac.compare_angles(joint_angles_formatted):
        ac.move_multi(joint_angles_formatted, mode=1)
        time.sleep(0.5)

timer_end = time.time() # end timer after movement is complete
print("Time to complete pick and place process: %.2f seconds" % (timer_end - timer_start))
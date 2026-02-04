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
# interface = "eno1"
# ChannelFactoryInitialize(0, interface)
#
# sport_client = SportClient()
# sport_client.SetTimeout(10.0)
# sport_client.Init()

D1_DIR = (pathlib.Path.cwd() / "d1_servo_arm")
if str(D1_DIR) not in sys.path:
    sys.path.insert(0, str(D1_DIR))

p = pathlib.Path("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_servo_arm")
sys.path.insert(0, str(p))
print("OK")

d1_550 = Chain.from_urdf_file("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_550_description/urdf/d1.urdf",active_links_mask=[True, True, True, True, True, True, True, False])


# Grabbing sequence 1, arm and go2: Z difference

z_positions = [0.0, 0.2]
# target positions
target_position_1 = [0.3, 0., z_positions[0]]
target_position_2 = [0.3, 0., z_positions[1]]

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

target_poses = [pose_1, pose_2, pose_3, pose_4]

current_position = [0., 0., 0.]

# Function for Go2 movement
def move_go2(i):
    if i == 1:
        print("go prone")
        #sport_client.StandDown();
        time.sleep(1.0)
    elif i == 3:
        print("stand up")
        #sport_client.StandUp();
        time.sleep(1.0)

# Function for arm movement
def move_arm():
    ac.torque_lock(60000)
    time.sleep(.5)
    for pose in target_poses:
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

        # check if position is reached and move to target position
        # while not ac.compare_angles(joint_angles_formatted):
        #     ac.move_multi(joint_angles_formatted, mode=1)
        #     time.sleep(0.5)

timer_start = time.time() # start timer before movement
# Create threads for simultaneous execution
threads = []

for i in [1, 2, 3]:
    t = threading.Thread(target=move_go2, args=(i,))
    t.start()
    threads.append(t)

arm_thread = threading.Thread(target=move_arm)
arm_thread.start()
threads.append(arm_thread)

# Jetzt warten wir darauf, dass alle Threads fertig werden
for t in threads:
    t.join()

timer_end = time.time() # end timer after movement is complete
print("Time to complete pick and place process: %.2f seconds" % (timer_end - timer_start))
print("All movements completed!")

# Funktioniert das so oder sollte das Threading wie in sequence_2_arm_and_go2_parallel gemacht werden?
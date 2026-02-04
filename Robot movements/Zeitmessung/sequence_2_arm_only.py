from ikpy.chain import Chain
from ikpy.link import OriginLink, URDFLink
import matplotlib.pyplot
from mpl_toolkits.mplot3d import Axes3D
import math
import numpy as np
import time
import d1_servo_arm.arm_control as ac
import sys, pathlib

D1_DIR = (pathlib.Path.cwd() / "d1_servo_arm")
if str(D1_DIR) not in sys.path:
    sys.path.insert(0, str(D1_DIR))

p = pathlib.Path("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_servo_arm")
sys.path.insert(0, str(p))
print("OK")

d1_550 = Chain.from_urdf_file("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_550_description/urdf/d1.urdf",active_links_mask=[True, True, True, True, True, True, True, False])


# Grabbing sequence 2, arm only: x and y difference

x_positions = [0.3, 0.3]
y_positions = [0.0, 0.2]
z_positions = [-0.02, 0.2]

# target positions
x, y = 0, 1  # choose position index

target_position_1 = [x_positions[x], y_positions[y], z_positions[0]]
target_position_2 = [x_positions[x], y_positions[y], z_positions[1]]

# gripper positions
gripper_open = 20
gripper_closed = 0

# target orientations
target_orientation = np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]]) #[0, 0, -1]
orientation_axis = "all" #"Y"

# target poses
pose_1 = [target_position_1, gripper_open]
pose_2 = [target_position_1, gripper_closed]
pose_3 = [target_position_2, gripper_closed]
pose_4 = [target_position_2, gripper_open]
default_pose = [ d1_550.forward_kinematics(ac.STOW_ANGLES)[:3, 3], gripper_open ]

target_poses = [pose_1, pose_2, pose_3, pose_4, default_pose] # target poses for full grabbing sequence

current_position = [0., 0., 0.]
ac.torque_lock(60000)
time.sleep(.5)
timer_start = time.time() # start timer before movement

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

    #check if position is reached and move to target position
    while not ac.compare_angles(joint_angles_formatted):
        ac.move_multi(joint_angles_formatted, mode=1)
        time.sleep(0.1)

timer_end = time.time() # end timer after movement is complete
print("Time to complete pick and place process: %.2f seconds" % (timer_end - timer_start))
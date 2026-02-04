import sys, pathlib
import time

import d1_servo_arm.arm_control as ac

D1_DIR = (pathlib.Path.cwd() / "d1_servo_arm")
if str(D1_DIR) not in sys.path:
    sys.path.insert(0, str(D1_DIR))

import sys, pathlib
p = pathlib.Path("/home/forschungsseminar2025/PycharmProjects/forschungsseminar-go2-pick-n-place/d1_servo_arm")
sys.path.insert(0, str(p))

print("OK")
ac.torque_lock(60000)
time.sleep(.5)
ac.go_stow(verify=False)

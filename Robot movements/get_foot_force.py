"""get_foot_force.py: Get the latest foot force sensor data from the GO2 robot using Unitree SDK 2 Python bindings.

Created on 17.01.2026 by Christopher Kania for Forschungsseminar, TH Köln."""

__author__      = "Christopher Kania"
__license__   = "Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)"
__version__ = "1.0"
__maintainer__ = "Christopher Kania"
__email__ = "kania.christopher@web.de"

import math
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_

from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.utils.timerfd import timerfd_settime
import time

# get network interface name from terminal command: ifconfig
interface = "eno1"
ChannelFactoryInitialize(0, interface)

sport_client = SportClient()
sport_client.SetTimeout(10.0)
sport_client.Init()

# global variable to store the latest foot force data
current_foot_force = [0, 0, 0, 0]

def foot_force_callback(msg: LowState_):
    global current_foot_force
    current_foot_force = msg.foot_force

def start_listener(wait_for_data=True, timeout=5.0):
    """Startet den Subscriber und wartet optional auf die ersten Daten."""
    global lowstate_sub
    lowstate_sub = ChannelSubscriber("rt/lowstate", LowState_)
    lowstate_sub.Init(foot_force_callback, 10)

    if wait_for_data:
        t0 = time.time()
        while current_foot_force == [0, 0, 0, 0]:
            time.sleep(0.01)
            if time.time() - t0 > timeout:
                print("⚠️ Warnung: Keine foot_force-Daten erhalten.")
                break

def get_latest_low_state():
    return {"Foot sensor forces": current_foot_force}

if __name__ == "__main__":
    # nur laufen lassen, wenn man das Skript direkt ausführt
    start_listener()
    while True:
        print(get_latest_low_state())
        time.sleep(1)
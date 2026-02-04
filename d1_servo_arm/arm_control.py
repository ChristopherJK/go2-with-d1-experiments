# d1_servo_arm/arm_control.py
# Hilfsfunktionen, um den D1-Arm aus Python zu steuern – ohne Neucompilieren.
# Nutzt die bereits gebauten Binaries aus d1_sdk/build:
#   - arm_pub               (Publisher mit --stdin)
#   - arm_zero_control      (bewährtes "Home/Zero" Kommando)
#   - get_arm_joint_angle   (liest aktuelle Gelenkwinkel)
#
# Voraussetzung:
#   export CYCLONEDDS_URI=file:///tmp/cdds.xml
#   (Dieses Skript setzt die Variable zur Sicherheit selbst erneut.)
#   LD_LIBRARY_PATH auf ~/cdds/install/lib:/usr/local/lib
#
# Benutzung (Beispiel):
#   import arm_control as ac
#   ac.torque_lock(40000)
#   ac.move_multi([-5, -15, 25, 0, 0, 10, 10])
#   ac.go_home()
#   print(ac.read_angles_once())


"""
torque_lock(level): aktiviert/erhöht die „Härte“ (0..80000). Klein starten (z. B. 15000–30000).

torque_release(): entlastet (0) – Achtung: Arm kann absinken.

go_home(): fährt in die stehende Home/Kalibrierpose (per funcode=7).

go_stow(): fährt in deine Liegepose STOW_ANGLES (Multi-Joint-Befehl).

move_single_joint(id, angle): ein Gelenk (Doku funcode=1).

move_multi([7-Winkel]): alle Gelenke gleichzeitig (Doku funcode=2).

read_angles_once(): liest aktuelle 7 Winkel (Grad).

print_compare_stow(): vergleicht Ist mit deinen STOW_ANGLES.

"""

import os
import re
import json
import time
import signal
import subprocess
import numpy as np
from pathlib import Path
import threading

from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
# ---------- Pfade/Umgebung anpassen ----------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUILD = PROJECT_ROOT / "d1_sdk" / "build"

BUILD_DIR   = os.environ.get("D1_SDK_BUILD", str(DEFAULT_BUILD))
ARM_PUB     = str(Path(BUILD_DIR) / "arm_pub")
CYCLONE_CFG = os.environ.get("CYCLONEDDS_URI", f"file://{(SCRIPT_DIR / 'cdds.xml')}")

LD_LIBS     = os.path.expanduser("~/cdds/install/lib") + ":/usr/local/lib"

def _assert_binaries():
    req = ["get_arm_joint_angle", "arm_zero_control"]  #"arm_pub",
    missing = [exe for exe in req if not (Path(BUILD_DIR)/exe).exists()]
    if missing:
        raise FileNotFoundError(
            f"Folgende Binaries fehlen in {BUILD_DIR}: {', '.join(missing)}\n"
            f"Baue sie mit:\n"
            f"  cd {DEFAULT_BUILD.parent}\n"
            f"  cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_PREFIX_PATH=$HOME/cdds/install .\n"
            f"  make -j\n"
        )
_assert_binaries()

# ---------- interne Helfer ----------
def _env():
    """Umgebungsvariablen fürs Starten der Binaries setzen."""
    e = os.environ.copy()
    e["LD_LIBRARY_PATH"] = LD_LIBS + ":" + e.get("LD_LIBRARY_PATH", "")
    e["CYCLONEDDS_URI"]  = CYCLONE_CFG
    return e

def _run_binary(exe, timeout=None):
    """Binary ohne stdin starten und auf Ende warten."""
    return subprocess.run([os.path.join(BUILD_DIR, exe)],
                          env=_env(), timeout=timeout, check=False).returncode


# ---------- I/O ----------
def read_angles_once(timeout=1.0):
    """
    Liest eine Zeile aus get_arm_joint_angle und gibt 7 floats zurück
    oder None, wenn kein Parse möglich war.
    """
    cmd = [os.path.join(BUILD_DIR, "get_arm_joint_angle")]
    p = subprocess.Popen(cmd, env=_env(),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    last = None
    try:
        while time.time() - t0 < timeout:
            line = p.stdout.readline()
            if not line:
                break
            last = line.strip()
    finally:
        try:
            p.send_signal(signal.SIGINT)
            time.sleep(0.1)
            p.terminate()
        except Exception:
            pass

    if not last:
        return None
    vals = re.findall(r"servo\d+_data:([-+]?\d+(?:\.\d+)?)", last)
    return [float(v) for v in vals] if len(vals) == 7 else None


def print_angles(seconds=2):
    """Streamt Winkel für 'seconds' Sekunden auf stdout."""
    cmd = [os.path.join(BUILD_DIR, "get_arm_joint_angle")]
    p = subprocess.Popen(cmd, env=_env(),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            line = p.stdout.readline()
            if not line:
                break
            print(line.strip())
    finally:
        try:
            p.send_signal(signal.SIGINT)
            time.sleep(0.2)
            p.terminate()
        except Exception:
            pass


# ---------- Kommandos ----------
def torque_lock(level=60000):
    """
    funcode 5: „Lock“/Dämpfung setzen (0..80000).
    Hinweise der Doku: 0 voll weiches Auskuppeln, 80000 sehr hart.
    """
    payload = {"seq":4, "address":1, "funcode":5, "data":{"mode":int(level)}}
    return subprocess.run([ARM_PUB, "--stdin"],
                          input=json.dumps(payload), text=True, env=_env()).returncode

def torque_release():
    """funcode=5 – komplett entlasten (0). Achtung: Arm kann absinken/fallen."""
    payload = {"seq":4, "address":1, "funcode":5, "data":{"mode": 0}}
    return subprocess.run([ARM_PUB, "--stdin"], input=json.dumps(payload),
                          text=True, env=_env()).returncode

def move_single_joint(joint_id, angle_deg, delay_ms=0):
    """
    funcode 1: Einzelgelenk fahren.
    joint_id: laut Doku (0..6 oder 1..7 – je nach FW; bei dir: Beispiel id=5)
    """
    payload = {"seq":4, "address":1, "funcode":1,
               "data":{"id":int(joint_id), "angle":float(angle_deg), "delay_ms":int(delay_ms)}}
    return subprocess.run([ARM_PUB, "--stdin"],
                          input=json.dumps(payload), text=True, env=_env()).returncode

### Experimental Move Multi Function where joint angles are hit simultaneously ###

def move_multi_simultaneous(angles_deg, v = 5):
    """
    angles_deg: Liste von 7 Winkeln (Grad).
    v: Geschwindigkeit in Grad/Sekunde (gemeinsam für alle Gelenke).
    Alle Gelenke sollen gleichzeitig ihre Zielwinkel erreichen.
    """
    threads = []
    current_angles = np.array(read_angles_once()) #[90, -10, 30, 45, -34, -100, 0] #
    angles_deg = np.array(angles_deg)
    print(current_angles)
    angles_delta = abs(angles_deg - current_angles)
    print (angles_delta)
    max_delta = max([abs(angle) for angle in angles_delta])
    print(max_delta)
    execution_time = np.round(max_delta / v  * 1000) # time in milliseconds to reach the target angles at speed v
    print(execution_time)
    angles_deg = angles_deg.tolist()
    print(angles_deg)
    joint_id = 0

    torque_lock(40000)
    time.sleep(0.2)

    for angle in angles_deg:
        print(joint_id, angle, execution_time)
        thread_joint = threading.Thread(target=move_single_joint, args = (joint_id, angle, execution_time))
        #time.sleep(0.1)
        threads.append(thread_joint)
        thread_joint.start()
        joint_id = joint_id + 1

    for thread in threads:
        thread.join()

### End ###

def move_multi(angles_deg, mode=1, habr=20, ply=3):
    """
    funcode 2: Multi-Joint laut Doku mit angle0..angle6.
    angles_deg: Liste von 7 Winkeln (Grad).
    mode/habr/plyLevel werden mitgeschickt.
    """
    assert len(angles_deg) == 7, "Erwarte 7 Gelenkwinkel (Grad)."
    data = {f"angle{i}": float(angles_deg[i]) for i in range(7)}
    data.update({
        "mode": int(mode),
        "habr": [int(habr)]*7,
        "plyLevel": [int(ply)]*7
    })
    payload = {"seq":4, "address":1, "funcode":2, "data": data}
    return subprocess.run([ARM_PUB, "--stdin"],
                          input=json.dumps(payload), text=True, env=_env()).returncode

def go_home():
    """
    Robustes „Home/Zero“:
      1) moderates Lock (Controller kann sauber fahren)
      2) Home über das funktionierende C++-Binary arm_zero_control
      3) Fallback: sanft Richtung Null-Pose per funcode 2
    """
    # 1) moderat sperren
    torque_lock(40000)
    time.sleep(0.2)

    # 2) bewährtes Binary aufrufen
    _run_binary("arm_zero_control", timeout=5)
    time.sleep(0.8)

    # Prüfen, ob „nahe“ Home (Toleranz anpassbar)
    angles = read_angles_once(timeout=1.0)
    if angles and all(abs(a) < 5.0 for a in angles):
        return 0

    # 3) Fallback: Richtung Null-Pose
    move_multi([0, 0, 0, 0, 0, 0, 0], mode=1)
    time.sleep(1.0)
    return 0

# ======= Vordefinierte Posen & Helfer =======

# Gemessene "Liege-/Ausgangs-Pose" aus deinem System (Grad):
STOW_ANGLES = [-9.8, -87.8, 92.3, -7.7, 0.5, 10.0, 18.0]

# (Optional) eine "stand/neutral" Pose, wenn du die definieren willst:
STAND_ANGLES = [-1.0, -88.0, 93.0, 1.0, -0.3, 0.7, 0.0]  # nahe deiner geloggten „stehend“-Werte

def _near(a, b, tol=3.0):
    return all(abs(ai - bi) <= tol for ai, bi in zip(a, b))

def move_multi_stream(angles_deg, repeats=30, hz=10, mode=1, habr=20, ply=3):
    """
    Wiederholt Multi-Joint-Command 'repeats' mal mit 'hz', damit der Befehl sicher ankommt/„hält“.
    Nutzt arm_pub --stdin --repeat --hz.
    """
    assert len(angles_deg) == 7
    data = {f"angle{i}": float(angles_deg[i]) for i in range(7)}
    data.update({"mode": int(mode),
                 "habr": [int(habr)]*7,
                 "plyLevel": [int(ply)]*7})
    payload = {"seq":4, "address":1, "funcode":2, "data": data}
    return subprocess.run(
        [ARM_PUB, "--stdin", "--repeat", str(int(repeats)), "--hz", str(int(hz))],
        input=json.dumps(payload), text=True, env=_env()
    ).returncode

def go_stow(torque=45000, verify=True):
    """
    Fährt in die definierte Park-/Liegepose (STOW_ANGLES).
    - setzt moderates Lock (damit der Controller aktiv ist)
    - streamt mehrere Kommandos, wartet kurz und prüft (optional)
    """
    torque_lock(int(torque))
    time.sleep(0.2)
    # 3s halten bei 10 Hz
    move_multi_stream(STOW_ANGLES, repeats=30, hz=10, mode=1)
    time.sleep(0.8)

    if verify:
        ang = read_angles_once(timeout=1.0)
        if not ang or not _near(ang, STOW_ANGLES, tol=5.0):
            # Nochmals nachdrücken (etwas länger/„härter“)
            torque_lock(int(max(torque, 50000)))
            move_multi_stream(STOW_ANGLES, repeats=50, hz=10, mode=1)
            time.sleep(1.0)
    return 0

def go_stand(torque=45000, verify=False):
    """
    Optional: in eine definierte „Stand-/Neutral“-Pose fahren.
    Nutzt STAND_ANGLES (anpassbar).
    """
    torque_lock(int(torque))
    time.sleep(0.2)
    move_multi_stream(STAND_ANGLES, repeats=30, hz=10, mode=1)
    time.sleep(0.8)

    if verify:
        ang = read_angles_once(timeout=1.0)
        if not ang or not _near(ang, STAND_ANGLES, tol=5.0):
            torque_lock(int(max(torque, 50000)))
            move_multi_stream(STAND_ANGLES, repeats=50, hz=10, mode=1)
            time.sleep(1.0)
    return 0

def set_stow_to_current():
    """Liest aktuelle Winkel und schreibt sie in STOW_ANGLES (im Speicher zur Laufzeit)."""
    cur = read_angles_once(timeout=1.5)
    if cur and len(cur) == 7:
        global STOW_ANGLES
        STOW_ANGLES = [round(v, 1) for v in cur]
        print("Neue STOW_ANGLES =", STOW_ANGLES)
        return STOW_ANGLES
    else:
        print("Konnte aktuelle Winkel nicht lesen.")
        return None

def print_compare_stow(tol=5.0):
    """Vergleicht Ist mit STOW_ANGLES und druckt Diff pro Gelenk."""
    cur = read_angles_once(timeout=1.5)
    if not cur:
        print("Keine aktuellen Winkel lesbar.")
        return
    diffs = [round(c - s, 1) for c, s in zip(cur, STOW_ANGLES)]
    ok = all(abs(d) <= tol for d in diffs)
    print("Ist :", [round(x,1) for x in cur])
    print("Soll:", [round(x,1) for x in STOW_ANGLES])
    print("Diff:", diffs, "(OK)" if ok else "(außerhalb Toleranz)")

def compare_angles(target_angles, tol=2.0):
    """Compare current with target angles, return True if in tolerance."""
    cur = read_angles_once(timeout=1.5)
    if not cur:
        print("Keine aktuellen Winkel lesbar.")
        return
    diffs = [round(c - s, 1) for c, s in zip(cur, target_angles)]
    ok = all(abs(d) <= tol for d in diffs)
    # print("Ist :", [round(x,1) for x in cur])
    # print("Soll:", [round(x,1) for x in target_angles])
    # print("Diff:", diffs, "(OK)" if ok else "(außerhalb Toleranz)")
    return ok

# ---------- schneller Gesamttest ----------
def quick_sanity():
    """
    1) Lock moderat
    2) kleine Testpose
    3) Home
    4) Winkel ausgeben
    """


# ---------- direkter Start (zum Ausprobieren) ----------
if __name__ == "__main__":
    quick_sanity()

# d1_servo_arm/arm_control.py
# Steuerung des Unitree D1 Arms aus Python – ohne arm_pub und ohne joint_angle_control.
# Nutzt:
#   - multiple_joint_angle_control (7 absolute Winkel, Grad)
#   - joint_enable_control         (1/0)
#   - get_arm_joint_angle
#   - arm_zero_control

import os, re, time, signal, subprocess
from pathlib import Path
from typing import List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

def _detect_build_dir() -> str:
    env = os.environ.get("D1_SDK_BUILD")
    candidates = []
    if env: candidates.append(Path(env))
    candidates += [PROJECT_ROOT / "d1_sdk" / "build",
                   PROJECT_ROOT / "d1_sdk" / "d1_sdk" / "build"]
    for p in candidates:
        if p.is_dir():
            return str(p.resolve())
    raise FileNotFoundError("Setze D1_SDK_BUILD oder baue das SDK (cmake -S . -B build; cmake --build build).")

BUILD_DIR = _detect_build_dir()

def _exe(name: str) -> str:
    p = Path(BUILD_DIR) / name
    if not p.exists():
        raise FileNotFoundError(f"Binary '{name}' nicht gefunden in {BUILD_DIR}")
    return str(p)

GET_ANGLES = _exe("get_arm_joint_angle")
ZERO_EXE   = _exe("arm_zero_control")
ENA_EXE    = _exe("joint_enable_control")
MJA_EXE    = _exe("multiple_joint_angle_control")  # <- Hauptpfad für Bewegungen

# DDS / LD
_cfg_env = os.environ.get("CYCLONEDDS_URI")
_local   = (SCRIPT_DIR / "cdds.xml")
if _cfg_env:
    CYCLONE_CFG = _cfg_env
elif _local.exists():
    CYCLONE_CFG = f"file://{_local}"
else:
    CYCLONE_CFG = ""
LD_LIBS = os.environ.get("LD_LIBRARY_PATH", "")

def _env() -> dict:
    e = os.environ.copy()
    if LD_LIBS: e["LD_LIBRARY_PATH"] = LD_LIBS
    if CYCLONE_CFG: e["CYCLONEDDS_URI"] = CYCLONE_CFG
    return e

def _run(cmd: List[str], timeout: Optional[float]=None) -> Tuple[int,str]:
    try:
        p = subprocess.run(cmd, env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout or ""
    except Exception as e:
        return 127, f"[EXCEPTION] {e}"

# ---- Telemetrie ----
def read_angles_once(timeout: float = 1.0) -> Optional[List[float]]:
    p = subprocess.Popen([GET_ANGLES], env=_env(),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0, last = time.time(), None
    try:
        while time.time() - t0 < timeout:
            line = p.stdout.readline()
            if not line: break
            last = line.strip()
    finally:
        try:
            p.send_signal(signal.SIGINT); time.sleep(0.05); p.terminate()
        except Exception:
            pass
    if not last: return None
    vals = re.findall(r"servo\d+_data:([-+]?\d+(?:\.\d+)?)", last)
    return [float(v) for v in vals] if len(vals) == 7 else None

def print_angles(seconds: float = 2.0):
    p = subprocess.Popen([GET_ANGLES], env=_env(),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            line = p.stdout.readline()
            if not line: break
            print(line.strip())
    finally:
        try:
            p.send_signal(signal.SIGINT); time.sleep(0.05); p.terminate()
        except Exception:
            pass

# ---- Enable / Disable ----
def torque_lock(level: int = 60000) -> int:  # level wird hier ignoriert
    rc, _ = _run([ENA_EXE, "1"], timeout=2.0)
    return rc

def torque_release() -> int:
    rc, _ = _run([ENA_EXE, "0"], timeout=2.0)
    return rc

# ---- Bewegung über multiple_joint_angle_control ----
def move_single_joint(joint_id: int, angle_deg: float, delay_ms: int = 0) -> int:
    # Single via Multi: aktuelle Pose holen, ein Gelenk ersetzen, alles setzen
    cur = read_angles_once(timeout=0.5) or [0.0]*7
    cur[int(joint_id)] = float(angle_deg)
    return move_multi(cur)

def move_multi(angles_deg: List[float], mode: int = 1, habr: int = 20, ply: int = 3) -> int:
    """Setzt absolute 7-Gelenk-Winkel (Grad)."""
    assert len(angles_deg) == 7, "Erwarte 7 Gelenkwinkel (Grad)."
    args = [MJA_EXE] + [str(float(a)) for a in angles_deg]
    rc, _ = _run(args, timeout=3.0)
    return rc

def move_multi_stream(angles_deg: List[float], repeats: int = 30, hz: int = 10,
                      mode: int = 1, habr: int = 20, ply: int = 3) -> int:
    """Wiederholt dieselbe Pose, um sie zu „halten“ (Simulation von --repeat/--hz)."""
    assert len(angles_deg) == 7
    period = 1.0 / max(1, int(hz))
    rc_last = 0
    for _ in range(int(repeats)):
        rc_last = move_multi(angles_deg)
        time.sleep(period)
    return rc_last

# ---- Homing & Posen ----
def go_home() -> int:
    torque_lock(); time.sleep(0.2)
    _run([ZERO_EXE], timeout=10.0); time.sleep(0.8)
    ang = read_angles_once(timeout=1.0)
    if ang and all(abs(a) < 5.0 for a in ang):
        return 0
    move_multi([0,0,0,0,0,0,0]); time.sleep(1.0)
    return 0

STOW_ANGLES  = [-9.8, -87.8, 92.3, -7.7, 0.5, 10.0, 18.0]
STAND_ANGLES = [-1.0, -88.0, 93.0,  1.0, -0.3, 0.7, 0.0]

def _near(a: List[float], b: List[float], tol: float = 3.0) -> bool:
    return all(abs(ai - bi) <= tol for ai, bi in zip(a, b))

def go_stow(torque: int = 45000, verify: bool = True) -> int:
    torque_lock(); time.sleep(0.2)
    move_multi_stream(STOW_ANGLES, repeats=30, hz=10); time.sleep(0.8)
    if verify:
        ang = read_angles_once(timeout=1.0)
        if (not ang) or (not _near(ang, STOW_ANGLES, 5.0)):
            torque_lock(); move_multi_stream(STOW_ANGLES, repeats=50, hz=10); time.sleep(1.0)
    return 0

def go_stand(torque: int = 45000, verify: bool = False) -> int:
    torque_lock(); time.sleep(0.2)
    move_multi_stream(STAND_ANGLES, repeats=30, hz=10); time.sleep(0.8)
    if verify:
        ang = read_angles_once(timeout=1.0)
        if (not ang) or (not _near(ang, STAND_ANGLES, 5.0)):
            torque_lock(); move_multi_stream(STAND_ANGLES, repeats=50, hz=10); time.sleep(1.0)
    return 0

def set_stow_to_current():
    cur = read_angles_once(timeout=1.5)
    if cur and len(cur) == 7:
        global STOW_ANGLES
        STOW_ANGLES = [round(v,1) for v in cur]
        print("Neue STOW_ANGLES =", STOW_ANGLES)
        return STOW_ANGLES
    print("Konnte aktuelle Winkel nicht lesen.")
    return None

def quick_sanity():
    print("Enable…"); torque_lock(); time.sleep(0.2)
    print("Stand…");  go_stand(verify=False); time.sleep(0.5)
    print("Home…");   go_home()
    print("Angles:"); print_angles(2.0)

if __name__ == "__main__":
    quick_sanity()
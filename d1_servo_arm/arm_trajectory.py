# arm_trajectory.py
# Trajektorie aufzeichnen & 1:1 abspielen

import sys, os, json, time, pathlib, bisect, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # damit "import arm_control" lokal klappt
import arm_control as ac

# --- optionales Ruckig (für smooth playback) ---
try:
    # Online-OTG für stetige v/a-Profile
    from ruckig import Ruckig, InputParameter, OutputParameter, Result
    _RUCKIG_OK = True
except Exception:
    _RUCKIG_OK = False

# --- Standardverzeichnis: Ordner dieses Skripts ---
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

def _resolve_to_script_dir(p: str) -> pathlib.Path:
    """Relative Pfade ins Skriptverzeichnis auflösen; absolute Pfade unverändert lassen."""
    pp = pathlib.Path(p)
    return pp if pp.is_absolute() else (SCRIPT_DIR / pp)

def _best_existing_for_play(p: str) -> pathlib.Path:
    """
    Spielt-Datei finden:
      1) exakter Pfad, wenn existent
      2) sonst: gleicher Dateiname im Skriptordner (SCRIPT_DIR)
    """
    pp = pathlib.Path(p)
    if pp.exists():
        return pp
    fallback = SCRIPT_DIR / pp.name
    return fallback if fallback.exists() else pp

def record(path, hz=15.0, warmup=0.2):
    """Nimmt Gelenkwinkel mit ~hz auf und speichert als JSON.
       WICHTIG: setzt vorher torque_release(), damit der Arm weich bewegbar ist.
    """
    # Arm weich schalten – zwingend vor der Aufnahme
    print("[REC] torque_release() – Achtung: Arm kann absinken, Umgebung sichern!")
    try:
        ac.torque_release()
        time.sleep(0.3)
    except Exception as e:
        print(f"[REC] WARNUNG: torque_release() fehlgeschlagen: {e}")

    # -> Ziel relativ zum Skriptordner; Ordner ggf. anlegen
    path = _resolve_to_script_dir(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    hz = float(hz)
    dt = 1.0 / hz
    print(f"[REC] Warmup {warmup:.1f}s …")
    time.sleep(warmup)
    print(f"[REC] Läuft @ {hz:.1f} Hz – Stop mit Ctrl-C")

    samples = []
    t0 = time.monotonic()
    try:
        while True:
            t = time.monotonic() - t0
            q = ac.read_angles_once(timeout=min(0.15, dt*0.9))
            if q and len(q) == 7:
                samples.append({"t": round(t, 4), "q": [float(x) for x in q]})
            time.sleep(max(0.0, dt - 0.005))
    except KeyboardInterrupt:
        pass

    if not samples:
        print("[REC] Keine Samples, Abbruch.")
        return

    with open(path, "w") as f:
        json.dump({"hz": hz, "samples": samples}, f, indent=2)
    print(f"[REC] Gespeichert: {path} ({len(samples)} Samples, {samples[-1]['t']:.2f}s)")

def _resample(samples, speed=1.0):
    """Resample linear auf konstantes dt (durchschnittliches dt / speed), mit sauberem clamp am Ende."""
    if len(samples) < 2:
        raise ValueError("Zu wenige Samples in der Aufnahme (mind. 2).")

    ts_raw = [s["t"] for s in samples]
    qs_raw = [s["q"] for s in samples]

    total_T = ts_raw[-1] - ts_raw[0]
    avg_dt  = total_T / max(1, len(samples)-1)
    dt_play = max(0.02, avg_dt / max(1e-6, float(speed)))  # mind. 50 Hz vermeiden — nimm 20–30ms

    t_end = ts_raw[-1]
    ts = []
    t  = 0.0
    while t < t_end:
        ts.append(round(t, 5))
        t += dt_play
    ts.append(t_end)

    resampled = []
    for t in ts:
        if t <= ts_raw[0]:
            q = qs_raw[0]
        elif t >= ts_raw[-1]:
            q = qs_raw[-1]
        else:
            j = bisect.bisect_right(ts_raw, t) - 1
            t0, t1 = ts_raw[j], ts_raw[j+1]
            a = (t - t0) / max(1e-9, (t1 - t0))
            q0, q1 = qs_raw[j], qs_raw[j+1]
            q = [ (1-a)*q0[k] + a*q1[k] for k in range(7) ]
        resampled.append({"t": t, "q": [float(x) for x in q]})
    return resampled

# ========= 1:1-Wiedergabe ohne Glättungs-/Resample-Verluste =========
def play_exact(path, lock=50000, repeat_hz=15, repeats_per_point=3, mode=0, habr=0, ply=0):
    """
    Spielt die Roh-Samples so originalgetreu wie möglich:
      - mode=0 (kleinste Glättung)
      - habr=0, ply=0 (keine zusätzlichen Filter)
      - keinerlei Winkel-Rundung
      - Original-Zeitstempel exakt einhalten
      - pro Sample mehrere Wiederholungen @ repeat_hz, damit der Controller die Pose wirklich „hält“
    """
    p = _best_existing_for_play(path)
    if not p.exists():
        raise FileNotFoundError(f"Trajectory nicht gefunden: {path}\nAuch geprüft: {SCRIPT_DIR / pathlib.Path(path).name}")

    with open(p, "r") as f:
        data = json.load(f)
    samples = data.get("samples", [])
    if len(samples) < 2:
        print("[PLAY-EXACT] Aufnahme zu kurz.")
        return

    # Vorbereitung
    ac.torque_lock(int(lock))
    time.sleep(0.2)

    # Zeitplan relativ zu jetzt: t_schedule[i] = t0 + samples[i]["t"]
    t0 = time.monotonic()

    for i, s in enumerate(samples):
        target_time = t0 + float(s["t"])

        # Pose s["q"] mehrfach streamen, damit sie stabil anliegt
        ac.move_multi_stream(s["q"], repeats=int(repeats_per_point), hz=int(repeat_hz),
                             mode=int(mode), habr=int(habr), ply=int(ply))

        # Bis zur nächsten Original-Zeitmarke warten (falls noch Zeit)
        now = time.monotonic()
        sleep_left = target_time - now
        if i + 1 < len(samples):
            next_target = t0 + float(samples[i+1]["t"])
            sleep_left = max(0.0, next_target - time.monotonic())
            if sleep_left > 0:
                time.sleep(sleep_left)

    time.sleep(0.3)
    print(f"[PLAY-EXACT] Ende-Ist:", [round(x,1) for x in (ac.read_angles_once() or [])])

# ========= „normale“ Wiedergabe (resampled) – kann glätten =========
def play(path, speed=1.0, lock=45000, hold_each=0.0):
    """
    Resampled Wiedergabe (für glatte, aber nicht 1:1) – lasse für 1:1 besser play_exact laufen.
    """
    p = _best_existing_for_play(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Trajectory nicht gefunden: {path}\n"
            f"Auch geprüft: {SCRIPT_DIR / pathlib.Path(path).name}"
        )

    with open(p, "r") as f:
        data = json.load(f)
    print(f"[PLAY] Quelle: {p}")

    samples = data["samples"]
    if len(samples) < 2:
        print("[PLAY] Aufnahme zu kurz.")
        return

    ac.torque_lock(int(lock))
    time.sleep(0.2)

    resampled = _resample(samples, speed=speed)

    ts = [s["t"] for s in resampled]
    if len(ts) >= 2:
        step_dt = max(0.02, (ts[-1] - ts[0]) / max(1, len(ts)-1))
    else:
        step_dt = 0.05

    t_print = time.monotonic()
    for s in resampled:
        q = s["q"]                 # NICHT runden
        ac.move_multi_stream(q, repeats=5, hz=15, mode=0, habr=0, ply=0)  # direkter & gehalten
        now = time.monotonic()
        if now - t_print > 0.5:
            print(f"[PLAY] t={s['t']:.2f}s  q={[round(x,1) for x in q]}")
            t_print = now
        time.sleep(step_dt + max(0.0, hold_each))

    time.sleep(0.3)
    print(f"[PLAY] Ende-Ist:", [round(x,1) for x in (ac.read_angles_once() or [])])

# ========= SMOOTH Wiedergabe mit Ruckig (jerk-limitiert, Online-OTG) =========
def _default_limits(dofs=7):
    """
    Konservative Default-Limits. Bitte bei Bedarf je Gelenk anpassen (rad, rad/s, rad/s^2, rad/s^3).
    Diese Werte sind absichtlich moderat gewählt und sollten sicher unter Herstellergrenzen liegen.
    """
    v = [1.5] * dofs      # rad/s
    a = [3.0] * dofs      # rad/s^2
    j = [20.0] * dofs     # rad/s^3
    return v, a, j

def _decimate_waypoints(samples, min_dt=0.04, min_delta=0.01):
    """
    Aus der Aufnahme schlanke Wegpunkte extrahieren:
      - min_dt: mind. Zeitabstand zum letzten gewählten Punkt
      - min_delta: mind. Änderung (max-norm über 7 Gelenke) in rad
    Dadurch vermeiden wir "Stop-and-Go" zwischen dicht beieinanderliegenden Punkten.
    """
    if not samples:
        return []
    keep = [samples[0]]
    last_t = samples[0]["t"]
    last_q = samples[0]["q"]
    for s in samples[1:]:
        if (s["t"] - last_t) < float(min_dt):
            # nur nehmen, wenn wirklich nennenswerte Änderung
            dq = max(abs(sq - lq) for sq, lq in zip(s["q"], last_q))
            if dq < float(min_delta):
                continue
        keep.append(s)
        last_t = s["t"]
        last_q = s["q"]
    if keep[-1] is not samples[-1]:
        keep.append(samples[-1])
    return keep

def _detect_units_and_limits(q0, dofs=7):
    """
    Erkennt Grad vs. Rad grob an der Amplitude und gibt passende Limits zurück.
    Returns: (unit_str, vmax, amax, jmax) — alle in gleichen Einheiten wie q.
    """
    # einfache Heuristik: wenn irgendein |q| > ~6.5 -> Grad
    if any(abs(x) > 6.5 for x in q0):
        unit = "deg"
        # konservative Limits in Grad
        vmax = [80.0] * dofs      # deg/s
        amax = [300.0] * dofs     # deg/s^2
        jmax = [4000.0] * dofs    # deg/s^3
    else:
        unit = "rad"
        vmax = [1.4] * dofs       # rad/s
        amax = [2.5] * dofs       # rad/s^2
        jmax = [30.0] * dofs      # rad/s^3
    return unit, vmax, amax, jmax


def play_smooth(path, speed=1.0, lock=45000, control_hz=100, vmax=None, amax=None, jmax=None, mode=0, habr=0, ply=0):
    """
    Jerk-limitierte, stetige Wiedergabe via Ruckig (Online-OTG).
    - speed: skaliert die Limits (v * speed, a * speed^2, j * speed^3) -> schneller/langsamer
    - control_hz: Controller-Updatefrequenz (empfohlen 80–200 Hz)
    - vmax/amax/jmax: optionale Listen mit 7 Einträgen (pro Gelenk). Sonst Default.
    """
    if not _RUCKIG_OK:
        raise RuntimeError("Ruckig ist nicht installiert. Bitte `pip install ruckig` ausführen.")

    p = _best_existing_for_play(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Trajectory nicht gefunden: {path}\n"
            f"Auch geprüft: {SCRIPT_DIR / pathlib.Path(path).name}"
        )

    with open(p, "r") as f:
        data = json.load(f)
    samples = data.get("samples", [])
    if len(samples) < 2:
        print("[PLAY-SMOOTH] Aufnahme zu kurz.")
        return

    dofs = 7
    q0_recorded = samples[0]["q"]

    # Einheiten & Limits (autodetect, falls nicht vorgegeben)
    unit, vmax_auto, amax_auto, jmax_auto = _detect_units_and_limits(q0_recorded, dofs)
    if vmax is None: vmax = vmax_auto
    if amax is None: amax = amax_auto
    if jmax is None: jmax = jmax_auto

    # speed-Skalierung (Zeit ~ 1/speed)
    s = float(max(1e-3, speed))
    vmax_s = [v * s for v in vmax]
    amax_s = [a * (s ** 2) for a in amax]
    jmax_s = [j * (s ** 3) for j in jmax]

    waypoints = _decimate_waypoints(samples, min_dt=1.0 / float(control_hz) * 3.0, min_delta=0.01)

    print(
        f"[PLAY-SMOOTH] Quelle: {p}  |  Wegpunkte: {len(waypoints)}  |  control_hz={control_hz}  |  speed={speed:.2f}  |  units={unit}")

    ac.torque_lock(int(lock))
    time.sleep(0.2)

    control_dt = 1.0 / float(control_hz)
    otg = Ruckig(dofs, control_dt)
    inp = InputParameter(dofs)
    out = OutputParameter(dofs)

    # Startzustand
    inp.current_position = waypoints[0]["q"][:]
    inp.current_velocity = [0.0] * dofs
    inp.current_acceleration = [0.0] * dofs
    inp.max_velocity = vmax_s
    inp.max_acceleration = amax_s
    inp.max_jerk = jmax_s

    # Sauberes Streaming (Repeats leicht >1; Hz deckungsgleich mit control_hz)
    stream_hz = int(max(20, min(500, control_hz)))
    stream_repeats = 2

    t_print = time.monotonic()
    for idx in range(1, len(waypoints)):
        inp.target_position = waypoints[idx]["q"][:]
        inp.target_velocity = [0.0] * dofs
        inp.target_acceleration = [0.0] * dofs

        while True:
            res = otg.update(inp, out)

            # Pose streamen
            ac.move_multi_stream(out.new_position, repeats=stream_repeats, hz=stream_hz,
                                 mode=int(mode), habr=int(habr), ply=int(ply))

            # Nächsten Schritt vorbereiten
            inp.current_position = out.new_position
            inp.current_velocity = out.new_velocity
            inp.current_acceleration = out.new_acceleration

            # === Echtzeit-Takt ===
            time.sleep(control_dt)

            # Version-kompatibles Finish-Handling
            finished_enum = getattr(Result, 'Finished', None)
            goal_enum = getattr(Result, 'GoalReached', None)
            if (finished_enum is not None and res == finished_enum) or (goal_enum is not None and res == goal_enum):
                break
            if res not in (getattr(Result, 'Working', res), getattr(Result, 'Busy', res)):
                print(f"[PLAY-SMOOTH] OTG-Status unerwartet: {res} – Segment wird beendet.")
                break

            # Log-Throttle
            now = time.monotonic()
            if now - t_print > 0.5:
                dbg = [round(x, 2) for x in out.new_position]
                print(f"[PLAY-SMOOTH] Seg {idx}/{len(waypoints) - 1}  q≈{dbg}")
                t_print = now

    time.sleep(0.3)
    print(f"[PLAY-SMOOTH] Ende-Ist:", [round(x, 1) for x in (ac.read_angles_once() or [])])

# ========= CLI =========
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage:\n"
              f"  python {sys.argv[0]} record <out.json> [hz]\n"
              f"  python {sys.argv[0]} play <in.json> [speed] [lock]\n"
              f"  python {sys.argv[0]} play_exact <in.json> [lock] [repeat_hz] [repeats_per_point]\n"
              f"  python {sys.argv[0]} play_smooth <in.json> [speed] [lock] [control_hz]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "record":
        if len(sys.argv) < 3:
            print("record: Pfad fehlt")
            sys.exit(1)
        out = sys.argv[2]
        hz  = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
        record(out, hz=hz)

    elif cmd == "play":
        if len(sys.argv) < 3:
            print("play: Pfad fehlt")
            sys.exit(1)
        path  = sys.argv[2]
        speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        lock  = int(sys.argv[4])   if len(sys.argv) > 4 else 45000
        play(path, speed=speed, lock=lock)

    elif cmd == "play_exact":
        if len(sys.argv) < 3:
            print("play_exact: Pfad fehlt")
            sys.exit(1)
        path   = sys.argv[2]
        lock   = int(sys.argv[3]) if len(sys.argv) > 3 else 50000
        rhz    = int(sys.argv[4]) if len(sys.argv) > 4 else 15
        rpt    = int(sys.argv[5]) if len(sys.argv) > 5 else 3
        play_exact(path, lock=lock, repeat_hz=rhz, repeats_per_point=rpt, mode=0, habr=0, ply=0)

    elif cmd == "play_smooth":
        if len(sys.argv) < 3:
            print("play_smooth: Pfad fehlt")
            sys.exit(1)
        path  = sys.argv[2]
        speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        lock  = int(sys.argv[4])   if len(sys.argv) > 4 else 45000
        chz   = int(sys.argv[5])   if len(sys.argv) > 5 else 100
        play_smooth(path, speed=speed, lock=lock, control_hz=chz)

    else:
        print("Unbekannter Befehl (record|play|play_exact|play_smooth).")
        sys.exit(1)

# Ausführen Beispiele:
#   python3 arm_trajectory.py record pick_and_place.json 15
#   python3 arm_trajectory.py play_exact pick_and_place.json
#   python3 arm_trajectory.py play pick_and_place.json 1.0 45000
#   python3 arm_trajectory.py play_smooth pick_and_place.json 1.0 45000 120

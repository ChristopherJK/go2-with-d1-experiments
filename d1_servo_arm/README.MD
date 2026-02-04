# D1 Servo-Arm
Doku: https://support.unitree.com/home/en/developer/D1Arm_services
D1 SDK: https://unitree-firmware.oss-cn-hangzhou.aliyuncs.com/tool/d1_sdk.zip (Needs to be installed after unitree_sdk)


# Unitree **D1 Servo Arm** – Schnellstart (SDK & Services, ohne ROS)  
Steuerung über **Unitree SDK2** (DDS) + D1-Services

---

## Ziel
- **Unitree SDK2** (C++ & Python) lokal installieren/kompilieren.
- **CycloneDDS** konfigurieren & auf das richtige LAN-Interface pinnen.
- **D1-Arm-Services** (DDS) auffinden und erste Befehle testen (Home, Joints, Greifer).
- Optional: Hinweise zur ROS 2-Nutzung.

> Quelle/Bezug: Offizielle Unitree-Doku zu DDS/Services & D1-Arm ("D1Arm_services"), plus SDK2/Quick Start & Payload-Montagehinweise.

---

## Voraussetzungen
**Getestete/empfohlene Umgebungen**
- Ubuntu **20.04/22.04**
- Admin-Rechte für Paketinstallation
- (Empfohlen) Python 3 **venv**

**Benötigte Pakete**
```bash
sudo apt update
sudo apt install -y git build-essential cmake g++ \
  libyaml-cpp-dev libeigen3-dev libboost-all-dev libspdlog-dev libfmt-dev \
  cyclonedds-tools libddsc0t64
```

**Python (für SDK2-Python)**
```bash
python3 -m venv .venv # Venv erstellen falls nicht schon gemacht
source .venv/bin/activate
pip install --upgrade pip
pip install cyclonedds
```

---

## Netzwerk-Interface ermitteln (Ubuntu)
Ziel: Das Interface finden, das im **gleichen Subnetz** wie Go2/D1 liegt (z. B. `192.168.123.x`).

```bash
ip -br addr
ip route get <GO2_ODER_D1_IP>
```
Beispielausgabe zeigt `dev <INTERFACE_NAME> ...` dieses Interface unten in der DDS-Config verwenden.

---

## CycloneDDS konfigurieren
Im **Projekt-Root** (`~/PycharmProjects/go2_setup/`) Datei **`cyclonedds.xml`** anlegen:
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS>
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress><INTERFACE_NAME></NetworkInterfaceAddress>
      <AllowMulticast>true</AllowMulticast>
    </General>
  </Domain>
</CycloneDDS>
```
Konfiguration im jeweiligen Terminal aktivieren:
```bash
export CYCLONEDDS_URI=file://$PWD/cyclonedds.xml
```
> Hinweis: Die Variable ist "deprecated", für diesen Schnellstart aber ausreichend.

---

## 1) SDK2 (C++) ins Projekt klonen & bauen
Wir legen Drittanbieter-Code unter `third_party/` ab.

```bash
cd ~/PycharmProjects/go2_setup
mkdir -p third_party && cd third_party
git clone https://github.com/unitreerobotics/unitree_sdk2.git
cd unitree_sdk2
mkdir -p build && cd build
cmake ..
make -j"$(nproc)"
```
> Das C++-SDK stellt die DDS-Kommunikation & Beispielprogramme bereit.

---

## 2) (Optional, empfohlen) SDK2 **Python** installieren
Das Python-Interface spiegelt die C++-API und bringt Beispiele mit.

```bash
cd ~/PycharmProjects/go2_setup/third_party
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
cd unitree_sdk2_python
# im aktivierten venv:
pip install -e .
```

---

## 4) D1-Services (DDS) sichtbar machen
Mit gesetztem `CYCLONEDDS_URI` prüfen:
```bash
ddsls -a | grep -i -E "arm|servo|d1|unitree|payload" || true
```
Erwartung: DDS-Entities/Topics/Services des Go2 bzw. des D1 erscheinen.

Wenn **nichts** gelistet wird:
- WLAN aus, nur LAN aktiv; `CYCLONEDDS_URI` prüfen; neues Terminal testen.
- Netz im selben Subnetz? IPs prüfen (`ip -br addr`).

---

## 5) Erste Steuerung ohne ROS (SDK2-Python Beispiele)
Die genauen Service-/Topic-Namen können je nach Firmware variieren. Vorgehen:

1. **Themen/Services ermitteln**
   ```bash
   ddsls -a > dds_inventory.txt
   # Sucht z. B. nach Home/Enable/Joint/Gripper Services
   grep -i -E "home|enable|joint|grip|arm" dds_inventory.txt
   ```

2. **Beispielskripte starten**
   ```bash
   cd ~/PycharmProjects/go2_setup/third_party/unitree_sdk2_python/example
   # Beispiele variieren; prüfe README/Example-Ordner
   python3 <ein_beispielscript.py>
   ```

3. **Eigenes Minimalbeispiel (Service-Call, Pseudocode)**
   ```python
   #!/usr/bin/env python3
   from unitree_sdk2 import dds
   # Namen aus ddsls übernehmen:
   SERVICE_NAME = "<arm_service_name>"  # z. B. Home/EnableTorque/MoveJ/Gripper
   cli = dds.ServiceClient(SERVICE_NAME)
   req = {"...": "parameter je nach service"}
   print(cli.call(req))
   ```

> Tipp: Für wiederkehrende Kommandos (Home, Torque-Enable, Joint-Ziele, Greifer auf/zu) zunächst trocken mit sehr kleinen Werten testen.

---

## Troubleshooting (kurz)
- **Keine DDS-Entities**: WLAN aus, nur LAN; `CYCLONEDDS_URI` neu setzen; anderes Terminal testen.
- **Beispiele finden den Arm nicht**: Verkabelung/24 V prüfen; `ddsls -a` ausführen und exakte Namen übernehmen.
- **Build-Fehler SDK2**: CMake/Dev-Pakete wie oben installieren; `cmake ..` erneut ausführen.
- **ROS 2 nötig?** Erst SDK2 ohne ROS testen, danach ROS 2 gemäß Unitree-Leitfaden aufsetzen.

---

## Referenzen (Auszug)
- Unitree **DDS Services Interface** (SDK2, QoS, ROS 2): https://support.unitree.com/home/en/developer/DDS_services
- Unitree **Go2 SDK Quick Start** (SDK2 Setup): https://support.unitree.com/home/en/developer/Quick_start
- Unitree **Payload** (Montagehinweise): https://support.unitree.com/home/en/developer/Payload
- Unitree **D1 Arm Services** (spezifische Service-Doku): https://support.unitree.com/home/en/developer/D1Arm_services
- Repos: https://github.com/unitreerobotics/unitree_sdk2  |  https://github.com/unitreerobotics/unitree_sdk2_python
```

``` 
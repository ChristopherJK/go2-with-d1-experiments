<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

# Experiments with go2 quadruped and d1 robotic arm

[![Product Name Screen Shot][product-screenshot]]

Here's a blank template to get started. To avoid retyping too much info, do a search and replace with your text editor for the following: `github_username`, `repo_name`, `twitter_handle`, `linkedin_username`, `email_client`, `email`, `project_title`, `project_description`, `project_license`

<p align="right">(<a href="#readme-top">back to top</a>)</p>


Source code of go2 and d1 robot arm movements from Forschungsseminar project at TH Cologne.

In order to reproduce the experiments from the paper, you first need to install the required libraries and sdk´s, which is described in the upcoming sections. Then in the "Robot movements" folder you will find the code used to move the d1 arm, the go2 and for the whole pick and place movement of the efficency section.

---

## Ressources

* **Unitree Website:**
  [https://www.unitree.com/go2](https://www.unitree.com/go2)

* **Unitree SDK Documentation:**
  [https://support.unitree.com/home/en/developer](https://support.unitree.com/home/en/developer)


---

## Unitree Python SDK Installation
Installation and instructions: [unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python)

## Unitree SDK

Download the package: [unitree_sdk2](https://github.com/unitreerobotics/unitree_sdk2) 

Installation Guide: https://support.unitree.com/home/en/developer/Quick_start


---

## Establish Connection to Go2

### **Ethernet**

**Go2-IP (Link-Local):** `192.168.123.161`

#### Via Ethernet (Linux/TH-Computer)

1. **Settings → Network → Ethernet**
2. Section **IPv4** → **Method: Manual**
3. Insert:
   * **Address:** `192.168.123.222`
   * **Netmask:** `255.255.0.0` (=/16)
   * **Gateway:** *leer lassen*
4. (Optional) Sectoion **IPv6** → **Ignor**
5. **Save**

**Notes**
* Link-Local works **without DHCP**; use only **directly** on the device.

* If it doesn't work: briefly disconnect/disable other network connections, then reconnect.

* Firewalls/browser plugins can cause interference → try temporarily disabling them.

---

# D1 Servo Arm
Documentation: https://support.unitree.com/home/en/developer/D1Arm_services
D1 SDK: In the repository in the folder: d1_sdk. Install with cmake.

# Unitree **D1 Servo Arm** – Quick Start (SDK & Services, without ROS)
Control via **Unitree SDK2** (DDS) + D1 Services

---

## Goal
- Install/compile **Unitree SDK2** (C++ & Python) locally.

- Configure **CycloneDDS** and assign it to the correct LAN interface.

- Locate **D1 Arm Services** (DDS) and test initial commands (Home, Joints, Gripper).

- Optional: Notes on using ROS 2.

> Source/Reference: Official Unitree documentation on DDS/Services & D1 Arm ("D1Arm_services"), plus SDK2/Quick Start & Payload assembly instructions.

---

## Prerequisites
**Tested/Recommended Environments**

- Ubuntu **20.04/22.04**

- Administrator rights for package installation
- (Recommended) Python 3 **venv**

**Required Packages**
```bash

sudo apt update

sudo apt install -y git build-essential cmake g++ \
libyaml-cpp-dev libeigen3-dev libboost-all-dev libspdlog-dev libfmt-dev \
cyclonedds-tools libddsc0t64
```

**Python (for SDK2 Python)**
```bash

python3 -m venv .venv # Create Venv if not already done

source .venv/bin/activate
pip install --upgrade pip
pip install cyclonedds
```

---

## Determine the network interface (Ubuntu)

Goal: Find the interface that is on the **same subnet** as Go2/D1 (e.g., `192.168.123.x`).

```bash
`ip -br addr`
`ip route get <GO2_OR_D1_IP>`

```
Example output shows `dev <INTERFACE_NAME> ...` using this interface in the DDS configuration below.

---

## Configure CycloneDDS
Create the file **cyclonedds.xml** in the **project root** (`~/go2-with-d1-experiments/`):

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
Activate the configuration in the respective terminal:

```bash
export CYCLONEDDS_URI=file://$PWD/cyclonedds.xml

```
> Note: This variable is deprecated, but sufficient for this quick start.

---

## 1) Clone and build SDK2 (C++) into your project

We place third-party code in `third_party/`.

```bash

cd ~/PycharmProjects/go2_setup
mkdir -p third_party && cd third_party
git clone https://github.com/unitreerobotics/unitree_sdk2.git
cd unitree_sdk2
mkdir -p build && cd build
cmake ..

make -j"$(nproc)"
```
> The C++ SDK provides DDS communication and example programs.

---

## 2) (Optional, recommended) Install SDK2 **Python**
The Python interface mirrors the C++ API and includes examples.

```bash

cd ~/PycharmProjects/go2_setup/third_party
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git

cd unitree_sdk2_python
# in the active virtual machine:

pip install -e .

```

---

## 4) Make D1 Services (DDS) Visible
Check with `CYCLONEDDS_URI` set:

```bash

ddsls -a | grep -i -E "arm|servo|d1|unitree|payload" || true

```
Expectation: DDS entities/topics/services of the Go2 or D1 should appear.

If **nothing** is listed:

- Wi-Fi off, only LAN active; check `CYCLONEDDS_URI`; try a new terminal.

- Network on the same subnet? Check IPs (`ip -br addr`).

---

## Troubleshooting (brief)

- **No DDS entities**: Disable Wi-Fi, use LAN only; reset `CYCLONEDDS_URI`; try a different terminal. Disable VPN and firewall.

- **Examples can't find the arm**: Check cabling/24V; run `ddsls -a` and use the exact names.

- **SDK2 build error**: Install CMake/Dev packages as above; run `cmake ..` again.

- **ROS 2 required?** First test SDK2 without ROS, then install ROS 2 according to the Unitree guide.

---

## References (Excerpt)

- Unitree **DDS Services Interface** (SDK2, QoS, ROS 2): https://support.unitree.com/home/en/developer/DDS_services

- Unitree **Go2 SDK Quick Start** (SDK2 Setup): https://support.unitree.com/home/en/developer/Quick_start

- Unitree **Payload** (Installation Instructions): https://support.unitree.com/home/en/developer/Payload

- Unitree **D1 Arm Services** (Specific Service Documentation): https://support.unitree.com/home/en/developer/D1Arm_services

- Repositories: https://github.com/unitreerobotics/unitree_sdk2 | https://github.com/unitreerobotics/unitree_sdk2_python

#include <iostream>
#include <sstream>
#include <vector>
#include <string>
#include <stdexcept>
#include <unitree/robot/channel/channel_publisher.hpp>
#include "msg/ArmString_.hpp"

using namespace unitree::robot;

#define TOPIC "rt/arm_Command"

// JSON für funcode=2 (Gelenk-Positionsbefehl) bauen
static std::string build_json(const std::vector<double>& angles_deg, double duration_s)
{
    std::ostringstream os;
    os << "{\"seq\":4,\"address\":1,\"funcode\":2,";

    os << "\"angle\":[";
    for (size_t i=0; i<angles_deg.size(); ++i) { if (i) os << ","; os << angles_deg[i]; }
    os << "],";

    os << "\"duration\":[";
    for (size_t i=0; i<angles_deg.size(); ++i) { if (i) os << ","; os << duration_s; }
    os << "],";

    os << "\"habr\":[";
    for (size_t i=0; i<angles_deg.size(); ++i) { if (i) os << ","; os << 20; }
    os << "],";

    os << "\"plyLevel\":[";
    for (size_t i=0; i<angles_deg.size(); ++i) { if (i) os << ","; os << 3; }
    os << "]}";

    return os.str();
}

/*
 Aufruf:
   ./arm_move_demo a0 a1 a2 a3 a4 a5 a6 [duration_s]
 - a0..a6 in Grad (7 DOF)
 - duration_s in Sekunden (optional, Default 2.0)
*/
int main(int argc, char** argv)
{
    if (argc != 8 && argc != 9) {
        std::cerr << "Usage: " << argv[0] << " a0 a1 a2 a3 a4 a5 a6 [duration_s]\n";
        return 1;
    }

    std::vector<double> angles(7, 0.0);
    for (int i = 0; i < 7; ++i) {
        angles[i] = std::stod(argv[i + 1]);
    }

    double duration = 2.0;
    if (argc == 9) {
        duration = std::stod(argv[8]);
    }

    try {
        // Wenn du die NIC fest pinnen willst, nimm "enp129s0" wie in arm_zero_control:
        ChannelFactory::Instance()->Init(0, "enp129s0");
        // (alternativ "" für Autoauswahl, wenn CYCLONEDDS_URI sauber gesetzt ist)

        unitree_arm::msg::dds_::ArmString_ msg{};
        msg.data_() = build_json(angles, duration);

        ChannelPublisher<unitree_arm::msg::dds_::ArmString_> pub(TOPIC);
        pub.InitChannel();
        pub.Write(msg);

        std::cerr << "Sent joint command (funcode=2), duration=" << duration << "s\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[arm_move_demo] Exception: " << e.what() << "\n";
        return 2;
    }
}

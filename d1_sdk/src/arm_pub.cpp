#include <iostream>
#include <string>
#include <unitree/robot/channel/channel_publisher.hpp>
#include "msg/ArmString_.hpp"

using unitree::robot::ChannelFactory;
using unitree::robot::ChannelPublisher;

int main(int argc, char** argv) {
    // optional: Interface per ENV oder Param; hier leer lassen -> SDK/CycloneDDS-Config nutzen
    ChannelFactory::Instance()->Init(0, "");  // "" = nimm CycloneDDS-Config/Default

    ChannelPublisher<unitree_arm::msg::dds_::ArmString_> pub("rt/arm_Command");
    pub.InitChannel();

    // Lese eine JSON-Zeile von stdin
    std::string json;
    if (!std::getline(std::cin, json)) return 1;

    unitree_arm::msg::dds_::ArmString_ msg{};
    msg.data_() = json;
    pub.Write(msg);
    return 0;
}
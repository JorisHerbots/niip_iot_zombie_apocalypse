import sys

# Introduce new paths (This makes us developers have less of a headache)
sys.path.append("/flash/sensor_core")
sys.path.append("/flash/sensor_modules")
sys.path.append("/flash/sensor_modules/lib/")
sys.path.append("/flash/sensor_modules/lib/sensors/")
sys.path.append("/flash/network_core")
sys.path.append("/flash/servers")
sys.path.append("/flash/datastore")
sys.path.append("/flash/utilities")

# Imports
import sdhandler
import logging
from network import WLAN, LoRa
import device
import pycom
from wifi import WifiManager, WIFIMODI
from loramesh import LORAMESHMODI
from volatileconfiguration import VolatileConfiguration as Config
import uos
from configurationWebserver import InputManager
from system import System
from exceptions import Exceptions

# Setup global logger
logging.basicConfig(level=logging.DEBUG)

# Check for SD card availability
try:
    sdhandler.mount_device()
except sdhandler.SdNotAvailable:
    logging.getLogger("boot").warning("SD card not available. No logging to SD will be performed.")

# Prevent default WIFI from spawning, we want to control this ourselves
pycom.wifi_on_boot(False)

# Prevent the hardware to grab RGB control, we also want to control this for status information
pycom.heartbeat(False)

# Default configuration -> Saved in the global volatile configuration
try:
    Config.load_configuration_from_datastore("global")
    logging.getLogger("boot").info("Loaded 'global' configuration | {}".format(Config.get_full_configuration()))
except:
    logging.getLogger("boot").warning("No previous 'global' configuration save was found. Booting with default values.")

# Device Configuration
Config.set("device_trust_key", None, True, False) # Trust key for signing - Will be set by a tamper detection in system
Config.set("device_is_sensor", False, True, True) # TODO MANNU CODE
Config.set("device_is_router", True, True, True) # Is this device a router
Config.set("device_is_gateway", False, True, False) # Is this device a gateway
Config.set("device_position", None, True, False) # Device location

# WiFi Configuration
Config.set("wifi_mode", WIFIMODI.OFF, True, False) # Wifi Mode
Config.set("sta_ssid", None, True, False) # Station static - SSID
Config.set("sta_password", None, True, False) # Station static - Password
Config.set("sta_static_ip", "192.168.0.50", True, False) # Station static IP - IP
Config.set("sta_static_mask", "255.255.255.0", True, False) # Station static IP - Mask
Config.set("sta_static_gateway", "192.168.0.1", True, False) # Station static IP - Gateway
Config.set("sta_static_dns", "0.0.0.0", True, False) # Station static IP - DNS
Config.set("ap_static_ip", "10.0.0.1", True, False) # Access point static IP - IP
Config.set("ap_static_mask", "255.255.255.0", True, False) # Access point static IP - Mask
Config.set("ap_static_gateway", "0.0.0.0", True, False) # Access point static IP - Gateway
Config.set("ap_static_dns", "0.0.0.0", True, False) # Access point static IP - DNS

# LoRa Configuration
Config.set("lora_mode", LORAMESHMODI.OFF, True, False) # Lora mesh Mode
Config.set("lora_seq_num", int.from_bytes(uos.urandom(1), "big"), True, False) # Lora zombiegram packet sequence numbers
Config.set("lora_tampered_flag", False, True, False) # Lora zombiegram tampered flag
Config.set("lora_maintenance_flag", False, True, False) # Lora zombiegram maintance flag

# LoRa gateway configuration
Config.set("gateway_webhook_1", "", True, False) # Gateway hook 1
Config.set("gateway_webhook_2", "", True, False) # Gateway hook 2
Config.set("gateway_webhook_3", "", True, False) # Gateway hook 3

# User configuration options
InputManager.add_input("device_trust_key", str, "", "Device Options", "Device trust key", True)
InputManager.add_options("lora_tampered_flag", {"On":True, "Off":False}, False, "Device Options", "Device tampered flag (included in all Zombiegrams)")
InputManager.add_options("lora_maintenance_flag", {"Required":True, "Not Required":False}, False, "Device Options", "Does this device need maintenance?")
InputManager.add_options("device_is_router", {"Yes":True, "No":False}, False, "Device Options", "Is this device supposed to act as a router?")
InputManager.add_options("device_is_sensor", {"Yes":True, "No":False}, False, "Device Options", "Is this device a sensor?")
InputManager.add_input("gateway_webhook_1", str, "", "Gateway", "Webhook URL (http including) the device should forward messages to. Leave empty for none.")
InputManager.add_input("gateway_webhook_2", str, "", "Gateway", "Webhook URL (http including) the device should forward messages to. Leave empty for none.")
InputManager.add_input("gateway_webhook_3", str, "", "Gateway", "Webhook URL (http including) the device should forward messages to. Leave empty for none.")
InputManager.add_input("sta_ssid", str, "", "Wifi", "Station SSID to which the device should connect if put in station mode")
InputManager.add_input("sta_password", str, "", "Wifi", "Password for SSID to which the device should connect if put in station mode")
InputManager.add_input("sta_static_ip", str, "", "Wifi", "Station static IPv4")
InputManager.add_input("sta_static_mask", str, "", "Wifi", "Station mask (in IPv4 format)")
InputManager.add_input("sta_static_gateway", str, "", "Wifi", "Station gateway IP")
InputManager.add_input("ap_static_ip", str, "", "Wifi", "Access point static IPv4")
InputManager.add_input("ap_static_mask", str, "", "Wifi", "Access point mask (in IPv4 format)")
InputManager.add_input("ap_static_gateway", str, "", "Wifi", "Access point gateway IP")

InputManager.set_category_priority("Device Options", 50)
InputManager.set_category_priority("Gateway", 55)
InputManager.set_category_priority("Wifi", 60)

def p(): pass

try:
    # system = System()
    # system.configButton.longActiveTime = 3
    # system.configButton.longActiveCallback = p
    # InputManager.set_hardware_controller(system)
    # system.notifyNewConfiguration() # notify that a new configuration has been loaded (this call starts the connected sensor)
    # logging.getLogger("boot").debug("System properties at boot | Is sleep wake [{}] | Battery level [{}] | Connected Sensor ID [{}] | Tampered status [{}] | GPS Coordinates [{}]".format(system.isSleepWake, system.batteryLevel, system.sensorID, system.tempered, system.coordinates))
    # logging.getLogger("boot").info("System hardware configuration set")
    pass
except Exception as e:
    logging.getLogger("boot").error("Setting up hardware failed! | Reason [{}]".format(str(e)))

lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868, bandwidth=LoRa.BW_125KHZ, sf=7)
WifiManager.apply_settings()
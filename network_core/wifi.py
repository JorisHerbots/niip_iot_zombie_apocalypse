from network import WLAN
import device
import machine
from volatileconfiguration import VolatileConfiguration
import enum
import logging
import time

##################
# WIFI MODI ENUM #
##################

WIFIMODI = enum.create_enum(OFF=(WLAN.AP+WLAN.STA+WLAN.STA_AP), AP=WLAN.AP, STA=WLAN.STA, STA_AP=WLAN.STA_AP) # WLAN does not have negative values for their modi


######################
# WiFi Manager Class #
######################

class WifiManager:
    _wlan = None

    @staticmethod
    def _apply_interface_configurations(cm):
        """Apply volatile configuration options to the available WiFi chip interfaces
        
        :param cm: provided volatile configuration
        :type cm: VolatileConfiguration
        """
        # ID 0 = STA interface
        WifiManager._wlan.ifconfig(id=0, config=(cm.get("sta_static_ip", "192.168.0.50"),
            cm.get("sta_static_mask", "255.255.255.0"),
            cm.get("sta_static_gateway", "192.168.0.1"),
            cm.get("sta_static_dns", "0.0.0.0")))

        # ID 1 = AP interface
        WifiManager._wlan.ifconfig(id=1, config=(cm.get("ap_static_ip", "10.0.0.1"),
            cm.get("ap_static_mask", "255.255.255.0"),
            cm.get("ap_static_gateway", "0.0.0.0"),
            cm.get("ap_static_dns", "0.0.0.0")))

    @staticmethod
    def _connect_to_station(cm):
        # Check if we can find the configured WiFi station SSID in the available networks
        logging.getLogger("wifi").info("Scanning WiFi networks for SSID [{}]".format(cm.get("sta_ssid")))
        retrial_count = 0
        ssid_match = False
        sta_password_mode = None
        while retrial_count < 4 and not ssid_match:
            nets = WifiManager._wlan.scan()
            for net in nets:
                if net.ssid == cm.get("sta_ssid"):
                    ssid_match = True
                    logging.getLogger("wifi").info("SSID [{}] was found in the available WiFi networks.".format(cm.get("sta_ssid")))
                    sta_password_mode = net.sec
                    break
            retrial_count += 1
            if not ssid_match:
                logging.getLogger("wifi").info("SSID [{}] was not found in the available WiFi networks. Issuing a rescan, attempt [{}]".format(cm.get("sta_ssid"), retrial_count))
            time.sleep(1.5)
        if not ssid_match:
            logging.getLogger("wifi").error("Could not connect device to station with SSID [{}], device will not attempt a reconnect.".format(cm.get("sta_ssid")))
            return

        # Try connecting to the SSID with the provided credentials
        ssid_auth = (sta_password_mode, cm.get("sta_password")) if sta_password_mode and cm.get("sta_ssid") else None
        WifiManager._wlan.connect(cm.get("sta_ssid"), auth=ssid_auth, timeout=10000)
        retrial_count = 0
        while (not WifiManager._wlan.isconnected()) and (retrial_count < 10):
            time.sleep(2)
            retrial_count += 1
        if WifiManager._wlan.isconnected():
            logging.getLogger("wifi").info("Connected to WiFi station with SSID [{}]".format(cm.get("sta_ssid")))
        else:
            logging.getLogger("wifi").error("Could not connect to Wifi SSID [{}] even though it was found in the available networks. Is the password correct?".format(cm.get("sta_ssid")))

    @staticmethod
    def apply_settings(configuration_manager=None):
        """Apply WiFi settings as provided by the given configuration manager
        Calling this method will reset the current WiFi connections!
        
        :param configuration_manager: custom non global configuration, defaults to None
        :type configuration_manager: VolatileConfiguration, optional
        :raises TypeError: When the given configuration is not of the VolatileConfiguration type
        """
        if configuration_manager and not isinstance(configuration_manager, VolatileConfiguration):
            raise TypeError("Provided configuration manager is not an instance of a volatile configuration class. | Given type [{}]".format(type(configuration_manager)))
        cm = configuration_manager if configuration_manager else VolatileConfiguration

        WifiManager.deinit()

        current_mode = cm.get("wifi_mode", WIFIMODI.OFF)
        if current_mode != WIFIMODI.OFF:
            WifiManager._wlan = WLAN(mode=current_mode, ssid="ZombieRouter-{}".format(device.get_unique_name(":")), auth=None, antenna=None)
            WifiManager._apply_interface_configurations(cm)
            if current_mode is not WIFIMODI.STA:
                logging.getLogger("wifi").info("Access point up and running.")
            if cm.get("sta_ssid", None) and (current_mode == WIFIMODI.STA or current_mode == WIFIMODI.STA_AP):
                WifiManager._connect_to_station(cm)
                            
    @staticmethod
    def deinit():
        """Disable the WiFi radio completely
        """
        if WifiManager._wlan:
            WifiManager._wlan.deinit()
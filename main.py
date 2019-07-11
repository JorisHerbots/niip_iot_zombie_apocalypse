import logging
from volatileconfiguration import VolatileConfiguration as Config
from microWebServer import MicroWebSrv
from microDnsServer import MicroDNSSrv
from zombieRouter import ZombieRouter
from zombiegram import *
import configurationWebserver
from configurationWebserver import InputManager

# TODO REMOVE
diag = DiagnosticPayload((1.1, 2.2), [b"\x11\x11\x11\x11"], 97, 1)

# ZombieRouter LoRa network
zr = ZombieRouter(lora)
zr.start()

# Zombie callback
def zombie_detected_callback(confidence):
    payload  = DetectionPayload(confidence, 1)
    zr.queue_zombiegram(3, payload)

try:
    system.set_zombie_detected_callback(zombie_detected_callback)
except Exception as e:
    logging.getLogger("main").error("Could not set zombie detection callback! | Reason [{}]".format(str(e)))

# Webserver
mws = MicroWebSrv(bindIP="0.0.0.0", zombie_router=zr)
InputManager.set_webserver_controller(mws)
if Config.get("wifi_mode", WIFIMODI.OFF) != WIFIMODI.OFF:
    mws.Start(threaded=True)

def sleep_check():
    if Config.get("device_is_router", False) or Config.get("device_is_gateway", False):
        return False

    if zr.retransmission_count() > 0:
        return False

    
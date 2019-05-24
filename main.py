from volatileconfiguration import VolatileConfiguration as Config
from microWebServer import MicroWebSrv
from microDnsServer import MicroDNSSrv
from zombieRouter import ZombieRouter
from zombiegram import *
import configurationWebserver

# mds = MicroDNSSrv.Create({
#     "zombie.local" : Config.get("ap_static_ip")
# })
# mws = MicroWebSrv(bindIP="0.0.0.0")
# mds.Start(bind_ip=Config.get("ap_static_ip", "0.0.0.0"))
# mws.Start(threaded=True)
zr = ZombieRouter(lora)
zr.start()

test = Zombiegram(source_id=b"\x00\x00\x00\x03", seq_num=2, priority_flag=3, tampered_flag=False, maintenance_flag=False)
diag = DiagnosticPayload((1.1, 2.2), [b"\x11\x11\x11\x11"], 97, 1)
test.add_payload(diag)
test.sign_package("test")

# from network import LoRa
# from zombiegram import * # TODO REMOVE!!!

# import wifi
from microWebServer import MicroWebSrv
from configurationWebserver import *
# from lazy_object_proxy import MicroDNSSrv

# wifi.init_ap()



# @MicroWebSrv.route('/test', 'GET')
# def handlerFuncPost(httpClient, httpResponse):
#     print("Sup bitches")
#     httpResponse.WriteResponseOk( headers         = None,
#                                 contentType     = "text/html",
#                                 contentCharset  = "UTF-8",
#                                 content         = "HELLO WORLD :D :D" )

# mds = MicroDNSSrv.Create({
#     "zombie.local" : "10.0.0.2"
# })
# mds.Start()

mws = MicroWebSrv(bindIP="0.0.0.0")
mws.Start(threaded=True)
# print(lora)

# test = Zombiegram(source_id=b"\x00\x00\x00\x03", seq_num=2, priority_flag=3, tampered_flag=False, maintenance_flag=False)
# diag = DiagnosticPayload((1.1, 2.2), [b"\x11\x11\x11\x11"], 97, 1)
# test.add_payload(diag)
# detect = DetectionPayload(50, 1)
# us = UsmsPayload("a"*70)
# test.add_payload(detect)
# print(test.get_bytestring_representation())
# print()
# print(test)

# import device
# print(device.get_unique_name())

# # rgb LED color for each state: disabled, detached, child, router, leader and single leader
# RGBLED = [0x0A0000, 0x0A0000, 0x0A0A0A, 0x000A00, 0x0A000A, 0x000A0A]

# import sdhandler
# sdhandler.mount_device()
# with sdhandler.FileHandler("test.txt", "w") as fp:
#     fp.write("Hello world! :D")

# # sdhandler.mount_device()

# lora = LoRa(mode=LoRa.LORA, region=LoRa.EU868, bandwidth=LoRa.BW_125KHZ, sf=7)
# mesh = lora.Mesh()
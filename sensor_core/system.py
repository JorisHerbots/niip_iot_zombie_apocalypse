from rgbled import RGBLed
from battery import Battery
from sleep import Sleep
from exceptions import Exceptions

from shields import Shield
from communication import I2CBus, Connector, Pins
from configurations import Configuration
from protection import Protection
from volatileconfiguration import VolatileConfiguration as Config
import device


class System:
    """Class managing the hardware of the PyCom."""

    @property
    def configButton(self):
        return self.__pins.configButton

    @property
    def led(self):
        return RGBLed.color
    @led.setter
    def led(self, color):
        RGBLed.color = color

    @property
    def isSleepWake(self):
        return self.__sleep.isSleepWake

    @property
    def batteryLevel(self):
        return self.__battery.level

    @property
    def sensorID(self):
        return self.__config.id

    @property
    def tempered(self):
        return self.__protection.tempered

    @property
    def coordinates(self):
        return self.__protection.coordinates

    @property
    def canSleep(self):
        return self.__canSleep

    @property
    def canSleepChangeCallback(self):
        return self.__canSleepChangeCallback

    @canSleepChangeCallback.setter
    def canSleepChangeCallback(self, callback):
        self.__canSleepChangeCallback = callback


    # constructor
    def __init__(self):
        self.__sleep = Sleep()
        self.__canSleep = True

        self.__i2cBus = I2CBus()
        self.__shield = Shield(self.__i2cBus)
        self.__connector = Connector(self.__i2cBus)

        self.__pins = Pins(self.__sleep)

        self.__config =  Configuration(sleep=self.__sleep, connector=self.__connector, pins=self.__pins, \
            detectionCallback=self.__detectCallback, canSleepCallback=self.__canSleepCallback)
        self.__battery = Battery(sleep=self.__sleep, shield=self.__shield, config=self.__config)
        self.__protection = Protection(sleep=self.__sleep, shield=self.__shield, i2cBus=self.__i2cBus)

        # set variables
        self.__canSleepChangeCallback = None

        # self.__protection.gpsChangeCallback = lambda x: print("gps changed: " + str(x))
        # self.__protection.temperedChangeCallback = lambda x, y: print("tempered changed: " + str(x) + ", distance: " + str(y))
        self.__protection.gpsChangeCallback = self.gpsChangeCallback
        self.__protection.temperedChangeCallback = self.tamperedChangeCallback

        # External callbacks
        self.external_detection_callback = None

    def set_zombie_detected_callback(self, zombie_detection_callback=None):
        self.external_detection_callback = zombie_detection_callback

    def gpsChangeCallback(self, position):
        Config.set("device_position", position, True, True)

    def tamperedChangeCallback(self, is_tampered, distance):
        # if distance == None -> Accelerometer has triggered the protection
        Config.set("lora_tampered_flag", is_tampered, True, True) # Lora zombiegram tampered flag
        device.drop_trust_key()

    def notifyNewConfiguration(self):
        self.__sleep.resetTimers()
        self.__config.notifyNewConfiguration()
        self.__protection.notifyNewConfiguration()

    # set the device to sleep mode
    def sleep(self, milliseconds=0):
        print("Going to sleep")
        self.__sleep.sleep(milliseconds)

    def __detectCallback(self, confidence):
        if self.external_detection_callback:
            confidence = int(confidence*100) # Translate between zombiegram and system definitions
            self.external_detection_callback(confidence)

    def __canSleepCallback(self, value):
        if self.__canSleep != value:
            print('can sleep: ' + str(value))
            self.__canSleep = value
            if self.__canSleepChangeCallback:
                self.__canSleepChangeCallback(value)

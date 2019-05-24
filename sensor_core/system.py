from rgbled import RGBLed
from battery import Battery
from sleep import Sleep
from exceptions import Exceptions

from shields import Shield
from communication import I2CBus, Connector, Pins
from configurations import Configuration
from protection import Protection


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
    def __init__(self, configurationManager, sendMessageCallback, requestUserCallback):
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
        self.__sendMessageCallback = sendMessageCallback
        self.__requestUserCallback = requestUserCallback
        self.__canSleepChangeCallback = None

        if Exceptions.hasErrors() and requestUserCallback:
            requestUserCallback()

        self.__protection.gpsChangeCallback = lambda x: print("gps changed: " + str(x))
        self.__protection.temperedChangeCallback = lambda x, y: print("tempered changed: " + str(x) + ", distance: " + str(y))

    def notifyNewConfiguration(self):
        print('New configuration found')
        self.__sleep.resetTimers()
        self.__config.notifyNewConfiguration()
        self.__protection.notifyNewConfiguration()

    # set the device to sleep mode
    def sleep(self, milliseconds=0):
        print("Going to sleep")
        self.__sleep.sleep(milliseconds)

    def __detectCallback(self, confidence):
        print('zombie detected! confidence: ' + str(confidence))

    def __canSleepCallback(self, value):
        if self.__canSleep != value:
            print('can sleep: ' + str(value))
            self.__canSleep = value
            if self.__canSleepChangeCallback:
                self.__canSleepChangeCallback(value)

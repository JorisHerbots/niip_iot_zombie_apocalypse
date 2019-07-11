import sys
import json
import pycom


from communication import Pins
from exceptions import Exceptions

from volatileconfiguration import VolatileConfiguration as Config
from configurationWebserver import InputManager

configs = {
  0b00000000: {
    'moduleName': 'undefined',
    'className': 'Undefined',
    'communication': Pins.DIGITAL,
    'config': {
        'id': 0b00000000,
        'name': 'No Sensor',
        'powerActive': 100, # mA
        'powerInactive': 15, # mA
        'batteryCapacity': 5000, # mA
    },
    'to_configure': {
        "powerActive": int,
        "powerInactive": int,
        "batteryCapacity": int
    }
  },

  0b00000001: {
    'moduleName': 'laser',
    'className': 'Laser',
    'communication': Pins.I2C,
    'config': {
        'id': 0b00000001,
        'name': 'Laser',
        'powerActive': 100, # mA
        'powerInactive': 15, # mA
        'batteryCapacity': 5000, # mA
        'rate': 7,
        'threshold': 1200,
        'address': 72,
        'detectWindow': 10, # sec
        'maxDetectionRate': 4,
        'sendRate': 10 # sec
    },
    'to_configure': {
        "powerActive": int,
        "powerInactive": int,
        "batteryCapacity": int,
        "rate": int,
        "threshold": int,
        "address": int,
        "detectWindow": int,
        "maxDetectionRate": int,
        "sendRate": int
    }
  },
}


class Configuration:

    LAST_CONFIG_ID_KEY = 'lastConfigId'

    @property
    def id(self):
        return self.__id

    @property
    def config(self):
        return self.__config['config']

    @property
    def module(self):
        return self.__module


    def __init__(self, connector, sleep, pins, detectionCallback, canSleepCallback):
        self.__id = connector.id

        storedId = self.__getPersistentVariable(Configuration.LAST_CONFIG_ID_KEY)
        if sleep.isSleepWake and self.__id != storedId:
            Exceptions.error(Exception('Current sensor id (' + str(self.__id) + ') doesn\'t match with stored id (' + str(storedId) + ')'))
            self.__id = 0

        if self.__id not in configs:
            Exceptions.error(Exception('Undefined configuration key: "' + str(self.__id) + '"'))
            self.__id = 0

        self.__setPersistentVariable(Configuration.LAST_CONFIG_ID_KEY, self.__id)
        self.__config = configs[self.__id]
        self.__pins = pins
        self.__detectionCallback = detectionCallback
        self.__canSleepCallback = canSleepCallback

        # Load into InputManager
        prefix = "sensor_" + self.__config["moduleName"] + "_"
        for option in self.__config["to_configure"]:
            config_key = (prefix + option).lower()
            Config.set(config_key, self.__config["config"][option], True, False)
            InputManager.add_input(config_key, self.__config["to_configure"][option], self.__config["config"][option], self.__config["config"]["name"], "")
        InputManager.set_category_priority(self.__config["config"]["name"], 120)

    def notifyNewConfiguration(self):
         # Load into sensor config
        prefix = "sensor_" + self.__config["moduleName"] + "_"
        for option in self.__config["to_configure"]:
            config_key = (prefix + option).lower()
            self.__config["config"][option] = Config.get(config_key, self.__config["config"][option])
        try:
            self.__module = self.__createInstance(self.__config['moduleName'], self.__config['className'])
        except Exception as e:
            Exceptions.error(Exception('Invalid module: ' + str(e)))
            self.__module = None


    # create an instance specified by the module name and the class name
    def __createInstance(self, moduleName, className):
        exec('import ' + moduleName, {})
        return getattr(sys.modules[moduleName], className)(self.__config['config'], \
            self.__pins.createCommunication(self.__config['communication']), self.__pins.interruptPin, \
            self.__detectionCallback, self.__canSleepCallback)


    def __getPersistentVariable(self, key, default=0):
        if (pycom.nvs_get(key) == None):
            pycom.nvs_set(key, default)
        return pycom.nvs_get(key)

    def __setPersistentVariable(self, key, value):
        pycom.nvs_set(key, value)

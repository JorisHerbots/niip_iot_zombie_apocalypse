import sys
import json
import pycom


from communication import Pins
from exceptions import Exceptions

configs = {
  0b00000000: {
    'moduleName': 'undefined',
    'className': 'Undefined',
    'communication': Pins.DIGITAL,
    'config': {
        'id': 0b00000000,
        'name': 'None',
        'powerActive': 100, # mA
        'powerInactive': 15, # mA
        'batteryCapacity': 5000, # mA
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

        # TODO: load config into manager



    def notifyNewConfiguration(self):

        # TODO: read new config

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

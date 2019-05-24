from pycoproc import Pycoproc
from communication import I2CBus
from exceptions import Exceptions

shields =  {
    'default': {
        'name': 'default',
        'protectionACC': False,
        'protectionGPS': False,
        'batteryEstimation': False,
    },
    'pytrack': {
        'name': 'pytrack',
        'protectionACC': True,
        'protectionGPS': True,
        'batteryEstimation': True,
    },
    'pysense': {
        'name': 'pysense',
        'protectionACC': True,
        'protectionGPS': False,
        'batteryEstimation': True,
    },
    'expansion': {
        'name': 'expansion',
        'protectionACC': False,
        'protectionGPS': False,
        'batteryEstimation': True,
    },
    'deepsleep': {
        'name': 'deepsleep',
        'protectionACC': False,
        'protectionGPS': False,
        'batteryEstimation': False,
    }
}


class Shield:

    @property
    def name(self):
        if 'name' in self.__shield:
            return self.__shield['name']
        return 'unknown'

    @property
    def py(self):
        return self.__py

    # constructor
    def __init__(self, i2cBus):
        self.__shield = shields['default']
        self.__py = None

        try:
            self.__py = Pycoproc(i2c=i2cBus.i2c(I2CBus.BUS0))

            version = self.__py.read_hw_version()
            if version == 2:
                self.__shield = shields['pysense']
            elif version == 3:
                self.__shield = shields['pytrack']

        except Exception as e:
            Exceptions.warning('No pysense nor pytrack: ' + str(e))
            self.__py = None
            self.__shield = shields['expansion']

    # check if the shield has support for the given key
    def supports(self, key):
        return key in self.__shield and self.__shield[key]

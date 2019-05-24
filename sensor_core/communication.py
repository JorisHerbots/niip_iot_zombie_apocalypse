from rgbled import RGBLed
from trigger import TriggerPin
from MCP23017 import MCP23017
from exceptions import Exceptions

from machine import I2C, SPI, UART, Pin

"""###########################################################"""

class Pins:

    DATA0 = 'P9'
    DATA1 = 'P10'
    DATA2 = 'P11'

    INTERRUPT = 'P8'
    LED_BUTTON = 'P19'
    CONFIG_BUTTON = 'P20'

    SCL = 'P21'
    SDA = 'P22'
    INTERNAL_INTERRUPT = 'P13'

    I2C = {'name':'i2c', 'scl': DATA0, 'sda': DATA1, 'digital0': DATA2}
    SPI = {'name':'spi', 'clk': DATA0, 'miso': DATA1, 'mosi': DATA2}
    SERIAL = {'name':'serial', 'tx': DATA0, 'rx': DATA1, 'digital0': DATA2}
    DIGITAL = {'name':'digital', 'digital0': DATA0, 'digital1': DATA1, 'digital2': DATA2}

    @property
    def configButton(self):
        return self.__configButton

    @property
    def interruptPin(self):
        return self.__interruptPin

    def __init__(self, sleep):
        self.__configButton = TriggerPin(sleep=sleep, pinName=Pins.CONFIG_BUTTON)
        self.__ledButton = TriggerPin(sleep=sleep, pinName=Pins.LED_BUTTON, activeCallback=RGBLed.on, inActiveCallback=RGBLed.off, callAtWake=False)
        self.__interruptPin = TriggerPin(sleep=sleep, pinName=Pins.INTERRUPT)

        if self.__ledButton:
            RGBLed.on
        else:
            RGBLed.off

    def createCommunication(self, pins):
        if pins['name'] == 'i2c':
            return [I2C(1, mode=I2C.MASTER, pins=(pins['sda'], pins['scl'])), pins['digital0']]
        if pins['name'] == 'spi':
            return [SPI(0, mode=SPI.MASTER, pins=(pins['clk'], pins['mosi'], pins['miso']))]
        if pins['name'] == 'serial':
            return [UART(1, pins=(pins['tx'], pins['rx'])), pins['digital0']]
        if pins['name'] == 'digital':
            return [pins['digital0'], pins['digital1'], pins['digital2']]
        return []

"""###########################################################"""

class Connector:

    @property
    def id(self):
        return self.__id


    def __init__(self, i2cBus):
        try:
            self.__io = MCP23017(i2cBus.i2c(I2CBus.BUS0))
            self.__io.iodira = 0b11111111
            self.__io.gppua = 0b11111111
            self.__id = (~self.__io.gpioa) & 0b11111111
        except Exception as e:
            Exceptions.error(Exception('Connector not found: ' + str(e)))
            self.__id = 0


"""###########################################################"""

class I2CBus:

    BUS0 = 0
    BUS1 = 1

    def __init__(self):
        self.__i2c = [None, None]
        self.__i2c[0] = I2C(0, I2C.MASTER, pins=(Pins.SDA, Pins.SCL))
        self.__i2c[1] = None

    def devices(self, bus):
        if bus >= len(self.__i2c) or not self.__i2c[bus] :
            return []
        return self.__i2c[bus].scan()

    def i2c(self, bus):
        if bus >= len(self.__i2c):
            return None
        return self.__i2c[bus]

    def deinit(self, bus):
        if bus >= len(self.__i2c) or not self.__i2c[bus] :
            return
        self.__i2c[bus].deinit()

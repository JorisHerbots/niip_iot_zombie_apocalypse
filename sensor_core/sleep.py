import machine
import pycom
import utime

from exceptions import Exceptions

class Sleep:

    @property
    def wakeReason(self):
        return machine.wake_reason()[0]
    @property
    def wakePins(self):
        return machine.wake_reason()[1]
    @property
    def powerOnWake(self):
        return self.wakeReason == machine.PWRON_WAKE
    @property
    def pinWake(self):
        return self.wakeReason == machine.PIN_WAKE
    @property
    def RTCWake(self):
        return self.wakeReason == machine.RTC_WAKE
    @property
    def ULPWake(self):
        return self.wakeReason == machine.ULP_WAKE
    @property
    def isSleepWake(self):
        return self.pinWake or self.RTCWake or self.ULPWake

    @property
    def activeTime(self):
        return self.__activeTime + utime.ticks_diff(utime.ticks_ms(), self.__activityStart)
    @property
    def inactiveTime(self):
        return self.__inactiveTime

    ACTIVE_TIME_KEY = 'activeTime'
    INACTIVE_TIME_KEY = 'inactiveTime'
    SLEEP_TIME_KEY = 'sleepTime'

    def __init__(self):
        self.__activityStart = utime.ticks_ms()

        self.__initPersistentVariable(Sleep.ACTIVE_TIME_KEY)
        self.__initPersistentVariable(Sleep.INACTIVE_TIME_KEY)

        if not self.powerOnWake:
            sleptTime = pycom.nvs_get(Sleep.SLEEP_TIME_KEY) - machine.remaining_sleep_time()
            pycom.nvs_set(Sleep.INACTIVE_TIME_KEY, pycom.nvs_get(Sleep.INACTIVE_TIME_KEY) + sleptTime)

        self.__activeTime = pycom.nvs_get(Sleep.ACTIVE_TIME_KEY)
        self.__inactiveTime = pycom.nvs_get(Sleep.INACTIVE_TIME_KEY)
        self.__wakeUpPins = []


    def __initPersistentVariable(self, key, value=0):
        if (pycom.nvs_get(key) == None):
            pycom.nvs_set(key, value)


    def addWakeUpPin(self, pin):
        # P2, P3, P4, P6, P8 to P10 and P13 to P23
        if isinstance(pin, list):
            self.__wakeUpPins.extend(pin)
        else:
            self.__wakeUpPins.append(pin)

        try:
            machine.pin_sleep_wakeup(self.__wakeUpPins, mode=machine.WAKEUP_ANY_HIGH, enable_pull=True)
        except Exception as e:
            Exceptions.error(Exception('Sleep not available: ' + str(e)))

    def resetTimers(self):
        pycom.nvs_set(Sleep.ACTIVE_TIME_KEY, 0)
        pycom.nvs_set(Sleep.INACTIVE_TIME_KEY, 0)

    def sleep(self, milliseconds=0):
        if milliseconds == 0:
            milliseconds = 604800000 # 1 week

        pycom.nvs_set(Sleep.SLEEP_TIME_KEY, milliseconds)
        pycom.nvs_set(Sleep.ACTIVE_TIME_KEY, self.activeTime + utime.ticks_diff(utime.ticks_ms(), self.__activityStart))

        try:
            machine.deepsleep(milliseconds)
        except Exception as e:
            Exceptions.error(Exception('Deepsleep not available: ' + str(e)))

    def delay(self, milliseconds):
        utime.sleep_ms(milliseconds)

import utime
from machine import Pin

# Class that calls the callback method once the given pin is low for at least a defined number of seconds
class TriggerPin:
    """Class that will listen for changes on a specific pin and generate callback events."""

    @property
    def state(self):
        return self.__pin()

    @property
    def pinName(self):
        return self.__pinName

    @property
    def longActiveTime(self):
        return self.__longActiveTime
    @longActiveTime.setter
    def longActiveTime(self, seconds):
        self.__longActiveTime = seconds

    @property
    def activeCallback(self):
        return self.__activeCallback
    @activeCallback.setter
    def activeCallback(self, callback):
        self.__activeCallback = callback

    @property
    def inActiveCallback(self):
        return self.__inActiveCallback
    @inActiveCallback.setter
    def inActiveCallback(self, callback):
        self.__inActiveCallback = callback

    @property
    def longActiveCallback(self):
        return self.__longActiveCallback
    @longActiveCallback.setter
    def longActiveCallback(self, callback):
        self.__longActiveCallback = callback

    @property
    def isWakeReason(self):
        return self.__isWakeReason

    # constants
    __RISING = 1
    __FALLING = 0

    def __init__(self, sleep, pinName, activeCallback=None, inActiveCallback=None, longActiveCallback=None, longActiveTime=-1, callAtWake=True):
        """Constructor, creates a new listener for pin changes (active high).

        Parameters
        ----------
        pinName : string
            PyCom name of the pin to listen on ("Px").
        longActiveTime : integer=-1
            [Optional] Time in seconds the pin needs to be active before the event will be generated, -1 to disable this action.
        activeCallback : function()=None
            [Optional] Callback method for when the pin becomes active (high), or when the pin, if wakeCallback is not specified, wakes up the device.
        inActiveCallback : function()=None
            [Optional] Callback method for when the pin becomes inactive (low).
        longActiveCallback : function()=None
            [Optional] Callback method for when the pin becomes active (high) for a given amount of seconds ("longActiveTime" needs to be set).
        Returns
        -------
        TriggerPin
            TriggerPin object that will call the callbacks whenever an event occurs.

        """
        self.__sleep = sleep
        self.__pin = Pin(pinName, mode=Pin.IN, pull=Pin.PULL_DOWN)
        self.__pin.callback(Pin.IRQ_FALLING | Pin.IRQ_RISING, self.__interrupt)

        self.__pinName = pinName
        self.__activeCallback = activeCallback
        self.__inActiveCallback = inActiveCallback
        self.__longActiveCallback = longActiveCallback
        self.__longActiveTime = longActiveTime

        self.__lastPressed = 0
        self.__lastEvent = None
        self.__wakeUpCallbackEnabled = callAtWake
        self.__isWakeReason = False

        self.__checkWakeUpState()
        sleep.addWakeUpPin(pin=pinName)

    # check if the pin caused the device to wake up
    def __checkWakeUpState(self):
        if (self.__wakeUpCallbackEnabled and self.__sleep.pinWake and self.__pin in self.__sleep.wakePins):
            self.__isWakeReason = True
            if self.__activeCallback:
                self.__wakeUpCallbackEnabled = False
                self.__activeCallback()
            self.__lastPressed = utime.time()

    # check if the event already happended before and return True if that is the case
    def __debounced(self, event):
        if (self.__lastEvent == event):
            return True
        self.__lastEvent = event
        return False

    # handle the interrupt of the pin
    def __interrupt(self, arg):
        self.__sleep.delay(10)

        if self.__pin():
            # rising, becoming active
            if self.__debounced(self.__RISING):
                return

            self.__lastPressed = utime.time()

            # active callback
            if self.__activeCallback:
                self.__activeCallback()

        else:
            # falling, becoming inactive
            if self.__debounced(self.__FALLING):
                return

            # inactive callback
            if self.__inActiveCallback:
                self.__inActiveCallback()

            # long active callback
            if (self.__longActiveTime > -1) and (utime.time() - self.__lastPressed) >= self.__longActiveTime and self.__longActiveCallback:
                self.__longActiveCallback()

            self.__lastPressed = 0

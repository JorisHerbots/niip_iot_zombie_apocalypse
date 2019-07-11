import utime
import json
import _thread
from math import sin, cos, sqrt, atan2, radians

from LIS2HH12 import LIS2HH12
from L76GNSS import L76GNSS
from communication import Pins, I2CBus
from trigger import TriggerPin
from exceptions import Exceptions

from volatileconfiguration import VolatileConfiguration as Config
from configurationWebserver import InputManager

class Protection:
    """Protects the device from theft. Uses the accelerometer to detect movement, GPS is used to measure moved distance.
    When the device boots a location will be set if there isn't any stored, when a new configuration is uploaded the stored
    location will be overwritten"""

    R = 6373.0 # radius earth in km
    GPS_FILE_PATH = '/flash/datastore/coordinates.json'


    @property
    def tempered(self):
        return self.__tempered

    @property
    def temperedChangeCallback(self):
        return self.__temperedChangeCallback
    @temperedChangeCallback.setter
    def temperedChangeCallback(self, callback):
        self.__temperedChangeCallback = callback

    @property
    def gpsChangeCallback(self):
        return self.__gpsChangeCallback
    @gpsChangeCallback.setter
    def gpsChangeCallback(self, callback):
        self.__gpsChangeCallback = callback

    @property
    def coordinates(self):
        return self.__coordinates


    def __init__(self, sleep, shield, i2cBus):

        self.__sleep = sleep
        self.__i2cBus = i2cBus
        self.__tempered = False
        self.__coordinates = (None, None)

        # threading
        self.__threadStarted = False
        self.__threadStartedLock = _thread.allocate_lock()
        self.__threadCallbacks = []
        self.__threadCallbacksLock = _thread.allocate_lock()

        # ACC
        self.__acc = None
        self.__accGForce = 500 # mG force the accelerometer must have to trigger the interrupt
        self.__accDuration = 200 # duration in milliseconds the accelerometer must move to trigger the interrupt
        self.__accLongDuration = 3 # seconds indicating how long the accelerometer must be moving to indicate tempering

        # GPS
        self.__gps = None
        self.__gpsEnabled = False
        self.__gpsMaxDistance = 0.01 # the distance in km to trigger the callback
        self.__gpsTimeoutTime = 60 # timeout in seconds before the gps times out
        self.__gpsInterval = 100 # milliseconds between two gps requests

        self.__temperedChangeCallback = None
        self.__gpsChangeCallback = None

        # Set Config & Inputmanager settings
        Config.set("accelerometer_gforce", 500, True, False)
        Config.set("accelerometer_duration", 200, True, False)
        Config.set("accelerometer_longduration", 3, True, False)
        Config.set("gps_max_distance", 0.01, True, False)
        Config.set("gps_timeout", 60, True, False)
        Config.set("gps_interval", 100, True, False)

        InputManager.add_input("accelerometer_gforce", int, 500, "Accelerometer Config", "mG force the accelerometer must have to trigger the interrupt")
        InputManager.add_input("accelerometer_duration", int, 200, "Accelerometer Config", "duration in milliseconds the accelerometer must move to trigger the interrupt")
        InputManager.add_input("accelerometer_longduration", int, 3, "Accelerometer Config", "seconds indicating how long the accelerometer must be moving to indicate tempering")
        InputManager.add_input("gps_max_distance", float, 0.01, "GPS Config", "the distance in km to trigger the callback")
        InputManager.add_input("gps_timeout", int, 60, "GPS Config", "timeout in seconds before the gps times out")
        InputManager.add_input("gps_interval", int, 100, "GPS Config", "milliseconds between two gps requests")
        InputManager.set_category_priority("GPS Config", 116)
        InputManager.set_category_priority("Accelerometer Config", 115)

        try:
            if shield.supports('protectionACC'):
                self.__startACC()

                if shield.supports('protectionGPS'):
                    self.__startGPS()
                    self.__requestGPSCoordinates(callback=self.__setInitialCoordinates)

        except Exception as e:
            Exceptions.warning(Exception('Protection module error: ' + str(e)))
            raise e


    def notifyNewConfiguration(self):
        self.__tempered = False
        self.__requestGPSCoordinates(callback=self.__storeCoordinates)

        # Get values from config
        self.__accGForce = Config.get("accelerometer_gforce", 500)
        self.__accDuration = Config.get("accelerometer_duration", 200)
        self.__accLongDuration = Config.get("accelerometer_longduration", 3)
        self.__gpsMaxDistance = Config.get("gps_max_distance", 0.01)
        self.__gpsTimeoutTime = Config.get("gps_timeout", 60)
        self.__gpsInterval = Config.get("gps_interval", 100)

    """#######################################################################"""

    def __startACC(self):
        self.__accPin = TriggerPin(self.__sleep, Pins.INTERNAL_INTERRUPT, activeCallback=self.__accelerometerActive, \
            longActiveCallback=self.__accelerometerLongActive, longActiveTime=self.__accLongDuration, callAtWake=False)
        self.__acc = LIS2HH12()
        self.__acc.enable_activity_interrupt(self.__accGForce, self.__accDuration)

    # interrupt call for the accelerometer
    def __accelerometerActive(self):
        print('Activity interrupt')
        if self.__gpsEnabled:
            self.__requestGPSCoordinates(callback=self.__checkDistance, timeout=self.__gpsTimeoutTime)

    def __accelerometerLongActive(self):
        print('Long activity interrupt')
        if not self.__tempered and self.__temperedChangeCallback:
            self.__temperedChangeCallback(True, None)
        self.__tempered = True

    """#######################################################################"""

    def __startGPS(self):
        try:
            self.__gps = L76GNSS(self.__i2cBus.i2c(I2CBus.BUS0))
        except Exception as e:
            Exceptions.error(Exception('Failed to setup GPS: ' + str(e)))


    def __checkDistance(self, coordinates):
        distance = self.__distanceKM(coordinates, self.__loadStoredCoordinates(coordinates))
        if  distance > self.__gpsMaxDistance:
            if not self.__tempered and self.__temperedChangeCallback:
                self.__temperedChangeCallback(True, distance)
            self.__tempered = True


    """##########################################"""

    def __requestGPSCoordinates(self, callback, timeout=0):
        _thread.start_new_thread(self.__requestGPSCoordinatesThreaded, (callback, timeout))

    # start a new thread to request the gps coordinates
    def __requestGPSCoordinatesThreaded(self, callback, timeout=0):
        try:
            with self.__threadCallbacksLock:
                if callback not in self.__threadCallbacks:
                    self.__threadCallbacks.append(callback)

            with self.__threadStartedLock:
                if self.__threadStarted:
                    return
                self.__threadStarted = True

            if not self.__gps:
                Exceptions.warning(Exception('GPS module error: GPS not found'))
                with self.__threadStartedLock:
                    self.__threadStarted = False
                return

            coordinates = self.__waitForGPSCoordinates(timeout)

            if None in coordinates:
                Exceptions.warning(Exception('GPS module error: location not found'))
                with self.__threadStartedLock:
                    self.__threadStarted = False
                return

            self.__callGPSCallbacks(coordinates)
        except Exception as e:
            Exceptions.error(Exception('Unknown GPS error: ' + str(e)))
        finally:
            with self.__threadStartedLock:
                self.__threadStarted = False

    # wait until gps coordinates are received or until the timer has run out
    def __waitForGPSCoordinates(self, timeout):
        coordinates = (None, None)
        startTime = utime.time()
        while (timeout == 0 or utime.time() - startTime < timeout) and None in coordinates:
            coordinates = self.__gps.coordinates()
            utime.sleep_ms(self.__gpsInterval)
        return coordinates

    # call all current active gps callbacks
    def __callGPSCallbacks(self, coordinates):
        self.__coordinates = coordinates
        if self.__gpsChangeCallback:
            self.__gpsChangeCallback(coordinates)

        with self.__threadCallbacksLock:
            for callback in self.__threadCallbacks:
                try:
                    callback(coordinates)
                except Exception as e:
                    Exceptions.warning('Failed to call GPS callback: ' + str(e))
            self.__threadCallbacks = []

    """##########################################"""


    def __distanceKM(self, coord1, coord2):
        lat1 = radians(coord1[0])
        lon1 = radians(coord1[1])
        lat2 = radians(coord2[0])
        lon2 = radians(coord2[1])

        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2.0)**2.0 + cos(lat1) * cos(lat2) * sin(dlon / 2.0)**2.0
        c = 2.0 * atan2(sqrt(a), sqrt(1 - a))

        distance = Protection.R * c
        return distance

    """#######################################################################"""

    # store the coordinates only if the current coordinates are none
    def __setInitialCoordinates(self, coordinates):
        storedCoordinates = self.__loadStoredCoordinates()
        if (storedCoordinates == None):
            self.__storeCoordinates(coordinates)
        elif self.__accPin.isWakeReason:
            self.__checkDistance(coordinates)

        self.__gpsEnabled = True

    # store the current coordinates to a file
    def __storeCoordinates(self, coordinates):
        try:
            with open(Protection.GPS_FILE_PATH, 'w') as file:
                if None in coordinates:
                    file.write(json.dumps({}))
                else:
                    file.write(json.dumps({'lat': coordinates[0], 'long': coordinates[1]}))
        except Exception as e:
            Exceptions.error(Exception('Failed to store coordinates: ' + str(e)))

    # load the current coordinates from a file
    def __loadStoredCoordinates(self, defaultCoordinates=None):
        try:
            with open(Protection.GPS_FILE_PATH, 'r') as file:
                coordinates = json.loads(file.read())
                return (coordinates['lat'], coordinates['long'])
        except OSError:
            Exceptions.error(Exception('Failed to read coordinates file: ' + str(e)))
        except Exception as e:
            return defaultCoordinates

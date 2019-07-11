from ADS1X15 import ADS1015
from exceptions import Exceptions
from math import cos, pi

from machine import Timer
import utime


class Laser:

    instance = None

    def __init__(self, configuration, communication, interuptPin, detectionCallback, canSleepCallback):
        if not Laser.instance:
            if (configuration['address'] not in communication[0].scan()):
                Exceptions.error(Exception('I2C device not found'))
                return

            if not detectionCallback or not canSleepCallback:
                Exceptions.error(Exception('No detection or sleep callbacks found, stopping sensor'))
                return

            self.__startTime = utime.time()
            self.__configuration = configuration
            self.__confidence = 0
            self.__detections = []
            self.__detectionCallback = detectionCallback
            self.__canSleepCallback = canSleepCallback
            self.__detected = False
            self.__alarm = None

            self.__adc = ADS1015(communication[0], configuration['address'])
            self.__adc.alert_start_once(rate=configuration['rate'], channel1=0, threshold=configuration['threshold'])
            self.__adc.alert_read()  # clear the interrupt

            interuptPin.inActiveCallback = self.__detectionAlert
            Laser.instance = self
        else:
            Laser.instance.__adc.address = configuration['address']
            Laser.instance.__adc.alert_start_once(rate=configuration['rate'], channel1=0, threshold=configuration['threshold'])
            Laser.instance.__adc.alert_read()  # clear the interrupt

    def __detectionAlert(self):
        self.__canSleepCallback(False)
        self.__detected = True

        lastTime = utime.time()
        self.__detections.append(lastTime)
        while self.__detections[0] < lastTime - self.__configuration['detectWindow']:
            self.__detections.pop(0)

        rate = len(self.__detections) / self.__configuration['detectWindow']
        if rate > self.__configuration['maxDetectionRate']:
            self.__confidence = 1
        else:
            self.__confidence = (cos((rate / self.__configuration['maxDetectionRate']) * pi + pi) + 3.0) / 4.0

        if not self.__alarm:
            self.__detectionCallback(self.__confidence)
            self.__detected = False
            self.__alarm = Timer.Alarm(self.__timerAlert, s=self.__configuration['sendRate'], periodic=False)

    def __timerAlert(self, alarm):
        self.__alarm = None

        if self.__detected:
            self.__detectionCallback(self.__confidence)
            self.__detected = False
            self.__alarm = Timer.Alarm(self.__timerAlert, s=self.__configuration['sendRate'], periodic=False)
        else:
            self.__canSleepCallback(True)

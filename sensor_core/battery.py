class Battery:

    NOT_SUPPORTED = 101

    @property
    def level(self):
        if not self.__supported:
            return Battery.NOT_SUPPORTED

        capacity = self.__config.config['batteryCapacity']
        usageActive = self.__config.config['powerActive'] * self.__toHours(self.__sleep.activeTime)
        usageInactive = self.__config.config['powerInactive'] * self.__toHours(self.__sleep.inactiveTime)
        return max(0, min(100, 100 * (1 - ((usageActive + usageInactive) / capacity))))

    # constructor
    def __init__(self, sleep, shield, config):
        self.__supported = shield.supports('batteryEstimation')
        self.__config = config
        self.__sleep = sleep

    # convert milliseconds to hours
    def __toHours(self, milliseconds):
        return (((milliseconds / 1000.0) / 60.0) / 60.0)

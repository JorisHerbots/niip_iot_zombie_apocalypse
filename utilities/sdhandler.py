from machine import SD
import os
import device

##################
# Module Globals #
##################

__mounted = False
__device_directory_name = device.get_unique_name("-")
__device_directory = "/sd/" + __device_directory_name + "/"

##############
# Exceptions #
##############

class SdNotAvailable(Exception):
    pass

class SdNotMounted(Exception):
    pass

class SdAlreadyMounted(Exception):
    pass

##########################
# Handling functionality #
##########################

def mount_device():
    """Mount the SD card under the directory /sd

    :raises SdAlreadyMounted: When the SD card is already mounted (i.e. the /sd dir is available)
    :raised SdNotAvailable: When the SD card is not inserted
    """
    global __mounted
    try:
        os.listdir('/sd')
        raise SdAlreadyMounted()
    except OSError:
        pass

    try:
        sd = SD()
        os.mount(sd, '/sd')
        __mounted = True
    except OSError:
        raise SdNotAvailable()


class FileHandler:
    def __init__(self, filename, mode):
        """Wrapper for file handling on the SD card

        Files should always be accessed through this abstraction rather then raw via open calls.
        Every device will receive a separate directory on the SD card named after its unique_id/name.
        
        :param filename: filename, can include subdirectory listings
        :type filename: str
        :raises SdNotMounted:
        """
        global __mounted
        if not __mounted:
            raise SdNotMounted()
        self.filepointer = None
        self._open(filename, mode)

    def __enter__(self):
        """Adds the "with" statement ability
        """
        return self.filepointer

    def _open(self, filename, mode):
        """Opens up the file, wrapper for the open functionality of Python

        Internal use only
        """
        global __device_directory_name, __device_directory

        if __device_directory_name not in os.listdir("/sd"):
            os.mkdir(__device_directory[:-1])

        self.filepointer = open(__device_directory + filename, mode)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit functionality for the "with" statement

        Handles the cleaning up part of our open file
        """
        self.filepointer.close()
        
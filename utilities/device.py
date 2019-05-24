import machine
import ubinascii

def get_unique_name(name_separator=""):
    """Retrieve the readable version of the device unique ID (i.e. the MAC)
    
    :param name_separator: MAC separator, defaults to nothing
    :type name_separator: str, optional
    :return: Unique ID as a human readable name
    :rtype: str
    """
    mac = machine.unique_id()
    return ubinascii.hexlify(mac, name_separator).decode("ascii")

def can_device_sleep():
    return True
import json
import os

class ConfigurationNotValid(Exception):
    pass

class VolatileConfiguration:
    """Volatile Configuration
    Provides volatile global configuration options to all libraries and code
    This class can be used in a static or instantiated manner. Creating an instance will link
    all set configs to the instance itself. Utilising the class directly (static) will result
    in the usage of the global volatile configuration.
    """

    _configuration = {}

    def init(self, config=None):
        """Constructor
        
        :param config: configuration to initialise the class instance with, defaults to None
        :type config: dict, optional
        :raises TypeError: When the given config is not a dictionary
        """
        if config:
            if not isinstance(config, dict):
                raise TypeError("config parameter needs to be a dictionary | Given {}".format(config))
            _configuration = config.copy() # Shallow copy, do we need a deep copy??

    @classmethod
    def get_full_configuration(cls):
        """Retrieve the full configuration dictionary (copy)
        
        :return: copy of the dictionary
        :rtype: dict
        """
        return cls._configuration.copy()

    @classmethod
    def load_configuration_from_datastore(cls, name):
        """Load a configuration from file
        
        :param name: COnfiguration name
        :type name: str
        :raises ConfigurationNotValid: When the config contents are not valid
        :raises ConfigurationNotValid: When the config does not exist
        """
        try:
            with open("/flash/datastore/{}.json".format(name), "r") as fp:
                cls._configuration.update(json.load(fp))
        except ValueError:
            raise ConfigurationNotValid("Configuration is not a valid JSON")
        except: # IOError does not exist in µpython?
            raise ConfigurationNotValid("Configuration file is non existing? [{}]".format(name))

    @classmethod
    def save_configuration_to_datastore(cls, name):
        to_save_data = {}
        for key in cls._configuration:
            if cls._configuration[key]["can_be_saved"]:
                to_save_data[key] = cls._configuration[key]
        if not to_save_data:
            return
        
        try:
            with open("/flash/datastore/{}.json".format(name), "w") as fp:
                json.dump(to_save_data, fp)
        except ValueError as e:
            raise ConfigurationNotValid("Configuration could not be serialized to JSON | [{}]".format(str(e)))
        except:
            raise ConfigurationNotValid("Could not create configuration datastore object? [{}]".format(name))

    @staticmethod
    def clean_configuration_from_datastore(name):
        try:
            os.remove("/flash/datastore/{}.json".format(name))
        except OSError:
            raise ConfigurationNotValid("Datastore config [{}] non existant.".format(name))

    @classmethod
    def set(cls, key, value, can_be_saved=True, overwrite=True):
        """Set a configuration item
        All keys are by default lowercase
        
        :param str key:
        :param value:
        :param bool can_be_saved: Only keys marked with this get saved to the datastore upon request
        :param bool overwrite: Will overwrite the key if it already exists
        :raises TypeError: When the key is not a string
        """
        if not isinstance(key, str):
            raise TypeError("Key has to be of 'str' type | Given [{}]".format(type(key)))
        if (key in cls._configuration and overwrite) or not key in cls._configuration:
            cls._configuration[key.lower()] = {"value": value, "can_be_saved": can_be_saved}

    @classmethod
    def get(cls, key, default=None):
        """Retrieve a configuration item
        All keys are by default lowercase
        
        :param str key:
        :param default: A default value to return; default None
        :raises TypeError: When the key is not a string
        """
        if not isinstance(key, str):
            raise TypeError("Key has to be of 'str' type | Given [{}]".format(type(key)))
        return cls._configuration.get(key)["value"] if key in cls._configuration else default
    
import logging

class Exceptions:

    errors = []
    warnings = []

    @staticmethod
    def error(error):
        # Exceptions.errors.append(error)
        logging.getLogger("sensor-core").warning(str(error))

    @staticmethod
    def hasErrors():
        return len(Exceptions.errors) > 0

    @staticmethod
    def warning(warning):
        # Exceptions.warnings.append(warning)
        logging.getLogger("sensor-core").warning(str(warning))

    @staticmethod
    def hasWarnings():
        return len(Exceptions.warnings) > 0

    @staticmethod
    def clear():
        Exceptions.errors = []
        Exceptions.warnings = []

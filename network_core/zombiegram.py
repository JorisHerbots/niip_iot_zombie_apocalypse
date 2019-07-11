__MICROPYTHON__ = True
if __MICROPYTHON__:
    import struct as struct
    import hmac as hmaclib
    import hashlib as hashlib
    import usms as usmslib
else:
    import struct as struct
    import hmac as hmaclib
    import hashlib as hashlib
    import usms as usmslib


######################
# CONVERSION METHODS #
######################


def bytes_to_int(data):
    """Conversion method for retrieving a uniform way of representing data

    :param data: Can be a bytestring, bytes or int
    :return: Value represented as integer
    :rtype: int
    """
    try:
        # Try for int from bytes
        return int.from_bytes(data, "big")
    except TypeError:
        # Probably got an integer
        if not isinstance(data, int):
            raise TypeError(
                "Given data does not represent something we can convert to an integer | Given [{}]".format(data))
        return data


##############
# EXCEPTIONS #
##############


class ZombiegramException(Exception):
    pass


class MethodNotImplementedException(ZombiegramException):
    pass


class UsmsSizeTooLarge(ZombiegramException):
    pass


class MalformedZombiegram(ZombiegramException):
    pass


class ImmutableZombiegram(ZombiegramException):
    pass


class ZombiegramPayloadOverflow(MalformedZombiegram):
    pass


class ZombiegramPayloadPiggybackProhibited(MalformedZombiegram):
    pass


class DisallowedOperation(ZombiegramException):
    def __init__(self, is_immutable):
        super(DisallowedOperation, self).__init__(
            "Method disabled whilst in {} state.".format("immutable" if is_immutable else "mutable"))


##############
# ZOMBIEGRAM #
##############


class Zombiegram:
    __zombiegram_max_size = 64  # bytes
    __header_size_bytes = 10  # bytes
    __unsigned_hmac_default = b"\x00\x00\x00\x00"

    def __init__(self, hmac=None, source_id=None, seq_num=None, priority_flag=0, tampered_flag=False,
                 maintenance_flag=False, raw_payload=None, imported_payloads=[]):
        """A Zombiegram is a zombie apocalypse protocol for spreading information over low latency networks such as Lora.

        As a self-imposed rule; a zombiegram cannot be fragmented across multiple ones. As such the maximal payload is
        limited to 64 bytes in size of which 10 bytes is taken by the header. The header provides authentification and
        tamper-protection combined with anti-replay measures (if used correctly) through its HMAC and sequence number
        settings.

        Devices have the option to specify flags which indicate priority, maintenance required and potential tampering detection.
        The behaviour of the network is adjusted accordingly to these. Do note that the network does not have to respect them in certain cases (like when the HMAC is not trusted).

        It is advised to keep urgent priority Zombiegrams as small as possible (i.e. one payload, no piggybacking).

        The Zombiegram object exists in a mutable or immutable state. By default a new object is mutable until it is signed
        by the :func:`~zombiegram.Zombiegram.sign_package`.

        :param hmac: 4 byte HMAC; leave it set to None if the HMAC needs to be generated (Outgoing Zombiegrams)
        :param source_id: 4 byte unique source ID
        :param int seq_num: number in range [0,255]
        :param int priority_flag: number in  range [0,3], respectively: low, normal, high, urgent
        :param bool tampered_flag: Denotes that the source device has been tempered with
        :param bool maintenance_flag: Denoted that the source device needs maintenance
        :param raw_payload: Raw payload as bytestring; can only be supplied from an incoming/forged packet; automatically marks the object as immutable
        :param imported_payloads: Payload objects created from their respective from_payload() calls; can only be supplied from an incoming/forged packet; automatically marks the object as immutable
        :returns: Zombiegram object
        :rtype: Zombiegram
        :raises MalformedZombiegram: If given parameters do not adhere to the protocol
        """

        # Class properties
        self.__hmac = None
        self.__source_id = None
        self.__seq_num = None
        self.__priority = 1
        self.__tampered = False
        self.__maintenance = False
        self.__bytestring_representation = raw_payload
        self.__is_immutable = False
        self.__current_zombiegram_size = self.__header_size_bytes

        # Set properties
        if hmac:
            try:
                self.__hmac = bytes_to_int(hmac)
            except TypeError:
                raise MalformedZombiegram("HMAC should be a bytestring or integer. | hmac [{}]".format(hmac))
        self.source_id = source_id
        self.seq_num = seq_num
        self.priority = priority_flag
        self.tampered_flag = tampered_flag
        self.maintenance_flag = maintenance_flag
        self.__is_immutable = self.__bytestring_representation  # Sets mutable/immutable status at initialisation (should only happen when an existing payload gets loaded)

        self.payloads = []
        if imported_payloads:
            self.payloads += imported_payloads

    def __check_and_raise_for_mutable_status(self):
        """Check and raise an exception when object parameters are being modified whilst in immutable state
        :raises ImmutableZombiegram:
        """
        if self.__is_immutable:
            raise ImmutableZombiegram("This object is immutable, create a copy for a mutable version.")

    @property
    def hmac(self):
        """Authenticity and anti-tampering measure. Read only property."""
        return self.__hmac

    @property
    def source_id(self):
        """Source ID is a 4 byte long unique ID. e.g. last 4 bytes of a 6 byte long MAC."""
        return self.__source_id

    @source_id.setter
    def source_id(self, value):
        self.__check_and_raise_for_mutable_status()

        try:
            self.__source_id = bytes_to_int(value)
        except TypeError:
            raise MalformedZombiegram("Source ID should be a bytestring or integer. | source_id [{}]".format(value))

    @property
    def seq_num(self):
        """Anti-replay measure. Sequence numbers should always be increased and in be in range [0,255]. In case of overflow, restart from 0."""
        return self.__seq_num

    @seq_num.setter
    def seq_num(self, value):
        self.__check_and_raise_for_mutable_status()
        if not isinstance(value, int) or value not in range(0, 256):
            raise MalformedZombiegram("Sequence number is not in range [0,255] | seq_number [{}]".format(str(value)))
        self.__seq_num = value

    @property
    def priority(self):
        """Priority is an integer in the range [0,3], respectively low, normal, high and urgent.
        The network will always provide faster propagation for urgent messages."""
        return self.__priority

    @priority.setter
    def priority(self, value):
        self.__check_and_raise_for_mutable_status()
        if not isinstance(value, int) or value not in range(0, 4):
            raise MalformedZombiegram(
                "Priority flag should be a number in range [0,3] | priority_flag [{}]".format(str(value)))
        self.__priority = value

    @property
    def tampered_flag(self):
        """Indicates tampering detection."""
        return self.__tampered

    @tampered_flag.setter
    def tampered_flag(self, value):
        self.__check_and_raise_for_mutable_status()
        if not isinstance(value, bool):
            raise MalformedZombiegram(
                "Tampered flag should be a boolean instance. | tampered_flag [{}]".format(str(value)))
        self.__tampered = value

    @property
    def maintenance_flag(self):
        """Indicates maintenance needed for the set source"""
        return self.__maintenance

    @maintenance_flag.setter
    def maintenance_flag(self, value):
        self.__check_and_raise_for_mutable_status()
        if not isinstance(value, bool):
            raise MalformedZombiegram(
                "Maintenance flag should be a boolean instance. | maintenance_flag [{}]".format(str(value)))
        self.__maintenance = value

    def __str__(self):
        """Serialize object as readable plaintext format

        :return: Zombiegram parameters as a string
        :rtype: str
        """
        output = "Zombiegram packet {"
        output += "hmac [{}]".format(self.hmac)
        output += " | source_id [{}]".format(self.source_id)
        output += " | seq_num [{}]".format(self.seq_num)
        output += " | priority [{}]".format(self.priority)
        output += " | tampered [{}]".format(self.tampered_flag)
        output += " | maintenance [{}]".format(self.maintenance_flag)
        output += " | mutable [{}]".format(not self.__is_immutable)
        output += "}"

        for payload in self.payloads:
            output += "\n  |- " + str(payload)

        return output

    def serialize_to_dict(self, trust_key):
        zombiegram_dict = {
            "source_id": self.source_id,
            "priority": self.priority,
            "tampered": self.tampered_flag,
            "maintenance": self.maintenance_flag,
            "trusted": self.is_payload_trusted(trust_key),
            "payloads":[]
        }
        for payload in self.payloads:
            payload_json = payload.serialize_to_dict()
            if payload_json:
                zombiegram_dict["payloads"].append(payload.serialize_to_dict())
        return zombiegram_dict

    @staticmethod
    def get_max_package_size():
        return Zombiegram.__zombiegram_max_size

    def add_payload(self, payload):
        """Add a payload to the Zombiegram.

        Payloads can be piggybacked (not advised in high/urgent priority settings) together if they allow it.

        :param Payload payload:
        :raises ZombiegramPayloadPiggybackProhibited: If a previous or the currently payload being added does not allow Piggybacking.
        :raises ZombiegramPayloadOverflow: The maximum byte treshold is exceeded.
        """
        if not isinstance(payload, Payload):
            raise MalformedZombiegram(
                "Tried adding non-payload payload to the Zombiegram | Given [{}]".format(type(payload)))

        # Check if we can piggyback
        if not payload.can_be_combined and len(self.payloads) > 0:
            raise MalformedZombiegram(
                "Trying to piggyback a payload that can not piggyback! | Payload [{}]".format(type(payload)))
        if len(self.payloads) > 0 and not self.payloads[0].can_be_combined:
            raise ZombiegramPayloadPiggybackProhibited(
                "Zombiegram contains a payload that does not allow other piggybacking payloads. | Previous payload [{}]".format(
                    type(self.payloads[0])))

        if self.__current_zombiegram_size + payload.get_size() > self.__zombiegram_max_size:
            raise ZombiegramPayloadOverflow(
                "Adding payload prohibited, exceeds maximum size of {} bytes | Current size [{}] | Payload size [{}]".format(
                    self.__zombiegram_max_size, self.__current_zombiegram_size, payload.get_size()))

        self.__current_zombiegram_size += payload.get_size()
        self.payloads.append(payload)

    def get_payloads(self):
        """Retrieve all payloads belonging to this zombiegram

        :return: tuple of all payloads and their contents
        :rtype: tuple
        """
        return tuple(self.payloads)

    def __create_hmac(self, trust_key, payload):
        """Internal signing mechanism

        :param bytestring trust_key:
        :param payload: Can be a string or bytestring
        """
        if self.__is_immutable:
            raise ImmutableZombiegram("Cannot create an HMAC when immutable.")

        # Special case of no signing, we simply set the HMAC as 4byte nothingness
        if not trust_key:
            self.__hmac = self.__unsigned_hmac_default  # 4byte zeros
        else:
            try:
                # TODO error capturing
                digester = hmaclib.new(key=trust_key, msg=payload, digestmod=hashlib.sha256)
                self.__hmac = digester.digest()[:4]
            except TypeError:
                digester = hmaclib.new(key=trust_key.encode(), msg=payload, digestmod=hashlib.sha256)
                self.__hmac = digester.digest()[:4]
        self.__is_immutable = True

    def is_signed(self):
        """Retrieve the signed status of the zombiegram

        :return: True and false represent signed and unsigned status respectively
        :rtype: bool
        """
        return self.__is_immutable

    def sign_package(self, trust_key=None):
        """Sign a package with a key.

        An HMAC will be generated and the Zombiegram is marked as immutable.

        :note: Only possible when the object is still mutable, once signed no edits are possible

        :param bytestring trust_key: Key to hash the Zombiegram contents with
                                    If set to none, the Zombiegram with be signed with "\x00\x00\x00\x00"
        """
        if self.__is_immutable:
            raise DisallowedOperation(self.__is_immutable)
        self.__create_hmac(trust_key, self.__get_hmacless_bytestring())
        self.__bytestring_representation = self.get_bytestring_representation()

    def __get_hmacless_bytestring(self):
        def flag_encoder():
            tampered_shift = 2
            maintenance_shift = 3
            flags = 0
            flags |= self.priority
            flags |= (self.tampered_flag << tampered_shift)
            flags |= (self.maintenance_flag << maintenance_shift)
            return flags

        package = b""
        package += self.source_id.to_bytes(4, "big")
        package += self.seq_num.to_bytes(1, "big")
        package += flag_encoder().to_bytes(1, "big")
        for payload in self.payloads:
            package += _payload_opcode_list.index(type(payload)).to_bytes(1, "big")
            package += payload.get_bytestring_representation()

        return package

    def get_bytestring_representation(self):
        """Retrieve the bytestring representation of the Zombiegram object.
        If no previous :func:`~zombiegram.Zombiegram.sign_package` was called, the zombiegram will contain the default HMAC zero bytes

        :return: Bytestring representation of the current object
        :rtype: bytestring
        """
        # Check if a previous bytestring representation is present
        if self.__bytestring_representation:
            return self.__bytestring_representation

        hmac_part = None
        if self.hmac:
            try:
                hmac_part = self.hmac.to_bytes(4, "big")
            except:
                hmac_part = self.hmac[:4]
        else:
            hmac_part = self.__unsigned_hmac_default
        bytestring = hmac_part + self.__get_hmacless_bytestring()

        if self.__is_immutable and self.hmac:  # hmac has been set, thus the zombiegram has been signed, we can cache the bytestring
            self.__bytestring_representation = bytestring

        return bytestring

    def is_payload_trusted(self, trust_key):
        """Check payload integrity
        Zombiegram contents are hashed against the provided trust_key
        In case the HMACs are similar, we are dealing with a trusted source

        :note: Only works if a Zombiegram was previously signed with :func:`~zombiegram.Zombiegram.sign_package` (either manually or when imported from bytestring payload)

        :param bytearray trust_key: Key for hashing
        :rtype: boolean
        :raises DisallowedOperation: If the Zombiegram has not been signed yet.
        """
        if not self.__is_immutable:
            raise DisallowedOperation(self.__is_immutable)

        if not trust_key:
            return False

        hmac = self.__bytestring_representation[0:4]

        digester = None
        try:
            # TODO error capturing
            digester = hmaclib.new(key=trust_key, msg=self.__bytestring_representation[4:], digestmod=hashlib.sha256)
            self.__hmac = digester.digest()
        except TypeError:
            digester = hmaclib.new(key=trust_key.encode(), msg=self.__bytestring_representation[4:],
                                   digestmod=hashlib.sha256)
            self.__hmac = digester.digest()[:4]
        generated_hmac = digester.digest()[:4]

        return hmac == generated_hmac

    @staticmethod
    def _payloads_from_package(payload):
        """Import Zombiegram payloads from bytestring

        :param payload: bytrestring
        :return: List of payload objects if parsing succeeded
        :raises MalformedZombiegram: When a payload is corrupted
        """
        imported_payloads = []
        offset = Zombiegram.__header_size_bytes
        while True:
            opcode = payload[offset]
            if opcode < 0 or opcode > len(_payload_opcode_list):
                raise MalformedZombiegram(
                    "Package payload contains unknown opcode [{}] | Payload [{}]".format(opcode, str(payload)))

            payload_class = _payload_opcode_list[opcode]
            try:
                offset += 1
                payload_obj = payload_class.from_payload(payload, offset)
                offset += payload_class.size
                imported_payloads.append(payload_obj)
            except IndexError:
                raise MalformedZombiegram(
                    "Package payload contains corrupted data | Opcode [{}] | Payload [{}]".format(opcode, str(payload)))

            if offset >= len(payload) or payload_class in _no_piggyback_opcode_list:
                break
        return imported_payloads

    @staticmethod
    def from_package(payload):
        """Import Zombiegram from bytestring payload

        :param payload: bytestring
        :return: Zombiegram object
        :raises MalformedZombiegram: if the package size is smaller than or equal to the header size which would indicate no attached payload
        """

        def flag_decoder(flag):
            """Flag decoder
            :returns: tuple (priority, tampered, maintenance)
            """
            priority_mask = 3
            tampered_mask = 4
            tampered_shift = 2
            maintenance_mask = 8
            maintenance_shift = 3

            priority = flag & priority_mask
            tampered = bool((flag & tampered_mask) >> tampered_shift)
            maintenance = bool((flag & maintenance_mask) >> maintenance_shift)
            return priority, tampered, maintenance

        if len(payload) <= Zombiegram.__header_size_bytes:
            raise MalformedZombiegram(
                "Package size is smaller [{} bytes] than expected or equal to the header size [{} bytes] | Payload [{}]".format(
                    len(payload), Zombiegram.__header_size_bytes, str(payload)))
        hmac, source_id, seq_num, flags = struct.unpack("!IIBB", payload[0:10])
        flags = flag_decoder(flags)
        imported_payloads = Zombiegram._payloads_from_package(payload)
        return Zombiegram(hmac=hmac, source_id=source_id, seq_num=seq_num, priority_flag=flags[0],
                          tampered_flag=flags[1], maintenance_flag=flags[2], raw_payload=payload,
                          imported_payloads=imported_payloads)


############
# PAYLOADS #
############


class Payload:
    size = 0  # Size in bytes (without opcode)
    can_be_combined = True  # Flag which specifies if the payload can be combined with others

    def __init__(self):
        raise MethodNotImplementedException()

    def __str__(self):
        raise MethodNotImplementedException()

    def get_bytestring_representation(self):
        raise MethodNotImplementedException()

    def serialize_to_dict(self):
        return {}

    def get_size(self):
        return self.size

    @staticmethod
    def from_payload(payload, offset):
        raise MethodNotImplementedException()


class AcknowledgePayload(Payload):
    size = 5
    can_be_combined = False

    def __init__(self, source_id, seq_num):
        try:
            self.source_id = bytes_to_int(source_id)
        except TypeError:
            raise MalformedZombiegram("Source ID should be a bytestring or integer. | source_id [{}]".format(source_id))

        if not isinstance(seq_num, int) or seq_num > 255 or seq_num < 0:
            raise MalformedZombiegram(
                "Sequence number should represent an integer in the range [0,255] | Given [{}]".format(seq_num))
        self.seq_num = seq_num

    def __str__(self):
        output = "Acknowledgement payload {"
        output += "source_id [{}]".format(self.source_id)
        output += " | seq_num [{}]".format(self.seq_num)
        output += "}"
        return output

    def get_bytestring_representation(self):
        package = self.source_id.to_bytes(4, "big")
        package += self.seq_num.to_bytes(1, "big")
        return package

    def serialize_to_dict(self):
        return {
            "source_id": self.source_id,
            "seq_num": self.seq_num
        }

    @staticmethod
    def from_payload(payload, offset):
        source_id = struct.unpack_from("!I", payload, offset)
        source_id = source_id[0] # unpack_from always returns a tuple
        seq_num = payload[offset+4]
        return AcknowledgePayload(source_id, seq_num)


class DetectionPayload(Payload):
    size = 2
    can_be_combined = True

    def __init__(self, confidence_percentage, hitcounter):
        """Detection Payload

        Used for sensor elements that detect movement/presence of living creatures/objects. This payload is intentionally
        kept small as to keep urgence zombiegrams small. It contains 2 generic parameters which can give an broad idea of the
        detection event.

        :param confidence_percentage: An integer between 0 and 100 indicating the percentage of confidence the sensor has in its detection.
        :param hitcounter: An integer in the ranger [0,255] that indicates the amount of detections. Used in situations where a sensor temporarily withholds broadcasting the detection event for a better reading of possibly more detections.
        :raises MalformedZombiegram: When input parameters don't match the required ranges.
        """
        if not isinstance(confidence_percentage, int) or confidence_percentage < 0 or confidence_percentage > 100:
            raise MalformedZombiegram(
                "Confidence percentage should represent an integer in the range [0,100] | Given [{}]".format(
                    confidence_percentage))

        if not isinstance(hitcounter, int) or hitcounter < 0 or hitcounter > 255:
            raise MalformedZombiegram("Hitcounter should be in the range [0,255] | Given [{}]".format(hitcounter))

        self.confidence = confidence_percentage
        self.hitcounter = hitcounter

    def __str__(self):
        output = "Detection payload {"
        output += "confidence_percentage [{}]".format(self.confidence)
        output += " | hitcounter [{}]".format(self.hitcounter)
        output += "}"
        return output

    def get_bytestring_representation(self):
        package = self.confidence.to_bytes(1, "big")
        package += self.hitcounter.to_bytes(1, "big")
        return package

    def serialize_to_dict(self):
        return {
            "confidence_percentage": self.confidence,
            "hitcounter": self.hitcounter
        }

    @staticmethod
    def from_payload(payload, offset):
        confidence_percentage, hitcounter = struct.unpack_from("!BB", payload, offset)
        confidence_percentage = bytes_to_int(confidence_percentage)
        hitcounter = bytes_to_int(hitcounter)
        return DetectionPayload(confidence_percentage, hitcounter)


class UsmsPayload(Payload):
    __max_char_size = 70

    size = 0
    can_be_combined = False

    def __init__(self, ascii_text):
        """Ultra Short Message Service Payload

        Human Communication over long range.
        Every message has a maximum limit if 70 characters.

        :param str ascii_text:
        :raises UsmsSizeTooLarge: When the provided message exceeds the message size limit of 70 chars.
        """
        if len(ascii_text) > self.__max_char_size:
            raise UsmsSizeTooLarge(
                "{} chars given, maximum of {} allowed.".format(len(ascii_text), self.__max_char_size))

        self.ascii_payload = ascii_text
        self.usms_payload = usmslib.ascii_to_bytes(ascii_text)
        self.size = len(self.usms_payload)

    def __str__(self):
        output = "USMS payload {"
        output += "usms size in bytes [{}]".format(self.size)
        output += " | ascii [{}]".format(self.ascii_payload)
        output += " | usms [{}]".format(self.usms_payload)
        output += "}"
        return output

    def get_bytestring_representation(self):
        return self.usms_payload

    def serialize_to_dict(self):
        return {
            "ascii_text": self.ascii_payload
        }

    @staticmethod
    def from_payload(payload, offset):
        usms = usmslib.bytes_to_ascii(payload[offset:])
        return UsmsPayload(usms)


class DiagnosticPayload(Payload):
    size = 23
    can_be_combined = True
    __default_neighbor_id = b"\x00\x00\x00\x00"

    def __init__(self, gps_coordinates, best_neighbors, battery_status, network_role, is_sensor=False, is_router=False,
                 is_gateway=False, sensor_id=0):
        """Diagnostic information from network elements

        :param tuple gps_coordinates: Longitude and latitude as floats
        :param list best_neighbors: Three best neighbor source_IDs. The list can contain up to three items, less are allowed.
        :param int battery_status: Intenger in the range [0, 101] indicating the battery level of the network device. 101 is reserved for the "Unknown battery" state
        :param int network_role: Integer in the range [0,2]; respectively child, router and leader
        :param bool is_sensor: Device role; defaults to false
        :param bool is_router: Device role; defaults to false
        :param bool is_gateway: Device role; defaults to false
        :param int sensor_id: ID of the sensor, defaults to 0 which indicates no sensor being attached
        """
        if not isinstance(gps_coordinates, tuple) or not isinstance(gps_coordinates[0], float) or not isinstance(
                gps_coordinates[1], float):
            raise MalformedZombiegram(
                "GPS coordinates should be a tuple consisting of longitude and latitude | Given [{}]".format(
                    gps_coordinates))

        if not isinstance(best_neighbors, list):
            raise MalformedZombiegram(
                "Best Neighbors should be a list consisting of max 3 neighbors | Given [{}]".format(best_neighbors))

        if not isinstance(battery_status, int) or battery_status < 0 or battery_status > 101:
            raise MalformedZombiegram(
                "Battery status should be an integer between 0 and 100 | Given [{}]".format(battery_status))

        if not isinstance(network_role, int) or network_role < 0 or network_role > 2:
            raise MalformedZombiegram(
                "Network role should be an intenger in the range [0,2] | Given [{}]".format(network_role))

        if not isinstance(sensor_id, int) or network_role < 0 or network_role > 255:
            raise MalformedZombiegram(
                "Sensor ID should be an intenger in the range [0,255] | Given [{}]".format(sensor_id))

        if not isinstance(is_sensor, bool):
            raise MalformedZombiegram(
                "Device role [is_sensor] should be a boolean] | Given type [{}]".format(type(is_sensor)))

        if not isinstance(is_gateway, bool):
            raise MalformedZombiegram(
                "Device role [is_gateway] should be a boolean] | Given type [{}]".format(type(is_gateway)))

        if not isinstance(is_router, bool):
            raise MalformedZombiegram(
                "Device role [is_router] should be a boolean] | Given type [{}]".format(type(is_router)))

        self.gps_longitude = gps_coordinates[0]
        self.gps_latitude = gps_coordinates[1]
        self.best_neighbor_one = bytes_to_int(best_neighbors[0]) if len(best_neighbors) > 0 else None
        self.best_neighbor_two = bytes_to_int(best_neighbors[1]) if len(best_neighbors) > 1 else None
        self.best_neighbor_three = bytes_to_int(best_neighbors[2]) if len(best_neighbors) > 2 else None
        self.battery_status = battery_status
        self.network_role = network_role
        self.is_sensor = is_sensor
        self.is_router = is_router
        self.is_gateway = is_gateway
        self.sensor_id = sensor_id

    def __str__(self):
        output = "Diagnostic payload {"
        output += "GPS [{}° latitude,{}° longtitude]".format(self.gps_latitude, self.gps_longitude)
        output += " | neighbor_one [{}]".format(self.best_neighbor_one)
        output += " | neighbor_two [{}]".format(self.best_neighbor_two)
        output += " | neighbor_three [{}]".format(self.best_neighbor_three)
        output += " | battery_status [{}]".format(self.battery_status)
        output += " | network_role [{}]".format(self.network_role)
        output += " | is_sensor [{}]".format(self.is_sensor)
        output += " | is_router [{}]".format(self.is_router)
        output += " | is_gateway [{}]".format(self.is_gateway)
        output += " | sensor_id [{}]".format(self.sensor_id)
        output += "}"
        return output

    def get_bytestring_representation(self):
        def device_network_encoder():
            sensor_shift = 2
            router_shift = 3
            gateway_shift = 4
            roles = 0
            roles |= self.network_role
            roles |= (self.is_sensor << sensor_shift)
            roles |= (self.is_router << router_shift)
            roles |= (self.is_gateway << gateway_shift)
            return roles

        package = struct.pack("!ff", self.gps_latitude, self.gps_longitude)
        package += self.best_neighbor_one.to_bytes(4, "big") if self.best_neighbor_one else self.__default_neighbor_id
        package += self.best_neighbor_two.to_bytes(4, "big") if self.best_neighbor_two else self.__default_neighbor_id
        package += self.best_neighbor_three.to_bytes(4,
                                                     "big") if self.best_neighbor_three else self.__default_neighbor_id
        package += self.battery_status.to_bytes(1, "big")
        package += self.sensor_id.to_bytes(1, "big")
        package += device_network_encoder().to_bytes(1, "big")
        return package

    def serialize_to_dict(self):
        neighbors = []
        if self.best_neighbor_one:
            neighbors.append(self.best_neighbor_one)
        if self.best_neighbor_two:
            neighbors.append(self.best_neighbor_two)
        if self.best_neighbor_three:
            neighbors.append(self.best_neighbor_three)
        return {
            "gps_coordinates": (self.gps_latitude, self.gps_longitude),
            "best_neighbors": neighbors,
            "battery_status": self.battery_status,
            "network_role": self.network_role,
            "is_sensor": self.is_sensor,
            "is_router": self.is_router,
            "is_gateway": self.is_gateway,
            "sensor_id": self.sensor_id
        }

    @staticmethod
    def from_payload(payload, offset):
        def device_network_decoder(roles):
            """Roles decoder
            :returns: tuple (network role, is sensor, is router, is gateway)
            """
            network_mask = 3
            is_sensor_mask = 4
            is_sensor_shift = 2
            is_router_mask = 8
            is_router_shift = 3
            is_gateway_mask = 16
            is_gateway_shift = 4

            network_role = roles & network_mask
            is_sensor = bool((roles & is_sensor_mask) >> is_sensor_shift)
            is_router = bool((roles & is_router_mask) >> is_router_shift)
            is_gateway = bool((roles & is_gateway_mask) >> is_gateway_shift)

            return network_role, is_sensor, is_router, is_gateway

        gps_long, gps_lat, neighbor_one, neighbor_two, neighbor_three, battery_status, sensor_id, roles = struct.unpack_from(
            "!ffIIIBBB", payload, offset)
        network_role, is_sensor, is_router, is_gateway = device_network_decoder(roles)
        neighbors = []
        if neighbor_one: neighbors.append(neighbor_one)
        if neighbor_two: neighbors.append(neighbor_two)
        if neighbor_three: neighbors.append(neighbor_three)
        return DiagnosticPayload((gps_long, gps_lat), neighbors, battery_status, network_role, is_sensor, is_router,
                                 is_gateway, sensor_id)


class NetworkChange(Payload):
    size = 4
    can_be_combined = False

    def __init__(self, trust_key=None, signed_source_id=None):
        if trust_key:
            message = b'\x80}'
            self.signed_source_id = None
            try:
                digester = hmaclib.new(key=trust_key, msg=message, digestmod=hashlib.sha256)
                self.signed_source_id = digester.digest()[:4]
            except TypeError:
                digester = hmaclib.new(key=trust_key.encode(), msg=message, digestmod=hashlib.sha256)
                self.signed_source_id = digester.digest()[:4]

            if not self.signed_source_id:
                raise MalformedZombiegram("Could not create Network Change payload.")
        elif signed_source_id:
            self.signed_source_id = signed_source_id
        else:
            raise MalformedZombiegram("No trust key or signed source given.")

    def __str__(self):
        output = "Network Change payload {"
        output += "signed_source_id [{}]".format(self.signed_source_id)
        output += "}"
        return output

    def get_bytestring_representation(self):
        return self.signed_source_id

    def serialize_to_dict(self):
        return {}

    @staticmethod
    def from_payload(payload, offset):
        signed_source = payload[offset:(offset + 4)]
        return NetworkChange(signed_source_id=signed_source)


# List allows us to look for Opcodes (= index of the payload item) and for payloads (indexing)
# Please do not alter the order of items
_payload_opcode_list = [
    AcknowledgePayload,  # 0
    NetworkChange,  # 1
    DetectionPayload,  # 2
    UsmsPayload,  # 3
    DiagnosticPayload  # 4
]

_no_piggyback_opcode_list = []
for payload in _payload_opcode_list:
    if not payload.can_be_combined:
        _no_piggyback_opcode_list.append(payload)

#########
# DEBUG #
#########

if __name__ == '__main__':
    # zombiegram_payload = b"\x0A\x0A\x0A\x0A\x0B\x0B\x0B\x0B\x01\x0B\00"
    # a = Zombiegram.from_payload(zombiegram_payload)
    # print(a)
    #
    # print("\n")
    # print(_no_piggyback_opcode_list)
    test = Zombiegram(source_id=b"\x00\x00\x00\x03", seq_num=2, priority_flag=3, tampered_flag=True,
                      maintenance_flag=False)
    # print(test)
    # print(Zombiegram.from_payload(test.get_bytestring_representation() + b"\x00"))
    # test.sign_package("heheh")
    # print(Zombiegram.from_payload(test.get_bytestring_representation() + b"\x00"))
    #
    # print(test.is_payload_trusted(b"heheh"))
    # b = Zombiegram.from_payload(test.create_package(b"hello world") + b"\x00")
    # print(b.is_payload_trusted(b""))
    # b.source_id = b"hello"
    # print(b)

    diag = DiagnosticPayload((1.1, 2.2), [b"\x11\x11\x11\x11"], 97, 1, False, False, False, 112)
    # print(diag)
    # print(diag.get_bytestring_representation())
    # print(DiagnosticPayload.from_payload(diag.get_bytestring_representation(), 0))

    detect = DetectionPayload(50, 1)
    # print(detect)
    # print(DetectionPayload.from_payload(detect.get_bytestring_representation(), 0))

    us = UsmsPayload("a" * 60)
    # print(us)
    # print(UsmsPayload.from_payload(us.get_bytestring_representation(), 0))

    # print(type(us) in _payload_opcode_list)
    # print(_payload_opcode_list.index(type(us)))

    ack = AcknowledgePayload(b"\x00\x00\x00\x03", 255)

    nc = NetworkChange("test")

    # test.add_payload(us)
    # test.add_payload(detect)
    # test.add_payload(diag)
    # test.add_payload(diag)
    test.add_payload(ack)
    # test.add_payload(nc)
    test.sign_package("test")
    # print(test.get_bytestring_representation())
    # print()
    print(test.serialize_to_dict("test"))

    # imported = Zombiegram.from_package(test.get_bytestring_representation())
    # print(imported.is_payload_trusted("test"))
    # print(imported)
    # print(nc.signed_source_id == imported.payloads[0].signed_source_id)

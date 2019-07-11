"""Ultra Short Message System
6bit based character coding

Developer note: Only works on 32 bit integer processors (some adjustments needed for bigger/smaller scales)
"""

__usms_chars = [None]
__usms_chars += [chr(i) for i in range(ord("a"), ord("z") + 1)]
__usms_chars += [chr(i) for i in range(ord("0"), ord("9") + 1)]
__usms_chars += list(",?;.:/\()[]!&|@#\'\"%*-_+=<> ")
if len(__usms_chars) > 2**6:
    raise RuntimeError("USMS system dictionary contains more characters than its 6bit encoding system can support!")


class UsmsCharacterOutOfRange(Exception):
    pass


def print_usms_table():
    """Pretty print all possible characters in our 6bit USMS alphabet"""
    print("+-----+------+")
    print("| DEC | CHAR |")
    print("+=====+======+")
    for i in range(1, len(__usms_chars)):
        print("| {}{}  | {}    |".format("" if i > 9 else " ", i, __usms_chars[i]))
    print("+-----+------+")


def bytes_to_ascii(bytestring):
    """Decode a 6-bit USMS bytestring to ASCII string representation

    :param bytestring: 6bit encoded USMS bytestring (with end-padding)
    :return: ASCII string
    """
    pattern = [(2, 3), (4, 15), (6, 63)]  # (bits to shift, rest bit pattern)
    pattern_index = 0
    ascii_output = []
    rest_bits = 0
    for byte in bytestring:
        six_bit_int_rep = (byte >> pattern[pattern_index][0]) | (rest_bits << (8 - pattern[pattern_index][0]))
        rest_bits = byte & pattern[pattern_index][1]

        if six_bit_int_rep not in range(0, len(__usms_chars)):
            raise UsmsCharacterOutOfRange("Unknown character index [{}]".format(str(six_bit_int_rep)))

        if __usms_chars[six_bit_int_rep] is not None:
            ascii_output.append(__usms_chars[six_bit_int_rep])

        if pattern_index == 2 and __usms_chars[rest_bits] is not None:
            if rest_bits not in range(0, len(__usms_chars)):
                raise UsmsCharacterOutOfRange("Unknown character index [{}]".format(str(rest_bits)))
            ascii_output.append(__usms_chars[rest_bits])

        pattern_index = (pattern_index + 1) % 3
    return "".join(ascii_output)


def ascii_to_bytes(asciistring):
    """Encode an ASCII string to a 6bit encoded USMS bytestring with padding

    :param asciistring: ASCII string
    :return: 6bit encoded USMS bytestring
    """
    byte_output = []
    pattern = [(2, 3, 4), (4, 15, 2), (6, 0, 0)]  # (bits to shift, rest bit pattern)
    pattern_index = 0
    for i in range(0, len(asciistring)):
        int_rep = __usms_chars.index(asciistring[i]) << pattern[pattern_index][0] & 255
        if pattern_index < 2:
            next_int_rest = ((__usms_chars.index(asciistring[i + 1]) >> pattern[pattern_index][2]) if (i + 1) < len(asciistring) else 0) & pattern[pattern_index][1]
            int_rep |= next_int_rest
        else:
            i += 1
        byte_output.append(int_rep)

        pattern_index = (pattern_index + 1) % 3
    return bytes(byte_output)


if __name__ == "__main__":
    print_usms_table()
    print(ascii_to_bytes("abcdefghijklmnopqrstuvwxyz"))
    print(bytes_to_ascii(b'\x04 \xc0\x10Q\x80\x1c\x82@(\xb3\x004\xe3\xc0A\x14\x80ME@Yv\x00e\xa0'))
    print(ascii_to_bytes("eeeeee"))
    print(bytes_to_ascii(b'\x14Q@\x14Q@'))


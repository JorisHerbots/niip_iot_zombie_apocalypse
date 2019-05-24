import pycom

class RGBLed:
    """Static class to control the build in RGB led of the PyCom."""

    __state = False
    __ledColor = (255,0,0)

    # fading parameters
    __fadeColors = [255, 0, 0]
    __fadeIndex = 0
    __colorIndexInc = 1
    __colorIndexDec = 0

    @staticmethod
    def color(color=None):
        """Get or set the color of the led. If a color is provided, the color will be set.
        If the led is turned of the color will be stored but not displayed.

        Parameters
        ----------
        color : (integer, integer, integer)
            The new color of the led. The format of the color is (Red, Green, Blue). Each integer must be a number between [0,255].

        Returns
        -------
        color : (integer, integer, integer)
            The color of the led. The format of the color is (Red, Green, Blue). Each integer must be a number between [0,255].

        """
        if color:
            RGBLed.__ledColor = color
            if (RGBLed.__state):
                colorHex = '%02x%02x%02x' % (RGBLed.__ledColor[0], RGBLed.__ledColor[1], RGBLed.__ledColor[2])
                pycom.rgbled(int(colorHex, 16))

        return RGBLed.__ledColor

    # turn the led on
    @staticmethod
    def on():
        """Turn the led on.

        Parameters
        ----------

        Returns
        -------

        """
        RGBLed.__state = True
        RGBLed.color(RGBLed.__ledColor)

    # turn the led off
    @staticmethod
    def off():
        """Turn the led off.

        Parameters
        ----------

        Returns
        -------

        """
        RGBLed.__state = False
        pycom.rgbled(0)

    @staticmethod
    def nextFadeColor():
        """Go to the next color in the fading effect.

        Parameters
        ----------

        Returns
        -------

        """
        if (RGBLed.__fadeIndex >= 255):
            RGBLed.__fadeIndex = 0
            RGBLed.__colorIndexDec += 1

            if (RGBLed.__colorIndexDec == 3):
                RGBLed.__colorIndexDec = 0

            if (RGBLed.__colorIndexDec == 2):
                RGBLed.__colorIndexInc = 0
            else:
                RGBLed.__colorIndexInc = RGBLed.__colorIndexDec + 1

        RGBLed.__fadeColors[RGBLed.__colorIndexDec] -= 1
        RGBLed.__fadeColors[RGBLed.__colorIndexInc] += 1
        RGBLed.color((RGBLed.__fadeColors[0], RGBLed.__fadeColors[1], RGBLed.__fadeColors[2]))

        RGBLed.__fadeIndex += 1

"""Module for tapo-branded smart bulbs (L5**)."""

from __future__ import annotations

from ..bulb import Bulb
from ..exceptions import KasaException
from ..iot.iotbulb import HSV, BulbPreset, ColorTempRange
from .smartdevice import SmartDevice

AVAILABLE_EFFECTS = {
    "L1": "Party",
    "L2": "Relax",
}


class SmartBulb(SmartDevice, Bulb):
    """Representation of a TP-Link Tapo Bulb.

    Documentation TBD. See :class:`~kasa.iot.Bulb` for now.
    """

    @property
    def is_color(self) -> bool:
        """Whether the bulb supports color changes."""
        # TODO: this makes an assumption that only color bulbs report this
        return "hue" in self._info

    @property
    def is_dimmable(self) -> bool:
        """Whether the bulb supports brightness changes."""
        return "Brightness" in self.modules

    @property
    def is_variable_color_temp(self) -> bool:
        """Whether the bulb supports color temperature changes."""
        ct = self._info.get("color_temp_range")
        # L900 reports [9000, 9000] even when it doesn't support changing the ct
        return ct is not None and ct[0] != ct[1]

    @property
    def valid_temperature_range(self) -> ColorTempRange:
        """Return the device-specific white temperature range (in Kelvin).

        :return: White temperature range in Kelvin (minimum, maximum)
        """
        if not self.is_variable_color_temp:
            raise KasaException("Color temperature not supported")

        ct_range = self._info.get("color_temp_range", [0, 0])
        return ColorTempRange(min=ct_range[0], max=ct_range[1])

    @property
    def has_effects(self) -> bool:
        """Return True if the device supports effects."""
        return "dynamic_light_effect_enable" in self._info

    @property
    def effect(self) -> dict:
        """Return effect state.

        This follows the format used by SmartLightStrip.

        Example:
            {'brightness': 50,
             'custom': 0,
             'enable': 0,
             'id': '',
             'name': ''}
        """
        # If no effect is active, dynamic_light_effect_id does not appear in info
        current_effect = self._info.get("dynamic_light_effect_id", "")
        data = {
            "brightness": self.brightness,
            "enable": current_effect != "",
            "id": current_effect,
            "name": AVAILABLE_EFFECTS.get(current_effect, ""),
        }

        return data

    @property
    def effect_list(self) -> list[str] | None:
        """Return built-in effects list.

        Example:
            ['Party', 'Relax', ...]
        """
        return list(AVAILABLE_EFFECTS.keys()) if self.has_effects else None

    @property
    def hsv(self) -> HSV:
        """Return the current HSV state of the bulb.

        :return: hue, saturation and value (degrees, %, %)
        """
        if not self.is_color:
            raise KasaException("Bulb does not support color.")

        h, s, v = (
            self._info.get("hue", 0),
            self._info.get("saturation", 0),
            self._info.get("brightness", 0),
        )

        return HSV(hue=h, saturation=s, value=v)

    @property
    def color_temp(self) -> int:
        """Whether the bulb supports color temperature changes."""
        if not self.is_variable_color_temp:
            raise KasaException("Bulb does not support colortemp.")

        return self._info.get("color_temp", -1)

    @property
    def brightness(self) -> int:
        """Return the current brightness in percentage."""
        if not self.is_dimmable:  # pragma: no cover
            raise KasaException("Bulb is not dimmable.")

        return self._info.get("brightness", -1)

    async def set_hsv(
        self,
        hue: int,
        saturation: int,
        value: int | None = None,
        *,
        transition: int | None = None,
    ) -> dict:
        """Set new HSV.

        Note, transition is not supported and will be ignored.

        :param int hue: hue in degrees
        :param int saturation: saturation in percentage [0,100]
        :param int value: value in percentage [0, 100]
        :param int transition: transition in milliseconds.
        """
        if not self.is_color:
            raise KasaException("Bulb does not support color.")

        if not isinstance(hue, int) or not (0 <= hue <= 360):
            raise ValueError(f"Invalid hue value: {hue} (valid range: 0-360)")

        if not isinstance(saturation, int) or not (0 <= saturation <= 100):
            raise ValueError(
                f"Invalid saturation value: {saturation} (valid range: 0-100%)"
            )

        if value is not None:
            self._raise_for_invalid_brightness(value)

        request_payload = {
            "color_temp": 0,  # If set, color_temp takes precedence over hue&sat
            "hue": hue,
            "saturation": saturation,
        }
        # The device errors on invalid brightness values.
        if value is not None:
            request_payload["brightness"] = value

        return await self.protocol.query({"set_device_info": {**request_payload}})

    async def set_color_temp(
        self, temp: int, *, brightness=None, transition: int | None = None
    ) -> dict:
        """Set the color temperature of the device in kelvin.

        Note, transition is not supported and will be ignored.

        :param int temp: The new color temperature, in Kelvin
        :param int transition: transition in milliseconds.
        """
        # TODO: Note, trying to set brightness at the same time
        #  with color_temp causes error -1008
        if not self.is_variable_color_temp:
            raise KasaException("Bulb does not support colortemp.")

        valid_temperature_range = self.valid_temperature_range
        if temp < valid_temperature_range[0] or temp > valid_temperature_range[1]:
            raise ValueError(
                "Temperature should be between {} and {}, was {}".format(
                    *valid_temperature_range, temp
                )
            )

        return await self.protocol.query({"set_device_info": {"color_temp": temp}})

    def _raise_for_invalid_brightness(self, value: int):
        """Raise error on invalid brightness value."""
        if not isinstance(value, int) or not (1 <= value <= 100):
            raise ValueError(f"Invalid brightness value: {value} (valid range: 1-100%)")

    async def set_brightness(
        self, brightness: int, *, transition: int | None = None
    ) -> dict:
        """Set the brightness in percentage.

        Note, transition is not supported and will be ignored.

        :param int brightness: brightness in percent
        :param int transition: transition in milliseconds.
        """
        if not self.is_dimmable:  # pragma: no cover
            raise KasaException("Bulb is not dimmable.")

        self._raise_for_invalid_brightness(brightness)

        return await self.protocol.query(
            {"set_device_info": {"brightness": brightness}}
        )

    async def set_effect(
        self,
        effect: str,
        *,
        brightness: int | None = None,
        transition: int | None = None,
    ) -> None:
        """Set an effect on the device."""
        raise NotImplementedError()

    @property
    def presets(self) -> list[BulbPreset]:
        """Return a list of available bulb setting presets."""
        return []

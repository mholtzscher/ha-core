"""Motor speed support for Xiaomi Mi Air Humidifier."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import callback

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    FEATURE_FLAGS_AIRFRESH,
    FEATURE_FLAGS_AIRHUMIDIFIER_CA4,
    FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    FEATURE_FLAGS_AIRPURIFIER_2S,
    FEATURE_FLAGS_AIRPURIFIER_MIIO,
    FEATURE_FLAGS_AIRPURIFIER_MIOT,
    FEATURE_FLAGS_AIRPURIFIER_PRO,
    FEATURE_FLAGS_AIRPURIFIER_PRO_V7,
    FEATURE_FLAGS_AIRPURIFIER_V1,
    FEATURE_FLAGS_AIRPURIFIER_V3,
    FEATURE_SET_FAN_LEVEL,
    FEATURE_SET_FAVORITE_LEVEL,
    FEATURE_SET_MOTOR_SPEED,
    FEATURE_SET_VOLUME,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODEL_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V1,
    MODEL_AIRPURIFIER_V3,
    MODELS_PURIFIER_MIIO,
    MODELS_PURIFIER_MIOT,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_FAN_LEVEL = "fan_level"
ATTR_FAVORITE_LEVEL = "favorite_level"
ATTR_MOTOR_SPEED = "motor_speed"
ATTR_VOLUME = "volume"


@dataclass
class XiaomiMiioNumberDescription(NumberEntityDescription):
    """A class that describes number entities."""

    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    available_with_device_off: bool = True
    method: str | None = None


NUMBER_TYPES = {
    FEATURE_SET_MOTOR_SPEED: XiaomiMiioNumberDescription(
        key=ATTR_MOTOR_SPEED,
        name="Motor Speed",
        icon="mdi:fast-forward-outline",
        unit_of_measurement="rpm",
        min_value=200,
        max_value=2000,
        step=10,
        available_with_device_off=False,
        method="async_set_motor_speed",
    ),
    FEATURE_SET_FAVORITE_LEVEL: XiaomiMiioNumberDescription(
        key=ATTR_FAVORITE_LEVEL,
        name="Favorite Level",
        icon="mdi:star-cog",
        min_value=0,
        max_value=17,
        step=1,
        method="async_set_favorite_level",
    ),
    FEATURE_SET_FAN_LEVEL: XiaomiMiioNumberDescription(
        key=ATTR_FAN_LEVEL,
        name="Fan Level",
        icon="mdi:fan",
        min_value=1,
        max_value=3,
        step=1,
        method="async_set_fan_level",
    ),
    FEATURE_SET_VOLUME: XiaomiMiioNumberDescription(
        key=ATTR_VOLUME,
        name="Volume",
        icon="mdi:volume-high",
        min_value=0,
        max_value=100,
        step=1,
        method="async_set_volume",
    ),
}

MODEL_TO_FEATURES_MAP = {
    MODEL_AIRHUMIDIFIER_CA1: FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    MODEL_AIRHUMIDIFIER_CA4: FEATURE_FLAGS_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1: FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    MODEL_AIRPURIFIER_2S: FEATURE_FLAGS_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_PRO: FEATURE_FLAGS_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7: FEATURE_FLAGS_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V1: FEATURE_FLAGS_AIRPURIFIER_V1,
    MODEL_AIRPURIFIER_V3: FEATURE_FLAGS_AIRPURIFIER_V3,
    MODEL_AIRFRESH_VA2: FEATURE_FLAGS_AIRFRESH,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Selectors from a config entry."""
    entities = []
    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return
    model = config_entry.data[CONF_MODEL]
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]

    if model in MODEL_TO_FEATURES_MAP:
        features = MODEL_TO_FEATURES_MAP[model]
    elif model in MODELS_PURIFIER_MIIO:
        features = FEATURE_FLAGS_AIRPURIFIER_MIIO
    elif model in MODELS_PURIFIER_MIOT:
        features = FEATURE_FLAGS_AIRPURIFIER_MIOT
    else:
        return

    for feature, description in NUMBER_TYPES.items():
        if feature & features:
            entities.append(
                XiaomiNumberEntity(
                    f"{config_entry.title} {description.name}",
                    device,
                    config_entry,
                    f"{description.key}_{config_entry.unique_id}",
                    hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
                    description,
                )
            )

    async_add_entities(entities)


class XiaomiNumberEntity(XiaomiCoordinatedMiioEntity, NumberEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._attr_min_value = description.min_value
        self._attr_max_value = description.max_value
        self._attr_step = description.step
        self._attr_value = self._extract_value_from_attribute(
            coordinator.data, description.key
        )
        self.entity_description = description

    @property
    def available(self):
        """Return the number controller availability."""
        if (
            super().available
            and not self.coordinator.data.is_on
            and not self.entity_description.available_with_device_off
        ):
            return False
        return super().available

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def async_set_value(self, value):
        """Set an option of the miio device."""
        method = getattr(self, self.entity_description.method)
        if await method(value):
            self._attr_value = value
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        self._attr_value = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        self.async_write_ha_state()

    async def async_set_motor_speed(self, motor_speed: int = 400):
        """Set the target motor speed."""
        return await self._try_command(
            "Setting the target motor speed of the miio device failed.",
            self._device.set_speed,
            motor_speed,
        )

    async def async_set_favorite_level(self, level: int = 1):
        """Set the favorite level."""
        return await self._try_command(
            "Setting the favorite level of the miio device failed.",
            self._device.set_favorite_level,
            level,
        )

    async def async_set_fan_level(self, level: int = 1):
        """Set the fan level."""
        return await self._try_command(
            "Setting the favorite level of the miio device failed.",
            self._device.set_fan_level,
            level,
        )

    async def async_set_volume(self, volume: int = 50):
        """Set the volume."""
        return await self._try_command(
            "Setting the volume of the miio device failed.",
            self._device.set_volume,
            volume,
        )

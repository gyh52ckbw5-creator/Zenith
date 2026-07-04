"""Akıllı ev otomasyonu ve IoT entegrasyonu.

Home Assistant, MQTT, ve diğer akıllı ev protokollerini destekler.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class DeviceType(Enum):
    """Akıllı cihaz türleri."""
    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    CAMERA = "camera"
    SPEAKER = "speaker"
    SENSOR = "sensor"
    FAN = "fan"
    BLINDS = "blinds"
    PLUG = "plug"


@dataclass
class SmartDevice:
    """Akıllı bir cihaz."""
    id: str
    name: str
    device_type: DeviceType
    state: Any
    controllable: bool = True
    attributes: dict[str, Any] | None = None


class SmartHomeHub:
    """Akıllı ev cihazlarını yönet."""

    def __init__(self):
        self.devices: dict[str, SmartDevice] = {}
        self.integrations: dict[str, Any] = {}  # Home Assistant, MQTT, vb.
        self.automation_rules: list[AutomationRule] = []

    def add_device(self, device: SmartDevice) -> bool:
        """Cihaz ekle."""
        if device.id in self.devices:
            return False
        self.devices[device.id] = device
        return True

    def remove_device(self, device_id: str) -> bool:
        """Cihazı kaldır."""
        if device_id not in self.devices:
            return False
        del self.devices[device_id]
        return True

    def get_device(self, device_id: str) -> SmartDevice | None:
        """Cihazı al."""
        return self.devices.get(device_id)

    def get_devices_by_type(self, device_type: DeviceType) -> list[SmartDevice]:
        """Tür'e göre cihazları al."""
        return [d for d in self.devices.values() if d.device_type == device_type]

    async def control_device(self, device_id: str, command: str, value: Any = None) -> bool:
        """Cihazı kontrol et."""
        device = self.get_device(device_id)
        if not device or not device.controllable:
            return False

        # Komut türüne göre işle
        if command == "turn_on":
            device.state = True
        elif command == "turn_off":
            device.state = False
        elif command == "set_value":
            device.state = value
        elif command == "toggle":
            device.state = not device.state
        else:
            return False

        return True

    def list_devices(self) -> list[dict[str, Any]]:
        """Tüm cihazları listele."""
        return [
            {
                "id": d.id,
                "name": d.name,
                "type": d.device_type.value,
                "state": d.state,
                "controllable": d.controllable,
            }
            for d in self.devices.values()
        ]

    def add_automation_rule(self, rule: AutomationRule) -> None:
        """Otomasyon kuralı ekle."""
        self.automation_rules.append(rule)

    async def check_automations(self) -> None:
        """Otomasyon kurallarını kontrol et ve çalıştır."""
        for rule in self.automation_rules:
            if rule.should_trigger(self.devices):
                await rule.execute(self)


@dataclass
class AutomationRule:
    """Otomasyon kuralı."""
    name: str
    trigger_condition: Callable[[dict[str, SmartDevice]], bool]
    actions: list[tuple[str, str, Any]]  # (device_id, command, value)

    def should_trigger(self, devices: dict[str, SmartDevice]) -> bool:
        """Kural tetiklenecek mi?"""
        return self.trigger_condition(devices)

    async def execute(self, hub: SmartHomeHub) -> None:
        """Kuralı çalıştır."""
        for device_id, command, value in self.actions:
            await hub.control_device(device_id, command, value)

"""MechWarrior Online loadout string codec.

Port of the reference `public/mwo-codec.js`. The format is a little-endian
6-bit alphabet followed by ordered component sections. This module only handles
the wire format — validating the decoded ids against real mech and equipment
data is the caller's job.
"""
from typing import Any, Dict, List, NamedTuple, Optional

ALPHABET = "0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmno"
_DECODE = {character: index for index, character in enumerate(ALPHABET)}
MIN_LENGTH = 36


class _Section(NamedTuple):
    name: str
    terminator: str


# Section order is part of the wire format and must not be reordered.
COMPONENTS = (
    _Section("centre_torso", "p"),
    _Section("right_torso", "q"),
    _Section("left_torso", "r"),
    _Section("left_arm", "s"),
    _Section("right_arm", "t"),
    _Section("left_leg", "u"),
    _Section("right_leg", "v"),
    _Section("head", "w"),
)

REAR_ARMOR_COMPONENTS = ("centre_torso", "left_torso", "right_torso")


class MwoCodecError(ValueError):
    """Raised when a loadout code is malformed or a value cannot be encoded."""


def encode_value(value: Any, min_characters: int, max_characters: Optional[int] = None) -> str:
    if max_characters is None:
        max_characters = min_characters
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise MwoCodecError("Cannot encode invalid value: {0!r}".format(value))
    if value < 0:
        raise MwoCodecError("Cannot encode invalid value: {0!r}".format(value))

    remainder = value
    encoded = ""
    for _ in range(min_characters):
        encoded += ALPHABET[remainder & 0x3F]
        remainder //= 64
    while remainder > 0 and len(encoded) < max_characters:
        encoded += ALPHABET[remainder & 0x3F]
        remainder //= 64
    if remainder > 0:
        raise MwoCodecError("Value is too large to encode: {0}".format(value))
    return encoded


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text
        self.position = 0

    def peek(self) -> Optional[str]:
        if self.position >= len(self.text):
            return None
        return self.text[self.position]

    def read_exactly(self, character_count: int) -> int:
        value = 0
        for index in range(character_count):
            character = self.peek()
            bits = _DECODE.get(character) if character is not None else None
            if bits is None:
                raise MwoCodecError(
                    "Unexpected character at {0}: {1}".format(
                        self.position + 1, character if character is not None else "end of code"
                    )
                )
            value += bits * (64 ** index)
            self.position += 1
        return value

    def read_available(self, max_characters: int) -> int:
        value = 0
        read_count = 0
        while read_count < max_characters:
            character = self.peek()
            bits = _DECODE.get(character) if character is not None else None
            if bits is None:
                break
            value += bits * (64 ** read_count)
            self.position += 1
            read_count += 1
        if not read_count:
            raise MwoCodecError("Expected an encoded value at {0}".format(self.position + 1))
        return value


def decode(code: Any) -> Dict[str, Any]:
    """Decode an MWO loadout code into its raw chassis / upgrade / component ids."""
    text = str(code or "").strip()
    if len(text) < MIN_LENGTH or text[0] != "A":
        raise MwoCodecError("This is not a supported MWO loadout code.")

    reader = _Reader(text)
    reader.position = 1
    chassis_id = reader.read_exactly(2)
    armor_structure = reader.read_exactly(1)
    heatsinks_guidance = reader.read_exactly(1)
    actuator_state = reader.read_exactly(1)
    is_omni = bool(heatsinks_guidance & 0x8)

    components: Dict[str, Dict[str, Any]] = {}
    for section in COMPONENTS:
        component: Dict[str, Any] = {
            "armor": reader.read_exactly(2),
            "omnipod": None,
            "item_ids": [],
        }
        if section.name != "centre_torso" and is_omni:
            component["omnipod"] = reader.read_available(6)
        while reader.peek() == "|":
            reader.position += 1
            component["item_ids"].append(reader.read_available(6))
        terminator = reader.peek()
        if terminator != section.terminator:
            raise MwoCodecError(
                "Malformed {0} section: expected {1}, found {2}".format(
                    section.name,
                    section.terminator,
                    terminator if terminator is not None else "end of code",
                )
            )
        reader.position += 1
        components[section.name] = component

    rear_armor = {name: reader.read_exactly(2) for name in REAR_ARMOR_COMPONENTS}

    if reader.position != len(text):
        raise MwoCodecError("Unexpected trailing data at {0}".format(reader.position + 1))

    return {
        "chassis_id": chassis_id,
        "is_omni": is_omni,
        "actuator_state": actuator_state,
        "upgrades": {
            "armor_type": armor_structure & 0x7,
            "structure_type": armor_structure >> 3,
            "heat_sink_type": (heatsinks_guidance & 0x7) >> 1,
            "artemis": bool(heatsinks_guidance & 0x1),
        },
        "components": components,
        "rear_armor": rear_armor,
    }


def encode(loadout: Dict[str, Any]) -> str:
    """Encode a decoded-shape loadout dict back into an MWO loadout code."""
    is_omni = bool(loadout.get("is_omni"))
    upgrades: Dict[str, Any] = loadout.get("upgrades") or {}

    code = "A"
    code += encode_value(loadout.get("chassis_id") or 0, 2)
    code += encode_value(
        (int(upgrades.get("structure_type") or 0) << 3) | int(upgrades.get("armor_type") or 0),
        1,
    )
    code += encode_value(
        (int(upgrades.get("heat_sink_type") or 0) << 1)
        | (1 if upgrades.get("artemis") else 0)
        | (0x8 if is_omni else 0),
        1,
    )
    code += encode_value(loadout.get("actuator_state") or 0, 1)

    components: Dict[str, Any] = loadout.get("components") or {}
    for section in COMPONENTS:
        component: Dict[str, Any] = components.get(section.name) or {}
        code += encode_value(component.get("armor") or 0, 2)
        if section.name != "centre_torso" and is_omni:
            omnipod = component.get("omnipod")
            try:
                omnipod = int(omnipod)
            except (TypeError, ValueError):
                omnipod = 0
            if omnipod <= 0:
                raise MwoCodecError("Missing omnipod for {0}".format(section.name))
            code += encode_value(omnipod, 3, 6)
        for item_id in component.get("item_ids") or ():
            code += "|" + encode_value(item_id, 1, 6)
        code += section.terminator

    rear_armor: Dict[str, Any] = loadout.get("rear_armor") or {}
    for name in REAR_ARMOR_COMPONENTS:
        code += encode_value(rear_armor.get(name) or 0, 2)
    return code


def component_names() -> List[str]:
    return [section.name for section in COMPONENTS]

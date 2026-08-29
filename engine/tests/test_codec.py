"""MWO loadout code round-trips."""
import pytest

from omnibay import codec


def _sample_loadout(is_omni=False):
    components = {}
    for index, section in enumerate(codec.COMPONENTS):
        components[section.name] = {
            "armor": 10 + index * 3,
            "omnipod": (30000 + index) if (is_omni and section.name != "centre_torso") else None,
            "item_ids": [1000 + index, 2000 + index],
        }
    return {
        "chassis_id": 42,
        "is_omni": is_omni,
        "actuator_state": 3,
        "upgrades": {
            "armor_type": 2,
            "structure_type": 1,
            "heat_sink_type": 1,
            "artemis": True,
        },
        "components": components,
        "rear_armor": {"centre_torso": 9, "left_torso": 5, "right_torso": 5},
    }


@pytest.mark.parametrize("is_omni", [False, True])
def test_encode_decode_round_trip(is_omni):
    loadout = _sample_loadout(is_omni)
    decoded = codec.decode(codec.encode(loadout))

    assert decoded["chassis_id"] == loadout["chassis_id"]
    assert decoded["is_omni"] == is_omni
    assert decoded["actuator_state"] == loadout["actuator_state"]
    assert decoded["upgrades"] == loadout["upgrades"]
    assert decoded["rear_armor"] == loadout["rear_armor"]
    for name, component in loadout["components"].items():
        assert decoded["components"][name]["armor"] == component["armor"]
        assert decoded["components"][name]["item_ids"] == component["item_ids"]
        assert decoded["components"][name]["omnipod"] == component["omnipod"]


def test_codes_start_with_a_and_meet_minimum_length():
    code = codec.encode(_sample_loadout())
    assert code.startswith("A")
    assert len(code) >= codec.MIN_LENGTH


def test_section_terminators_appear_in_wire_order():
    code = codec.encode(_sample_loadout())
    positions = [code.index(section.terminator) for section in codec.COMPONENTS]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    "bad",
    ["", "not-a-code", "B" + "0" * 40, "A" + "0" * 5],
)
def test_malformed_codes_are_rejected(bad):
    with pytest.raises(codec.MwoCodecError):
        codec.decode(bad)


def test_trailing_data_is_rejected():
    code = codec.encode(_sample_loadout())
    with pytest.raises(codec.MwoCodecError):
        codec.decode(code + "00")


def test_omni_encode_requires_omnipods():
    loadout = _sample_loadout(is_omni=True)
    loadout["components"]["left_arm"]["omnipod"] = None
    with pytest.raises(codec.MwoCodecError):
        codec.encode(loadout)


def test_encode_rejects_negative_values():
    with pytest.raises(codec.MwoCodecError):
        codec.encode_value(-1, 2)


def test_encode_rejects_oversized_values():
    with pytest.raises(codec.MwoCodecError):
        codec.encode_value(64 ** 3, 1, 1)

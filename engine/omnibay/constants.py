"""Fixed domain constants ported from the reference MwoLab client.

Every value here mirrors a constant in the reference `public/app.js`. When the
game data changes shape these are the first things to re-verify.
"""
from typing import Dict, FrozenSet, Tuple

# Order used when walking a mech for display and aggregation.
COMPONENT_ORDER: Tuple[str, ...] = (
    "head",
    "left_arm",
    "left_torso",
    "centre_torso",
    "right_torso",
    "right_arm",
    "left_leg",
    "right_leg",
)

# Upgrade slots (endo-steel / ferro) are filled in this priority order.
STRUCTURE_SLOT_ORDER: Tuple[str, ...] = (
    "right_torso",
    "centre_torso",
    "left_torso",
    "left_arm",
    "right_arm",
    "left_leg",
    "right_leg",
    "head",
)

COMPONENT_LABELS: Dict[str, str] = {
    "head": "Head",
    "left_arm": "Left Arm",
    "left_torso": "Left Torso",
    "centre_torso": "Centre Torso",
    "right_torso": "Right Torso",
    "right_arm": "Right Arm",
    "left_leg": "Left Leg",
    "right_leg": "Right Leg",
}

ENGINE_COMPONENTS: FrozenSet[str] = frozenset({"centre_torso"})
ENGINE_SIDE_COMPONENTS: FrozenSet[str] = frozenset({"left_torso", "right_torso"})
JUMP_JET_COMPONENTS: FrozenSet[str] = frozenset(
    {"left_torso", "centre_torso", "right_torso", "left_leg", "right_leg"}
)

# Placeholder internals that mark where a movable upgrade slot may sit. They are
# not real equipment and must not be counted as occupied slots.
FIXED_ARMOR_SLOT_ID = 3101
FIXED_STRUCTURE_SLOT_ID = 3100
MOVABLE_UPGRADE_SLOT_IDS: FrozenSet[int] = frozenset(
    {FIXED_ARMOR_SLOT_ID, FIXED_STRUCTURE_SLOT_ID}
)

# Total critical slots consumed by each ferro-class armor container.
ARMOR_CONTAINER_SLOT_COUNTS: Dict[int, int] = {
    2801: 14,
    2802: 7,
    2805: 7,
}

# Stealth armor is pinned to specific components instead of floating.
STEALTH_ARMOR_SLOTS_BY_COMPONENT: Dict[str, int] = {
    "left_torso": 2,
    "right_torso": 2,
    "left_arm": 2,
    "right_arm": 2,
    "left_leg": 2,
    "right_leg": 2,
}

# Endo-steel slot cost differs by tech base.
STRUCTURE_SLOTS_CLAN = 7
STRUCTURE_SLOTS_INNER_SPHERE = 14

# The head is the one component whose armor cap is not derived from internal HP.
HEAD_MAX_ARMOR = 18

DEFAULT_ARMOR_PER_TON = 32.0

WEIGHT_CLASS_ORDER: Tuple[str, ...] = ("light", "medium", "heavy", "assault")

HARDPOINT_TYPES: Tuple[str, ...] = ("energy", "ballistic", "missile", "ams", "ecm")

# `Type: 4` hardpoints are AMS regardless of what the extracted label says.
AMS_HARDPOINT_TYPE_ID = "4"


# Actuator removal is encoded as a bitfield in the MWO loadout code.
LOWER_ARM_ACTUATOR_ID = 1910
HAND_ACTUATOR_ID = 1911
ACTUATOR_BITS: Dict[str, int] = {
    "right_hand_removed": 1,
    "right_lower_arm_removed": 2,
    "left_hand_removed": 4,
    "left_lower_arm_removed": 8,
}


# Quirks name the component they apply to with a short code, e.g.
# `armor_rt_additive`. Used to show each component's own quirks beside it.
COMPONENT_QUIRK_CODES: Dict[str, str] = {
    "head": "hd",
    "left_arm": "la",
    "left_torso": "lt",
    "centre_torso": "ct",
    "right_torso": "rt",
    "right_arm": "ra",
    "left_leg": "ll",
    "right_leg": "rl",
}

# Short labels for the component grid.
COMPONENT_ABBREVIATIONS: Dict[str, str] = {
    "head": "HD",
    "left_arm": "LA",
    "left_torso": "LT",
    "centre_torso": "CT",
    "right_torso": "RT",
    "right_arm": "RA",
    "left_leg": "LL",
    "right_leg": "RL",
}

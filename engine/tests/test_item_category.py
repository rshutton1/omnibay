"""Item categories drive colour and grouping in the client.

Ammo takes the class of the weapon that fires it and ECM stands apart from
generic equipment, so the slot grid can colour them the way players already
read them elsewhere.
"""
from omnibay.calculate import item_category


def _by_name(data, name):
    return next(item for item in data.items.values() if item["name"] == name)


def test_ammo_takes_class_of_consuming_weapon(data):
    assert item_category(_by_name(data, "AC20Ammo")) == "ammo-ballistic"
    assert item_category(_by_name(data, "ClanLRMAmmo")) == "ammo-missile"
    assert item_category(_by_name(data, "AMSAmmo")) == "ammo-ams"


def test_artemis_ammo_is_still_missile_ammo(data):
    # Only the artemisAmmoType stat on launchers points at these.
    assert item_category(_by_name(data, "LRMAmmoArtemis")) == "ammo-missile"
    assert item_category(_by_name(data, "ClanSRMAmmoArtemis")) == "ammo-missile"


def test_every_ammo_item_is_classified(data):
    unclassified = [
        item["name"]
        for item in data.items.values()
        if item.get("item_type") == "ammo" and item_category(item) == "ammo-other"
    ]
    assert unclassified == []


def test_ecm_has_its_own_category(data):
    assert item_category(_by_name(data, "GuardianECM")) == "ecm"
    assert item_category(_by_name(data, "ClanECM")) == "ecm"
    assert item_category(_by_name(data, "BeagleProbe")) == "equipment"


def test_weapons_are_split_by_hardpoint(data):
    assert item_category(_by_name(data, "AutoCannon20")) == "weapon-ballistic"
    assert item_category(_by_name(data, "MediumLaser")) == "weapon-energy"

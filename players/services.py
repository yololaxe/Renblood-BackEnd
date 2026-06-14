from copy import deepcopy

from players.models import CHARACTERISTICS


LEVEL_THRESHOLDS = [
    (3000, 15),
    (2000, 14),
    (1600, 13),
    (1250, 12),
    (1000, 11),
    (750, 10),
    (600, 9),
    (450, 8),
    (350, 7),
    (270, 6),
    (200, 5),
    (140, 4),
    (90, 3),
    (50, 2),
    (20, 1),
    (0, 0),
]


def calculate_level(xp):
    for xp_threshold, level in LEVEL_THRESHOLDS:
        if xp >= xp_threshold:
            return level
    return 0


def set_nested(data, keys, value):
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def normalize_admin_bonuses(raw_real_charact):
    existing_admin = {}
    for stat, info in (raw_real_charact or {}).items():
        if isinstance(info, dict) and info.get("type") == "Admin":
            existing_admin.setdefault(stat, []).append(info)
        elif isinstance(info, list):
            admin_entries = [
                bonus for bonus in info
                if isinstance(bonus, dict) and bonus.get("type") == "Admin"
            ]
            if admin_entries:
                existing_admin.setdefault(stat, []).extend(admin_entries)
    return existing_admin


def merge_real_charact(admin_bonuses, talent_bonuses, trait_bonuses):
    merged = {
        stat: deepcopy(entries)
        for stat, entries in (admin_bonuses or {}).items()
    }
    for source in (talent_bonuses or {}, trait_bonuses or {}):
        for stat, entries in source.items():
            merged.setdefault(stat, []).extend(deepcopy(entries))
    return merged


def recalculate_job_levels(experiences):
    updated = deepcopy(experiences or {})
    jobs = updated.get("jobs", {})
    changed = False

    for job_data in jobs.values():
        xp = job_data.get("xp", 0)
        new_level = calculate_level(xp)
        if job_data.get("level") != new_level:
            job_data["level"] = new_level
            changed = True

    return updated, changed


def characteristic_totals(player, real_charact):
    totals = {}
    for stat in CHARACTERISTICS:
        base_value = getattr(player, stat, 0)
        bonus_entries = real_charact.get(stat, [])
        bonus_total = 0
        if isinstance(bonus_entries, list):
            bonus_total = sum(
                bonus.get("count", 0)
                for bonus in bonus_entries
                if isinstance(bonus, dict)
            )
        totals[stat] = base_value + bonus_total
    return totals

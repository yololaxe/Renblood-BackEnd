"""Shared job experience thresholds; preserve the established talent curve."""
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

def level_from_xp(xp):
    return next((level for threshold,level in LEVEL_THRESHOLDS if xp>=threshold),0)

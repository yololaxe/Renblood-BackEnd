from .models import NpcChange


def record_change(entity_type, entity_id, action, payload=None):
    return NpcChange.objects.create(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        payload=payload or {},
    )

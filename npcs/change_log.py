from functools import lru_cache
from types import SimpleNamespace
from django.conf import settings
from pymongo import MongoClient
from .native_changes import ChangeLog

@lru_cache(maxsize=1)
def change_writer():
    client=MongoClient(settings.MONGO_URI,serverSelectionTimeoutMS=3000,connectTimeoutMS=3000,socketTimeoutMS=10000,maxPoolSize=5)
    return ChangeLog(client[settings.MONGO_DB_NAME])


def record_change(entity_type, entity_id, action, payload=None):
    return SimpleNamespace(**change_writer().append(entity_type,entity_id,action,payload))

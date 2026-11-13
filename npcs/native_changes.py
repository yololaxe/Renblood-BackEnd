"""Ordered NPC notifications independent of Djongo's implicit auto fields."""
from datetime import datetime, timezone
from threading import Lock
from pymongo import ReturnDocument

class ChangeLog:
    def __init__(self, db):
        self.db=db;self.ready=False;self.lock=Lock()

    def initialize(self):
        if self.ready:return
        with self.lock:
            if self.ready:return
            latest=self.db.npc_changes.find_one({'revision':{'$type':'number'}},sort=[('revision',-1)])
            self.db.npc_change_counter.update_one({'_id':'revision'},{'$max':{'value':(latest or {}).get('revision',0)}},upsert=True)
            self.db.npc_changes.create_index('revision',unique=True,partialFilterExpression={'revision':{'$type':'number'}})
            self.ready=True

    def append(self, entity_type, entity_id, action, payload=None):
        self.initialize();created=datetime.now(timezone.utc)
        def write(session):
            counter=self.db.npc_change_counter.find_one_and_update({'_id':'revision'},{'$inc':{'value':1}},return_document=ReturnDocument.AFTER,session=session)
            row={'revision':counter['value'],'entity_type':entity_type,'entity_id':str(entity_id),'action':action,'payload':payload or {},'created_at':created}
            self.db.npc_changes.insert_one(row,session=session)
            return row
        # Counter and event commit together: a later poll cannot skip an earlier
        # writer whose insertion has not committed yet.
        with self.db.client.start_session() as session:return session.with_transaction(write)

    def repair_missing_revisions(self):
        self.initialize();count=0
        query={'$or':[{'revision':{'$exists':False}},{'revision':None}]}
        for candidate in self.db.npc_changes.find(query).sort('created_at',1):
            def repair(session):
                row=self.db.npc_changes.find_one({'_id':candidate['_id'],**query},session=session)
                if not row:return 0
                counter=self.db.npc_change_counter.find_one_and_update({'_id':'revision'},{'$inc':{'value':1}},return_document=ReturnDocument.AFTER,session=session)
                self.db.npc_changes.update_one({'_id':row['_id']},{'$set':{'revision':counter['value']}},session=session)
                return 1
            with self.db.client.start_session() as session:count+=session.with_transaction(repair)
        return count

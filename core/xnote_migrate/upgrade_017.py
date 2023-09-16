import xtables
import xutils
import xauth
import logging

from . import base
from xutils import Storage
from xutils import dbutil, dateutil
from xutils.db.dbutil_helper import new_from_dict

def do_upgrade():
    base.execute_upgrade("20230916_note_index", migrate_note_index)



class KvNoteIndexDO(Storage):
    def __init__(self):
        self.id = "" # id是str
        self.name = ""
        self.path = ""
        self.creator = ""
        self.ctime = dateutil.format_datetime()
        self.mtime = dateutil.format_datetime()
        self.atime = dateutil.format_datetime()
        self.type = "md"
        self.category = "" # 废弃
        self.size = 0
        self.children_count = 0
        self.parent_id = "0" # 默认挂在根目录下
        self.content = ""
        self.data = ""
        self.is_deleted = 0 # 0-正常， 1-删除
        self.is_public = 0  # 0-不公开, 1-公开
        self.token = ""
        self.priority = 0 
        self.visited_cnt = 0
        self.orderby = ""
        # 热门指数
        self.hot_index = 0
        # 版本
        self.version = 0

    @staticmethod
    def from_dict(dict_value):
        return new_from_dict(KvNoteIndexDO, dict_value)

class NoteIndexDO(Storage):
    def __init__(self):
        self.id = 0
        self.name = ""
        self.creator = ""
        self.creator_id = 0
        self.type = ""
        self.ctime = dateutil.format_datetime()
        self.mtime = dateutil.format_datetime()
        self.parent_id = 0
        self.size = 0
        self.version = 0
        self.is_deleted = 0
        self.level = 0
        self.children_count = 0

    @staticmethod
    def from_dict(dict_value):
        return new_from_dict(NoteIndexDO, dict_value)

def migrate_note_index():
    """迁移笔记索引"""
    old_db = dbutil.get_table("note_index")
    new_db = xtables.get_table_by_name("note_index")
    note_full_db = dbutil.get_table("note_full")

    for item in old_db.iter(limit=-1):
        old_index = KvNoteIndexDO.from_dict(item)
        new_index = NoteIndexDO()

        try:
            note_id = int(old_index.id)
        except:
            base.add_failed_log("note_index", old_index, reason="note_id无法转换成数字")
            continue

        creator = old_index.creator
        creator_id = xauth.UserDao.get_id_by_name(creator)

        new_index.id = note_id
        new_index.name = old_index.name
        new_index.creator = old_index.creator
        new_index.creator_id = creator_id
        new_index.name = old_index.name
        new_index.parent_id = int(old_index.parent_id)
        new_index.ctime = old_index.ctime
        new_index.mtime = old_index.mtime
        new_index.type = old_index.type or "md"
        new_index.size = old_index.size or 0
        new_index.level = old_index.priority or 0
        new_index.children_count = old_index.children_count or 0
        if old_index.archived:
            new_index.level = -1

        old_note_id = str(old_index.id)
        if str(note_id) != old_note_id:
            full_do = note_full_db.get_by_id(old_note_id)
            if full_do != None:
                note_full_db.update_by_id(str(note_id), full_do)
                note_full_db.delete_by_id(old_note_id)

        old = new_db.select_first(where=dict(id=note_id))
        if old != None:
            new_db.update(**new_index, where=dict(id=new_index.id))
        else:
            new_db.insert(**new_index)
        
        logging.info("迁移笔记索引: %s", new_index)

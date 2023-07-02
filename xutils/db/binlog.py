# -*- coding:utf-8 -*-
"""
@Author       : xupingmao
@email        : 578749341@qq.com
@Date         : 2022-05-04 19:55:32
@LastEditors  : xupingmao
@LastEditTime : 2023-07-02 19:25:50
@FilePath     : /xnote/xutils/db/binlog.py
@Description  : 数据库的binlog,用于同步
"""
from xutils.db.dbutil_base import count_table, prefix_iter
from xutils.db.dbutil_table import db_put, prefix_list, register_table, create_write_batch

import struct
import threading
import logging
import base64

register_table("_binlog", "数据同步的binlog")

class BinLog:
    _table_name = "_binlog"
    _lock = threading.RLock()
    _delete_lock = threading.RLock()
    _instance = None
    _is_enabled = False
    _max_size = 10000
    log_debug = False
    logger = logging.getLogger("binlog")

    def __init__(self) -> None:
        """正常要使用单例模式使用"""
        with self._lock:
            if self._instance != None:
                raise Exception("只能创建一个BinLog单例")
            self._instance = self

        last_key = self.get_last_key()
        if last_key == None:
            self.last_seq = 0
        else:
            self.last_seq = self._unpack_id(last_key)

    def _pack_id(self, log_id=0):
        return struct.pack('>Q', log_id).hex()
    
    def _unpack_id(self, id_str=""):
        if len(id_str) == 20:
            return int(id_str)
        
        id_bytes = base64.b16decode(id_str.upper())
        return struct.unpack('>Q', id_bytes)[0]

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance == None:
                cls._instance = BinLog()
            return cls._instance

    @classmethod
    def set_enabled(cls, is_enabled):
        cls._is_enabled = is_enabled

    @classmethod
    def set_max_size(cls, max_size):
        cls._max_size = max_size

    def count_size(self):
        return count_table(self._table_name)

    def get_record_key(self, log_id):
        return self._table_name + ":" + log_id

    def get_last_key(self):
        logs = prefix_list(self._table_name, reverse=True,
                           limit=1, include_key=True)
        if len(logs) == 0:
            return None
        key, value = logs[0]
        return key.split(":")[1]

    def find_start_seq(self):
        logs = prefix_list(self._table_name, limit=1, include_key=True)
        if len(logs) == 0:
            return 1
        key, value = logs[0]
        return int(key.split(":")[1])

    def _put_log(self, log_id, log_body, batch=None):
        key = self.get_record_key(log_id)
        # print("binlog(%s,%s)" % (key, log_body))
        if batch != None:
            batch.put(key, log_body)
        else:
            db_put(key, log_body)

    def add_log(self, optype, key, value=None, batch=None, old_value=None, *, record_value=False):
        if not self._is_enabled:
            return

        with self._lock:
            self.last_seq += 1
            binlog_id = self._pack_id(self.last_seq)
            binlog_body = dict(optype=optype, key=key, old_value=old_value)
            if record_value:
                binlog_body["value"] = value
            self._put_log(binlog_id, binlog_body, batch=batch)

    def list(self, last_seq, limit, map_func=None):
        """从last_seq开始查询limit个binlog"""
        start_id = self._pack_id(last_seq)
        key_from = self._table_name + ":" + start_id
        return prefix_list(self._table_name, key_from=key_from, limit=limit, map_func=map_func)

    def delete_expired(self):
        assert self._max_size != None, "binlog_max_size未设置"
        assert self._max_size > 0, "binlog_max_size必须大于0"

        start_seq = self.find_start_seq()

        size = self.count_size()
        self.logger.info("count size:%s", size)

        if size > self._max_size:
            with self._delete_lock:
                limit = size - self._max_size
                self.logger.info("limit size: %s", size)
                keys = []
                batch_size = 100

                key_from = self._table_name + ":" + self._pack_id(start_seq)
                for key, value in prefix_iter(self._table_name, key_from=key_from, limit=limit, include_key=True):
                    keys.append(key)
                    if len(keys) >= batch_size:
                        self.delete_batch(keys)
                        keys = []
                self.delete_batch(keys)
    
    def delete_batch(self, keys):
        if len(keys) == 0:
            return
        if self.log_debug:
            self.logger.info("Delete keys: %s", keys)
        with create_write_batch() as batch:
            for key in keys:
                batch.delete(key)

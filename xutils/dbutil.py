# encoding=utf-8

"""xnote的数据库封装，基于键值对数据库（目前是基于leveldb，键值对功能比较简单，方便在不同引擎之间切换）

由于KV数据库没有表的概念，dbutil基于KV模拟了表，基本结构如下
* <table_name>:[subkey1]:[subkey2]:id

示例：
案例1： <表名:用户名:主键> note:admin:0001
案例2： <表名:标签:主键> note_public:tag1:0001

注意：读写数据前要先调用register_table来注册表，不然会失败！

包含的方法如下
* get_table       获取一个表对象
* register_table  注册表，如果没注册系统会拒绝写入
* count_table     统计表记录数
* put
* get
* delete
* scan
* prefix_list
* prefix_iter
* prefix_count

"""
# 先加载标准库
from __future__ import print_function, with_statement
import os
import time
import json
import threading
try:
    import sqlite3
except ImportError:
    # 部分运行时环境可能没有sqlite3
    sqlite3 = None

# 加载第三方的库
import xutils
from xutils.base import Storage

try:
    import leveldb
except ImportError:
    leveldb = None


WRITE_LOCK    = threading.Lock()
LAST_TIME_SEQ = -1

# 注册的数据库表名，如果不注册，无法进行写操作
TABLE_DICT = dict()
LDB_TABLE_DICT = dict()

###########################################################
# @desc db utilties
# @author xupingmao
# @email 578749341@qq.com
# @since 2015-11-02 20:09:44
# @modified 2021/09/19 13:14:23
###########################################################

class DBException(Exception):
    pass

class RecordLock:

    _enter_lock = threading.Lock()
    _lock_dict  = dict()

    def __init__(self, lock_key):
        self.lock = None
        self.lock_key = lock_key

    def acquire(self, timeout = -1):
        lock_key = self.lock_key

        wait_time_start = time.time()
        with RecordLock._enter_lock:
            while RecordLock._lock_dict.get(lock_key) != None:
                # 如果复用lock，可能导致无法释放锁资源
                time.sleep(0.001)
                if timeout > 0:
                    wait_time = time.time() - wait_time_start
                    if wait_time > timeout:
                        return False
            # 由于_enter_lock已经加锁了，_lock_dict里面不需要再使用锁
            RecordLock._lock_dict[lock_key] = True
        return True

    def release(self):
        del RecordLock._lock_dict[self.lock_key]

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, type, value, traceback):
        self.release()

    def __del__(self):
        self.release()

def search_escape(text):
    if not (isinstance(text, str) or isinstance(text, unicode)):
        return text
    text = text.replace('/', '//')
    text = text.replace("'", '\'\'')
    text = text.replace('[', '/[')
    text = text.replace(']', '/]')
    #text = text.replace('%', '/%')
    #text = text.replace('&', '/&')
    #text = text.replace('_', '/_')
    text = text.replace('(', '/(')
    text = text.replace(')', '/)')
    return "'%" + text + "%'"

def to_sqlite_obj(text):
    if text is None:
        return "NULL"
    if not (isinstance(text, str)):
        return repr(text)
    # text = text.replace('\\', '\\')
    text = text.replace("'", "''")
    return "'" + text + "'"
    
def escape(text):
    if not (isinstance(text, str)):
        return text
    #text = text.replace('\\', '\\\\')
    text = text.replace("'", "''")
    return "'" + text + "'"


class LevelDBProxy:

    def __init__(self, path):
        """通过leveldbpy来实现leveldb的接口代理"""
        import leveldbpy
        self._db = leveldbpy.DB(path.encode("utf-8"), create_if_missing=True)

    def Get(self, key):
        return self._db.get(key)

    def Put(self, key, value, sync = False):
        return self._db.put(key, value, sync = sync)

    def Delete(self, key, sync = False):
        return self._db.delete(key, sync = sync)

    def RangeIter(self, key_from = None, key_to = None, reverse = False, include_value = False):
        if include_value:
            keys_only = False
        else:
            keys_only = True

        iterator = self._db.iterator(keys_only = keys_only)
        return iterator.RangeIter(key_from, key_to, include_value = include_value, reverse = reverse)

# 初始化KV存储
_leveldb = None


@xutils.log_init_deco("leveldb")
def init():
    global _leveldb
    if leveldb:
        import xconfig
        _leveldb = leveldb.LevelDB(xconfig.DB_DIR)

    if xutils.is_windows():
        os.environ["PATH"] += os.pathsep + "lib"
        import leveldbpy, xconfig
        _leveldb = LevelDBProxy(xconfig.DB_DIR)
    
    xutils.log("init leveldb done, leveldb = %s" % _leveldb)

def check_not_empty(value, message):
    if value == None or value == "":
        raise Exception(message)

def timeseq():
    # 加锁防止并发生成一样的值
    # TODO 提高存储效率
    global LAST_TIME_SEQ
    global WRITE_LOCK

    with WRITE_LOCK:
        t = int(time.time() * 1000)
        if t == LAST_TIME_SEQ:
            # 等于上次生成的值，说明太快了，sleep一下进行控速
            # print("too fast, sleep 0.001")
            time.sleep(0.001)
            t = int(time.time() * 1000)
        LAST_TIME_SEQ = t
        return "%020d" % t

def new_id(prefix):
    return "%s:%s" % (prefix, timeseq())

def get_object_from_bytes(bytes, parse_json = True):
    if bytes is None:
        return None
    str_value = bytes.decode("utf-8")
    
    if not parse_json:
        return str_value

    try:
        obj = json.loads(str_value)
    except:
        xutils.print_exc()
        return str_value
    if isinstance(obj, dict):
        obj = Storage(**obj)
    return obj

def check_leveldb():
    if _leveldb is None:
        raise Exception("leveldb not found!")

def check_get_leveldb():
    if _leveldb is None:
        raise Exception("leveldb not found!")
    return _leveldb

class LdbTable:
    """基于leveldb的表，比较常见的是以下几种
    * key = prefix:record_id           全局数据库
    * key = prefix:user_name:record_id 用户维度数据
    * key = prefix:user_name:folder_id:record_id 用户+文件夹维度数据

    字段说明: 
    * prefix    代表的是功能类型，比如猫和狗是两种不同的动物，锤子和手机是两种不同的工具
    * user_name 代表用户名，比如张三和李四
    * folder_id 代表用户定义的目录，比如张三有两个不同的项目
    * record_id 代表一条记录的ID
    """

    def __init__(self, table_name, key_name = "_key"):
        # 参数检查
        check_not_empty(table_name, "dbutil.Table: table_name can not be empty")

        self.table_name = table_name
        self.key_name = key_name

        self.prefix = table_name
        if self.prefix[-1] != ":":
            self.prefix += ":"

    def build_key(self, *argv):
        return self.prefix + ":".join(argv)

    def _get_key_from_obj(self, obj):
        if obj is None:
            raise Exception("obj can not be None")

        return getattr(obj, self.key_name)

    def _get_result_from_tuple_list(self, tuple_list):
        result = []
        for key, value in tuple_list:
            setattr(value, self.key_name, key)
            result.append(value)
        return result

    def _get_update_obj(self, obj):
        return obj

    def _get_id_value(self, id_type = "uuid"):
        if id_type == "uuid":
            return xutils.create_uuid()
        elif id_type == "timeseq":
            return timeseq()
        else:
            raise Exception("unknown id_type:%s" % id_type)

    def _check_before_delete(self, key):
        if not key.startswith(self.prefix):
            raise Exception("invalid key:%s" % key)

    def _check_value(self, obj):
        if not isinstance(obj, dict):
            raise Exception("invalid obj:%s, expected dict" % type(obj))

    def is_valid_key(self, key = None, user_name = None):
        if user_name is None:
            return key.startswith(self.prefix)
        else:
            return key.startswith(self.prefix + user_name)

    def get_by_key(self, key, default_value = None):
        value = get(key, default_value)
        if value != None:
            setattr(value, self.key_name, key)
        return value

    def insert(self, obj, id_type = "uuid"):
        self._check_value(obj)
        id_value = self._get_id_value(id_type)
        key  = self.build_key(id_value)
        put(key, obj)
        return key

    def insert_by_user(self, user_name, obj, id_type = "uuid"):
        self._check_value(obj)
        id_value = self._get_id_value(id_type)
        key  = self.build_key(user_name, id_value)
        put(key, obj)
        return key

    def update(self, obj):
        """从`obj`中获取主键`key`进行更新"""
        self._check_value(obj)
        obj_key = self._get_key_from_obj(obj)
        update_obj = self._get_update_obj(obj)
        put(obj_key, update_obj)

    def update_by_key(self, key, obj):
        """直接通过`key`进行更新"""
        self._check_value(obj)
        update_obj = self._get_update_obj(obj)
        put(key, update_obj)

    def delete(self, obj):
        obj_key = self._get_key_from_obj(obj)
        self._check_before_delete(obj_key)
        delete(obj_key)

    def delete_by_key(self, key):
        self._check_before_delete(key)
        delete(key)

    def list(self, offset = 0, limit = 20, reverse = False):
        tuple_list = prefix_list(self.prefix, None, offset, limit, reverse = reverse, include_key = True)
        return self._get_result_from_tuple_list(tuple_list)

    def list_by_user(self, user_name, offset = 0, limit = 20, reverse = False):
        tuple_list = prefix_list(self.prefix + user_name, None, offset, limit, reverse = reverse, include_key = True)
        return self._get_result_from_tuple_list(tuple_list)

    def list_by_func(self, user_name, filter_func = None, offset = 0, limit = 20, reverse = False):
        tuple_list = prefix_list(self.prefix + user_name, filter_func, offset, limit, reverse = reverse, include_key = True)
        return self._get_result_from_tuple_list(tuple_list)

    def count(self):
        return count_table(self.table_name)

    def count_by_user(self, user_name):
        return count_table(self.prefix + user_name)

    def count_by_func(self, user_name, filter_func):
        assert filter_func != None, "[count_by_func.assert] filter_func != None"
        return prefix_count(self.prefix + user_name, filter_func)


class PrefixedDb(LdbTable):
    """plyvel中叫做prefixed_db"""
    pass


class TableInfo:

    def __init__(self, name, description, category):
        self.name = name
        self.description = description
        self.category = category

def register_table(table_name, description, category = "default"):
    # TODO 考虑过这个方法直接返回一个 LdbTable 实例
    # LdbTable可能针对同一个`table`会有不同的实例
    TABLE_DICT[table_name] = TableInfo(table_name, description, category)

def get_table(table_name):
    """获取table对象
    @param {str} table_name 表名
    @return {LdbTable}
    """
    assert table_name != None
    table = LDB_TABLE_DICT.get(table_name)
    if table is None:
        table = LdbTable(table_name)
        LDB_TABLE_DICT[table_name] = table
    return table

def get_table_dict_copy():
    return TABLE_DICT.copy()

def get(key, default_value = None):
    check_leveldb()
    try:
        if key == "" or key == None:
            return None

        key = key.encode("utf-8")
        value = _leveldb.Get(key)
        result = get_object_from_bytes(value)
        if result is None:
            return default_value
        return result
    except KeyError:
        return default_value

def obj_to_json(obj):
    # ensure_ascii默认为True，会把非ascii码的字符转成\u1234的格式
    return json.dumps(obj, ensure_ascii=False)

def put(key, obj_value, sync = False):
    check_leveldb()
    check_not_empty(key, "[dbutil.put] key can not be None")

    table_name = key.split(":")[0]

    if table_name not in TABLE_DICT:
        raise DBException("table %s not registered!" % table_name)
    
    key = key.encode("utf-8")
    # 注意json序列化有个问题，会把dict中数字开头的key转成字符串
    value = obj_to_json(obj_value)
    # print("Put %s = %s" % (key, value))
    _leveldb.Put(key, value.encode("utf-8"), sync = sync)

def insert(table_name, obj_value, sync = False):
    key = new_id(table_name)
    put(key, obj_value, sync)
    return key

def delete(key, sync = False):
    check_leveldb()

    print("Delete %s" % key)
    key = key.encode("utf-8")
    _leveldb.Delete(key, sync = sync)

def scan(key_from = None, key_to = None, func = None, reverse = False):
    """扫描数据库
    @param {string} key_from
    @param {string} key_to
    @param {function} func
    @param {boolean} reverse
    """
    check_leveldb()

    if key_from != None:
        key_from = key_from.encode("utf-8")
    if key_to != None:
        key_to = key_to.encode("utf-8")
    iterator = _leveldb.RangeIter(key_from, key_to, include_value = True, reverse = reverse)
    for key, value in iterator:
        key = key.decode("utf-8")
        value = get_object_from_bytes(value)
        if not func(key, value):
            break

def prefix_scan(prefix, func, reverse = False, parse_json = True):
    check_leveldb()

    key_from = None
    key_to   = None

    if prefix[-1] != ':':
        prefix += ':'

    prefix_bytes = prefix.encode("utf-8")

    if reverse:
        key_to   = prefix_bytes
        key_from = prefix_bytes + b'\xff'
        iterator = _leveldb.RangeIter(None, key_from, include_value = True, reverse = True)
    else:
        key_from = prefix_bytes
        key_to   = None
        iterator = _leveldb.RangeIter(key_from, None, include_value = True, reverse = False)

    offset = 0
    for key, value in iterator:
        key = key.decode("utf-8")
        if not key.startswith(prefix):
            break
        value = get_object_from_bytes(value, parse_json)
        if not func(key, value):
            break
        offset += 1

def prefix_list(prefix, filter_func = None, offset = 0, limit = -1, reverse = False, include_key = False):
    return list(prefix_iter(prefix, filter_func, offset, limit, reverse, include_key))

def prefix_iter(prefix, filter_func = None, offset = 0, limit = -1, reverse = False, include_key = False):
    """通过前缀查询
    @param {string} prefix 遍历前缀
    @param {function} filter_func 过滤函数
    @param {int} offset 选择的开始下标，包含
    @param {int} limit  选择的数据行数
    @param {boolean} reverse 是否反向遍历
    @param {boolean} include_key 返回的数据是否包含key，默认只有value
    """
    check_leveldb()

    if prefix[-1] != ':':
        prefix += ':'

    origin_prefix = prefix
    prefix = prefix.encode("utf-8")

    if reverse:
        # 时序表的主键为 表名:用户名:时间序列 时间序列长度为20
        prefix += b'\xff'
    
    # print("prefix: %s, origin_prefix: %s, reverse: %s" % (prefix, origin_prefix, reverse))
    if reverse:
        iterator = _leveldb.RangeIter(None, prefix, include_value = True, reverse = True)
    else:
        iterator = _leveldb.RangeIter(prefix, None, include_value = True, reverse = False)

    position       = 0
    matched_offset = 0
    result_size    = 0

    for key, value in iterator:
        key = key.decode("utf-8")
        if not key.startswith(origin_prefix):
            break
        value = get_object_from_bytes(value)
        if filter_func is None or filter_func(key, value):
            if matched_offset >= offset:
                result_size += 1
                if include_key:
                    yield key, value
                else:
                    yield value
            matched_offset += 1

        if limit > 0 and result_size >= limit:
            break
        position += 1


def count(key_from = None, key_to = None, filter_func = None):
    check_leveldb()

    if key_from:
        key_from = key_from.encode("utf-8")
    if key_to:
        key_to = key_to.encode("utf-8")
    iterator = _leveldb.RangeIter(key_from, key_to, include_value = True)
    count = 0
    for key, value in iterator:
        key = key.decode("utf-8")
        value = get_object_from_bytes(value)
        if filter_func(key, value):
            count += 1
    return count

def prefix_count(prefix, filter_func = None):
    count = [0]
    def func(key, value):
        if not key.startswith(prefix):
            return False
        if filter_func is None:
            count[0] += 1
        elif filter_func(key, value):
            count[0] += 1
        return True
    prefix_scan(prefix, func)
    return count[0]

def count_table(table_name):
    key_from = ("%s:" % table_name).encode("utf-8")
    key_to   = ("%s:" % table_name).encode("utf-8") + b'\xff'
    iterator = check_get_leveldb().RangeIter(key_from, key_to, include_value = False)
    count = 0
    for key in iterator:
        count += 1
    return count

def write_op_log(op, event):
    """开启批量操作前先记录日志
    @param {string} op 操作类型
    @param {object} event 操作事件
    @return 日志ID
    """
    pass

def delete_op_log(log_id):
    """完成批量操作后删除日志
    @param {string} log_id 操作日志ID
    @return None
    """
    pass


def rename_table(old_name, new_name):
    # TODO 还没实现
    for key, value in prefix_iter(old_name, include_key = True):
        name, rest = key.split(":", 1)
        new_key = new_name + ":" + rest


def _zadd(key, score, member):
    # step1. write log
    # step2. delete zscore:key:score
    # step3. write zmember:key:member = score
    # step4. write zscore:key:score = [key1, key2]
    # step5. delete log
    obj = get(key)
    # print("zadd %r %r" % (member, score))
    if obj != None:
        obj[member] = score
        put(key, obj)
    else:
        obj = dict()
        obj[member] = score
        put(key, obj)

def _zrange(key, start, stop):
    """zset分片，不同于Python，这里是左右包含，包含start，包含stop，默认从小到大排序
    :arg int start: 从0开始，负数表示倒数
    :arg int stop: 从0开始，负数表示倒数
    TODO 优化排序算法，使用有序列表+哈希表
    """
    obj = get(key)
    if obj != None:
        items = obj.items()
        length = len(items)

        if stop < 0:
            stop += length + 1
        if start < 0:
            start += length + 1

        sorted_items = sorted(items, key = lambda x: x[1])
        sorted_keys = [k[0] for k in sorted_items]
        if stop < start:
            # 需要逆序
            stop -= 1
            start += 1
            found = sorted_keys[stop: start]
            found.reverse()
            return found
        return sorted_keys[start: stop]
    return []

def _zcount(key):
    obj = get(key)
    if obj != None:
        return len(obj)
    return 0

def _zscore(key, member):
    obj = get(key)
    if obj != None:
        return obj.get(member)
    return None

def _zrem(key, member):
    obj = get(key)
    if obj != None:
        if member in obj:
            del obj[member]
            put(key, obj)
            return 1
    return 0

def run_test():
    pass

if __name__ == "__main__":
    run_test()
    
    
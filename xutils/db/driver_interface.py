# -*- coding:utf-8 -*-
# @author mark
# @since 2022/03/19 23:28:08
# @modified 2022/03/20 14:42:16
# @filename driver_interface.py

"""这里定义一个通用的K-V数据库接口
PS: 接口是以Leveldb的接口为模板定义的
"""

import warnings

class DBInterface:
    """KV存储的数据库接口"""

    def __init__(self, *args, **kw):
        self.driver_type = ""
        self.debug = False
        self.log_debug = False

    def Get(self, key):
        # type: (bytes) -> bytes
        """通过key读取Value
        @param {bytes} key
        @return {bytes|None} value
        """
        raise NotImplementedError("Get")
    
    def BatchGet(self, keys):
        """批量get操作"""
        result = dict()
        for key in keys:
            result[key] = self.Get(key)
        return result

    def Put(self, key, value, sync = False):
        # type: (bytes,bytes,bool) -> None
        """写入Key-Value键值对
        @param {bytes} key
        @param {bytes} value
        """
        raise NotImplementedError("Put")

    def Delete(self, key, sync = False):
        # type: (bytes, bool) -> None
        """删除Key-Value键值对
        @param {bytes} key
        """
        raise NotImplementedError("Delete")

    def RangeIter(self, 
            key_from = b'', # type: bytes
            key_to = b'',  # type: bytes
            reverse = False,
            include_value = True, 
            fill_cache = False):
        """返回区间迭代器
        @param {bytes}  key_from       开始的key（包含）FirstKey 字节顺序小的key
        @param {bytes}  key_to         结束的key（包含）LastKey  字节顺序大的key
        @param {bool}   reverse        是否反向查询
        @param {bool}   include_value  是否包含值
        @param {bool}   fill_cache     是否填充缓存
        """
        assert key_from <= key_to
        if include_value:
            yield b'test-key', b'test-value'
        else:
            yield b'test-key'

    def CreateSnapshot(self):
        raise NotImplementedError("CreateSnapshot")

    def Write(self, batch_proxy, sync = False):
        raise NotImplementedError("Write")

    def Count(self, key_from, key_to):
        iterator = self.RangeIter(
            key_from, key_to, include_value=False, fill_cache=False)
        count = 0
        for key in iterator:
            count += 1
        return count


class DBLockInterface:
    """基于数据库的锁的接口"""

    def Acquire(self, resource_id, timeout):
        """返回token
        @return {str} token
        """
        raise NotImplementedError("Acquire")
    
    def Release(self, resource_id, token):
        raise NotImplementedError("Release")
    
    def Refresh(self, resource_id, token, refresh_time):
        raise NotImplementedError("Refresh")

class RecordInterface:
    """数据库记录的接口
    @deprecated 使用 xutils.Storage 就可以了
    """

    def from_storage(self, dict_value):
        """从数据库记录转为领域模型"""
        self.__dict__.update(dict_value)

    def to_storage(self):
        """从领域模型转为数据库记录"""
        return self.__dict__

class BatchInterface:

    def check_and_delete(self, key):
        raise NotImplementedError("待子类实现")
    
    def check_and_put(self, key, value):
        raise NotImplementedError("待子类实现")

    def commit(self, sync=False, retries=0):
        raise NotImplementedError("待子类实现")


class CacheInterface:
    """缓存接口"""

    def get(self, key):
        return None
    
    def put(self, key, value, expire = -1, expire_random = 600):
        return None
    
    def delete(self, key):
        warnings.warn("CacheInterface.delete is not implemented")


empty_db = DBInterface()
empty_cache = CacheInterface()

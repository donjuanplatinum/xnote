# -*- coding:utf-8 -*-
# @author mark
# @since 2022/03/19 23:28:08
# @modified 2022/03/20 14:42:16
# @filename driver_interface.py

"""这里定义一个通用的K-V数据库接口
PS: 接口是以Leveldb的接口为模板定义的
"""

class DBInterface:
    """KV存储的数据库接口"""

    def __init__(self, *args, **kw):
        raise NotImplementedError("__init__")

    def Get(self, key):
        # type: (bytes) -> bytes
        """通过key读取Value
        @param {bytes} key
        @return {bytes|None} value
        """
        raise NotImplementedError("Get")

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
            key_from = None, # type: bytes
            key_to = None,  # type: bytes
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
        raise NotImplementedError("RangeIter")

    def CreateSnapshot(self):
        raise NotImplementedError("CreateSnapshot")

    def Write(self, batch_proxy, sync = False):
        raise NotImplementedError("Write")


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


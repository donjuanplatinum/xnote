# -*- coding:utf-8 -*-
# @author mark
# @since 2022/02/27 16:07:55
# @modified 2022/04/09 10:54:40
# @filename fs_helpers.py

"""文件管理模块的工具
注: 叫fs_helpers是为了和fsutil名称混淆
"""

import xutils
import xconfig
import xauth
import xconfig
import os
from xutils import dbutil
from xutils import format_size
from xutils import fsutil, six
from xutils.dbutil import LdbTable
from xutils.fsutil import FileItem

_index_db = dbutil.get_table("fs_index")
_index_db.set_binlog_enabled(False)

def get_index_db(): # type: ()-> LdbTable
    return _index_db

def handle_file_item(item):
    """文件的后置处理器"""
    if item.type == "dir":
        item.icon = "fa-folder orange"
    elif item.ext in xconfig.FS_VIDEO_EXT_LIST:
        item.icon = "fa-file-video-o"
    elif item.ext in xconfig.FS_CODE_EXT_LIST:
        item.icon = "fa-file-code-o"
    elif item.ext in xconfig.FS_AUDIO_EXT_LIST:
        item.icon = "fa-file-audio-o"
    elif item.ext in xconfig.FS_ZIP_EXT_LIST:
        item.icon = "fa-file-zip-o"
    elif xutils.is_text_file(item.path):
        item.icon = "fa-file-text-o"
    elif xutils.is_img_file(item.path):
        item.icon = "fa-file-image-o"

    handle_file_url(item)
    item.show_opt_btn = True
    return item

def handle_file_url(item):
    item.css_class = ""
    if item.type == "dir":
        item.url = "/fs/%s" % item.encoded_path
    elif xutils.is_img_file(item.path):
        item.url = "#"
        item.css_class = "x-photo"
    elif xutils.is_audio_file(item.path):
        item.url = "/fs/%s" % item.encoded_path
    else:
        item.url = "/fs_preview?path=%s&embed=false" % item.encoded_path

def get_parent_file_object(path, name = ""):
    path = os.path.abspath(path)
    parent_file = FileItem(os.path.dirname(path))
    handle_file_item(parent_file)
    if name != "":
        parent_file.name = name
    parent_file.show_opt_btn = False
    return parent_file

def get_index_dirs():
    index_dirs = xauth.get_user_config("admin", "fs_index_dirs")
    assert isinstance(index_dirs, six.string_types)
    return index_dirs.split("\n")

def get_file_thumbnail(fpath):
    if xutils.is_img_file(fpath):
        return xutils.get_webpath(fpath) + "?mode=thumbnail"

    if xutils.is_text_file(fpath):
        return "/static/image/icon_txt.png"

    # 位置类型
    return "/static/image/file2.png"

def get_file_download_link(fpath):
    if fsutil.is_parent_dir(xconfig.DATA_DIR, fpath):
        relative_path = fsutil.get_relative_path(fpath, xconfig.DATA_DIR)
        fpath = relative_path
        encoded_path = xutils.encode_uri_component(fpath)
        return "/data/%s?type=blob" % encoded_path
    encoded_path = xutils.encode_uri_component(fpath)
    download_link = "/fs/%s?type=blob" % encoded_path
    return download_link


def sort_files_by_size(filelist):
    db = get_index_db()
    for file in filelist:
        fpath = file.path
        fpath = os.path.abspath(fpath)
        realpath = os.path.realpath(fpath)
        info = db.get_by_id(realpath)
        if info != None and hasattr(info, "fsize"):
            file.fsize = info.fsize
            size_str = format_size(info.fsize)
            if os.path.islink(fpath):
                file.size = "Link(%s)" % size_str
            else:
                file.size = size_str
        else:
            file.size = "Unknown"

    def key_func(file):
        if not isinstance(file.fsize, int):
            return 0
        return file.fsize

    filelist.sort(key = key_func, reverse = True)


xutils.register_func("fs.get_file_thumbnail", get_file_thumbnail)
xutils.register_func("fs.get_file_download_link", get_file_download_link)
xutils.register_func("fs.get_index_dirs", get_index_dirs)

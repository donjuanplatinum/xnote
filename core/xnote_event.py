# encoding=utf-8
from xutils import Storage

class FileUploadEvent(Storage):
    """文件上传事件"""

    def __init__(self):
        self.user_name = ""
        self.user_id = 0
        self.fpath = ""

# encoding=utf-8
# filename post.py

import os
import re

import web
import xtemplate
import web.db as db

import xutils

from util import dateutil
from util import fsutil

def get_file_db():
    return db.SqliteDB(db="db/data.db")

class PostView(object):
    """docstring for handler"""
    
    def GET(self):
        args = web.input()
        id = int(args.id)
        file_db = get_file_db()
        file = file_db.select("file", where={"id": id})[0]
        if file.content != None:
            file.content = xutils.html_escape(file.content, quote=False);
            file.content = file.content.replace(" ", "&nbsp;")
            file.content = file.content.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
            file.content = file.content.replace("\n", "<br/>")
            file.content = file.content.replace("[img&nbsp;", "<p style=\"text-align:center;\"><img ")
            file.content = file.content.replace("img]", "></p>")
            file.content = re.sub(r"https?://[^\s]+", '<a href="\\g<0>">\\g<0></a>', file.content)

        return xtemplate.render("file/post.html",
            op = "view",
            file = file)

class PostEdit:
    def create_file_name(self, filename):
        date = dateutil.format_date(fmt="%Y/%m")
        newfilename = "static/img/" + date + "/" + filename
        fsutil.check_create_dirs("static/img/"+date)
        while os.path.exists(newfilename):
            name, ext = os.path.splitext(newfilename)
            newfilename = name + "1" + ext
        return newfilename

    def GET(self):
        args = web.input()
        id = int(args.id)
        file_db = get_file_db()
        file = file_db.select("file", where={"id": id})[0]
        rows = file.content.count("\n")+5
        rows = max(rows, 20)
        return xtemplate.render("file/post.html", 
            op="eidt", 
            file=file,
            rows = rows)

    def POST(self):
        # 一定要加file={}
        args = web.input(file={}, public=None)
        id = int(args.id)
        file_db = get_file_db()
        file = file_db.select("file", where={"id": id})[0]
        file.content = args.content
        file.smtime = dateutil.format_time()
        file.name = args.name
        file.type = "post"
        file.size = len(file.content)
        if args.public == "on":
            file.groups = "*"
        else:
            file.groups = file.creator
        if hasattr(args.file, "filename") and args.file.filename!="":
            filename = args.file.filename
            filepath = self.create_file_name(args.file.filename)
            fout = open(filepath, "wb")
            # fout.write(x.file.file.read())
            for chunk in args.file.file:
                fout.write(chunk)
            fout.close()
            file.content = file.content + "\n[img src=\"/{}\"img]".format(filepath)

        file_db.update("file", where={"id": id}, vars=["content"], **file)
        raise web.seeother("/file/post?id={}".format(id))
        
class PostDel:
    def GET(self):
        args = web.input()
        id = int(args.id)
        file_db = get_file_db()
        file_db.delete("file", where={"id": id})
        raise web.seeother("/")

xurls = ("/file/post", PostView, 
        "/file/post/edit", PostEdit, 
        "/file/post/del", PostDel)



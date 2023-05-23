# encoding=utf-8
# @modified 2022/04/04 14:01:57
import web
import xauth
import xtemplate
import xmanager
import xutils
import math
from xutils import textutil
from xutils import Storage
from xutils import dbutil
from xutils import webutil

OP_LOG_TABLE = dbutil.get_table("user_op_log")


def create_op_log(user_name, op_type, detail):
    now = xutils.format_datetime()
    ip = webutil.get_real_ip()
    log = Storage(ctime=now, user_name=user_name,
                  type=op_type, detail=detail, ip=ip)
    OP_LOG_TABLE.insert(log)


def get_user_dict():
    result = dict()
    for item in xauth.iter_user(limit=100):
        result[item.name] = item
    return result


class ListHandler:
    """用户管理"""

    @xauth.login_required("admin")
    def GET(self):
        page = xutils.get_argument_int("page", 1)
        page_size = xutils.get_argument_int("page_size", 10)
        offset = (page-1) * page_size
        assert offset >= 0

        total = xauth.UserModel.count()

        kw = Storage()
        kw.user_info = None
        kw.show_aside = False
        kw.user_list = xauth.UserModel.list(offset = offset, limit = page_size)
        kw.page = page
        kw.page_size = page_size
        kw.page_max = math.ceil(total/page_size)//1

        return xtemplate.render("user/page/user_list.html", **kw)

    @xauth.login_required("admin")
    def POST(self):
        name = xutils.get_argument("name")
        password = xutils.get_argument("password")
        error = xauth.create_user(name, password)
        added = xauth.get_user(name)
        # 先暴力解决
        xmanager.reload()
        raise web.seeother("/system/user?name=%s" % name)


class UserHandler:

    @xauth.login_required("admin")
    def GET(self):
        name = xutils.get_argument("name", "")
        user_info = None
        if name != "":
            user_info = xauth.get_user(name)
        return xtemplate.render("user/page/user_manage.html",
                                show_aside=False,
                                name=name,
                                user_info=user_info,
                                user_dict=get_user_dict())

    @xauth.login_required("admin")
    def POST(self):
        name = xutils.get_argument("name")
        password = xutils.get_argument("password")
        user_info = xauth.get_user(name)
        if user_info is None:
            raise Exception("用户不存在:%s" % name)

        user_info.password = password
        xauth.update_user(name, user_info)

        raise web.seeother("/system/user?name=%s" % name)


class AddHandler:

    @xauth.login_required("admin")
    def POST(self):
        name = xutils.get_argument("name")
        return xauth.create_user(name, textutil.random_string(6))


class RemoveHandler:

    @xauth.login_required("admin")
    def POST(self):
        user_id = xutils.get_argument_int("user_id")
        xauth.UserModel.delete_by_id(user_id)
        return dict(code="success")


class UserInfoHandler:

    @xauth.login_required()
    def GET(self):
        user = xauth.current_user()
        return xtemplate.render("user/page/userinfo.html", user=user)


class SessionInfoAjaxHandler:

    @xauth.login_required()
    def GET(self):
        user_name = xauth.current_name()
        return xauth.list_user_session_detail(user_name)


class ChangePasswordHandler:

    def GET(self, error=""):
        """获取页面, 修改密码后也需要跳转到这里，所以不能校验登录态"""
        old_password = xutils.get_argument("old_password", "")
        new_password = xutils.get_argument("new_password", "")
        return xtemplate.render("user/page/change_password.html",
                                old_password=old_password, new_password=new_password, error=error)

    @xauth.login_required()
    def POST(self):
        user_name = xauth.current_name()
        old_password = xutils.get_argument("old_password", "")
        new_password = xutils.get_argument("new_password", "")
        error = ""

        if old_password == "":
            return self.GET(error="旧的密码为空")
        if new_password == "":
            return self.GET(error="新的密码为空")

        try:
            xauth.check_old_password(user_name, old_password)
            xauth.update_user(user_name, Storage(password=new_password))
            create_op_log(user_name, "change_password", "修改密码")
        except Exception as e:
            return self.GET(error=str(e))

        return self.GET(error=error)


class UserOpLogHandler:

    @xauth.login_required()
    def GET(self):
        user_name = xauth.current_name()
        log_list = OP_LOG_TABLE.list_by_user(user_name, 0, 100, reverse=True)
        return xtemplate.render("user/page/user_op_log.html", log_list=log_list)


xurls = (
    r"/user/add",  AddHandler,
    r"/user/list",  ListHandler,
    r"/user/info",   UserInfoHandler,
    r"/user/session", SessionInfoAjaxHandler,
    r"/user/change_password", ChangePasswordHandler,
    r"/user/op_log", UserOpLogHandler,

    r"/system/user", UserHandler,
    r"/system/user/list", ListHandler,
    r"/system/user/remove", RemoveHandler,
)

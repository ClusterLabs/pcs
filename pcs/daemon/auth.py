from collections import namedtuple
from concurrent.futures import ProcessPoolExecutor
from ctypes import byref, cast, CDLL, CFUNCTYPE, POINTER, sizeof, Structure
from ctypes import c_char, c_char_p, c_int, c_uint, c_void_p
from ctypes.util import find_library
import grp
import pwd

from tornado.gen import coroutine

from pcs.daemon import log


class pam_message(Structure):
    _fields_ = [("msg_style", c_int), ("msg", POINTER(c_char))]

class pam_response(Structure):
    _fields_ = [("resp", POINTER(c_char)), ("resp_retcode", c_int)]

class pam_handle(Structure):
    _fields_ = [("handle", c_void_p)]

pam_conversation = CFUNCTYPE(
    c_int, #return value type
    c_int, #num_msg
    POINTER(POINTER(pam_message)), #msg
    POINTER(POINTER(pam_response)), #resp
    c_void_p, #appdata_ptr
)

class pam_conv(Structure):
    _fields_ = [("conv", pam_conversation), ("appdata_ptr", c_void_p)]

def prep_fn(fn, restype, argtypes):
    fn.restype = restype
    fn.argtypes = argtypes
    return fn

# c_char_p represents the C char * datatype when it points to a zero-terminated
# string. For a general character pointer that may also point to binary data,
# POINTER(c_char) must be used... and it is used for strdup
libc = CDLL(find_library("c"))
libpam = CDLL(find_library("pam"))
strdup = prep_fn(libc.strdup, POINTER(c_char), [c_char_p])
calloc = prep_fn(libc.calloc, c_void_p, [c_uint, c_uint])
pam_authenticate = prep_fn(libpam.pam_authenticate, c_int, [pam_handle, c_int])
pam_end = prep_fn(libpam.pam_end, c_int, [pam_handle, c_int])
pam_start = prep_fn(
    libpam.pam_start,
    c_int,
    [c_char_p, c_char_p, POINTER(pam_conv), POINTER(pam_handle)]
)

PAM_SUCCESS = 0
PAM_PROMPT_ECHO_OFF = 1
PCSD_SERVICE = "pcsd"
HA_ADM_GROUP = "haclient"# TODO use pacemaker_gname (??? + explanation why)

def authenticate_by_pam(username, password):
    @pam_conversation
    def conv(num_msg, msg, resp, appdata_ptr): # pylint: disable=unused-argument
        # it is: *resp = (pam_response *) calloc(num_msg, sizeof(pam_response))
        resp[0] = cast(
            calloc(num_msg, sizeof(pam_response)),
            POINTER(pam_response)
        )
        for i in range(num_msg):
            if msg[i].contents.msg_style == PAM_PROMPT_ECHO_OFF:
                resp.contents[i].resp = strdup(password.encode("utf8"))
                resp.contents[i].resp_retcode = 0
        return 0

    pamh = pam_handle()
    conversation = pam_conv(conv)
    returncode = pam_start(
        PCSD_SERVICE.encode("utf8"),
        username.encode("utf8"),
        byref(conversation),
        byref(pamh)
    )
    if returncode == PAM_SUCCESS:
        returncode = pam_authenticate(pamh, 0)
    pam_end(pamh, returncode)
    return returncode == PAM_SUCCESS

def get_user_groups_sync(username):
    return tuple([
        group.gr_name
        for group in grp.getgrall()
        if username in group.gr_mem
    ] + [
        # `group.gr_mem` does not contain the `username` when `group` is
        # primary for the `username` (the same is in /etc/group). So it is
        # necessary to add the primary group.
        grp.getgrgid(pwd.getpwnam(username).pw_gid).gr_name
    ])

UserAuthInfo = namedtuple("UserAuthInfo", "name groups is_authorized")

class LoginLogger:
    def unable_determine_groups(self, username, e):
        log.pcsd.info(
            "Unable to determine groups of user '%s': %s",
            username,
            e
        )
        log.pcsd.info(
            "Failed login by '%s' (unable to determine user's groups)",
            username
        )

    def not_ha_adm_member(self, username, ha_adm_group):
        log.pcsd.info(
            "Failed login by '%s' (user is not a member of '%s' group)",
            username,
            ha_adm_group
        )

    def success(self, username):
        log.pcsd.info("Successful login by '%s'", username)

class PlainLogger:
    def unable_determine_groups(self, username, e):
        log.pcsd.info(
            "Unable to determine groups of user '%s': %s",
            username,
            e
        )

    def not_ha_adm_member(self, username, ha_adm_group):
        log.pcsd.info(
            "User '%s' is not a member of '%s' group",
            username,
            ha_adm_group
        )

    def success(self, username):
        pass

def check_user_groups_sync(username, logger) -> UserAuthInfo:
    try:
        groups = get_user_groups_sync(username)
    except KeyError as e:
        logger.unable_determine_groups(username, e)
        return UserAuthInfo(username, [], is_authorized=False)

    if HA_ADM_GROUP not in groups:
        logger.not_ha_adm_member(username, HA_ADM_GROUP)
        return UserAuthInfo(username, groups, is_authorized=False)

    logger.success(username)
    return UserAuthInfo(username, groups, is_authorized=True)

def authorize_user_sync(username, password) -> UserAuthInfo:
    log.pcsd.info("Attempting login by '%s'", username)

    if not authenticate_by_pam(username, password):
        log.pcsd.info(
            "Failed login by '%s' (bad username or password)", username
        )
        return UserAuthInfo(username, [], is_authorized=False)

    return check_user_groups_sync(username, LoginLogger())

# TODO async/await version - how to do it?
# When async/await is used then the problem is:
# "TypeError: object Future can't be used in 'await' expression" is raised even
# if the function "convert_yielded" is used according to
# http://www.tornadoweb.org/en/stable/guide/coroutines.html#python-3-5-async-and-await
@coroutine
def run_in_process(sync_fn, *args):
    pool = ProcessPoolExecutor(max_workers=1)
    result = yield pool.submit(sync_fn, *args)
    pool.shutdown()
    return result

@coroutine
def authorize_user(username, password) -> UserAuthInfo:
    user = yield run_in_process(authorize_user_sync, username, password)
    return user

@coroutine
def check_user_groups(username) -> UserAuthInfo:
    user = yield run_in_process(check_user_groups_sync, username, PlainLogger())
    return user

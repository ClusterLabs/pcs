from ctypes import (
    CDLL,
    CFUNCTYPE,
    POINTER,
    Structure,
    byref,
    c_char,
    c_char_p,
    c_int,
    c_uint,
    c_void_p,
    cast,
    sizeof,
)
from ctypes.util import find_library

PAM_SUCCESS = 0
PAM_PROMPT_ECHO_OFF = 1
PCSD_SERVICE = "pcsd"


class pam_message(Structure):  # pylint: disable=invalid-name
    _fields_ = [("msg_style", c_int), ("msg", POINTER(c_char))]


class pam_response(Structure):  # pylint: disable=invalid-name
    _fields_ = [("resp", POINTER(c_char)), ("resp_retcode", c_int)]


class pam_handle(Structure):  # pylint: disable=invalid-name
    _fields_ = [("handle", c_void_p)]


pam_conversation = CFUNCTYPE(
    c_int,  # return value type
    c_int,  # num_msg
    POINTER(POINTER(pam_message)),  # msg
    POINTER(POINTER(pam_response)),  # resp
    c_void_p,  # appdata_ptr
)


class pam_conv(Structure):  # pylint: disable=invalid-name
    _fields_ = [("conv", pam_conversation), ("appdata_ptr", c_void_p)]


def _prep_fn(fn, restype, argtypes):  # pylint: disable=invalid-name
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


# c_char_p represents the C char * datatype when it points to a zero-terminated
# string. For a general character pointer that may also point to binary data,
# POINTER(c_char) must be used... and it is used for strdup
libc = CDLL(find_library("c"))
libpam = CDLL(find_library("pam"))
strdup = _prep_fn(libc.strdup, POINTER(c_char), [c_char_p])
calloc = _prep_fn(libc.calloc, c_void_p, [c_uint, c_uint])
pam_authenticate = _prep_fn(libpam.pam_authenticate, c_int, [pam_handle, c_int])
pam_acct_mgmt = _prep_fn(libpam.pam_acct_mgmt, c_int, [pam_handle, c_int])
pam_end = _prep_fn(libpam.pam_end, c_int, [pam_handle, c_int])
pam_start = _prep_fn(
    libpam.pam_start,
    c_int,
    [c_char_p, c_char_p, POINTER(pam_conv), POINTER(pam_handle)],
)


def authenticate_user(username: str, password: str) -> bool:
    @pam_conversation
    def conv(num_msg, msg, resp, appdata_ptr):
        del appdata_ptr
        # it is: *resp = (pam_response *) calloc(num_msg, sizeof(pam_response))
        resp[0] = cast(
            calloc(num_msg, sizeof(pam_response)), POINTER(pam_response)
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
        byref(pamh),
    )
    if returncode == PAM_SUCCESS:
        returncode = pam_authenticate(pamh, 0)
    if returncode == PAM_SUCCESS:
        returncode = pam_acct_mgmt(pamh, 0)
    pam_end(pamh, returncode)
    return returncode == PAM_SUCCESS

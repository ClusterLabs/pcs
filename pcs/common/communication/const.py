from .types import CommunicationResultStatus as Status

COM_STATUS_SUCCESS = Status("success")
COM_STATUS_INPUT_ERROR = Status("input_error")
COM_STATUS_UNKNOWN_CMD = Status("unknown_cmd")
COM_STATUS_ERROR = Status("error")
COM_STATUS_EXCEPTION = Status("exception")
COM_STATUS_NOT_AUTHORIZED = Status("not_authorized")

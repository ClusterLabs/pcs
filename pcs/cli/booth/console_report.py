from pcs.common.reports import codes

def format_booth_default(value, template):
    return "" if value in ("booth", "", None) else template.format(value)

#Each value (a callable taking report_item.info) returns a message.
#Force text will be appended if necessary.
#If it is necessary to put the force text inside the string then the callable
#must take the force_text parameter.
CODE_TO_MESSAGE_BUILDER_MAP = {
    codes.BOOTH_TICKET_OPERATION_FAILED: lambda info:
        (
            "unable to {operation} booth ticket '{ticket_name}'"
            " for site '{site_ip}', reason: {reason}"
        ).format(**info)

    ,
}

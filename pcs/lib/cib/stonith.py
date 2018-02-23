# TODO replace by the new finding function
def is_stonith_resource(resources_el, name):
    return len(
        resources_el.xpath(
            "primitive[@id='{0}' and @class='stonith']".format(name)
        )
    ) > 0

class DataTransferObject(object):
    def to_dict(self):
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, payload):
        raise NotImplementedError()


class ImplementsToDto(object):
    def to_dto(self):
        raise NotImplementedError()


class ImplementsFromDto(object):
    @classmethod
    def from_dto(cls, dto_obj):
        raise NotImplementedError()

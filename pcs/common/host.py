from collections import namedtuple

from pcs import settings


Destination = namedtuple("Destination", ["addr", "port"])


class PcsKnownHost(namedtuple("KnownHost", ["name", "token", "dest_list"])):
    @classmethod
    def from_known_host_file_dict(cls, name, known_host_dict):
        dest_list = [
            Destination(conn["addr"], conn["port"])
            for conn in known_host_dict["dest_list"]
        ]
        if not dest_list:
            raise KeyError("no destination defined")
        return cls(name, token=known_host_dict["token"], dest_list=dest_list)

    def to_known_host_dict(self):
        return (
            self.name,
            dict(
                token=self.token,
                dest_list=[
                    dict(addr=dest.addr, port=dest.port,)
                    for dest in self.dest_list
                ],
            ),
        )

    @property
    def dest(self):
        if self.dest_list:
            return self.dest_list[0]
        return Destination(self.name, settings.pcsd_default_port)

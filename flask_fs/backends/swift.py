import io
import logging

from contextlib import contextmanager
from dateutil import parser

import swiftclient

from . import BaseBackend

log = logging.getLogger(__name__)


class SwiftBackend(BaseBackend):
    """
    An OpenStack Swift backend

    Expect the following settings:

    - `authurl`: The Swift Auth URL.
    - `user`: The Swift user in.
    - `key`: The user API Key.
    - `auth_version`: The OpenStack auth version (optional, default: '3').
    - `os_options`: The OpenStack options as a dictonnary with keys such as
        'region_name' (optional, default: None).
    - `create_container`: Create the container if it does not
        exist (optional, default: False).
    """

    def __init__(self, name, config):
        super(SwiftBackend, self).__init__(name, config)

        auth_version = getattr(config, "auth_version", "3")
        self.conn = swiftclient.Connection(
            user=config.user,
            key=config.key,
            authurl=config.authurl,
            auth_version=auth_version,
            os_options={
                "tenant_name": getattr(config, "tenant_name", None),
                "region_name": getattr(config, "region_name", None),
            },
        )

        if getattr(config, "create_container", False):
            try:
                self.conn.head_container(self.name)
            except swiftclient.exceptions.ClientException:
                self.conn.put_container(self.name)

    def exists(self, filename):
        try:
            self.conn.head_object(self.name, filename)
            return True
        except swiftclient.ClientException:
            return False

    @contextmanager
    def open(self, filename, mode="r", encoding="utf8"):
        if "r" in mode:
            obj = self.read(filename)
            yield (
                io.BytesIO(obj)
                if "b" in mode
                else io.StringIO(obj.decode(encoding))
            )
        else:  # mode == 'w'
            f = io.BytesIO() if "b" in mode else io.StringIO()
            yield f
            self.write(filename, f.getvalue())

    def read(self, filename):
        _, data = self.conn.get_object(self.name, filename)
        return data

    def read_chunks(self, filename, chunks_size=1024 * 1024):
        _, data = self.conn.get_object(
            self.name, filename, resp_chunk_size=chunks_size
        )
        return data

    def write(self, filename, content):
        self.conn.put_object(
            self.name, filename, contents=self.as_binary(content)
        )

    def delete(self, filename):
        if self.exists(filename):
            self.conn.delete_object(self.name, filename)
        else:
            _, items = self.conn.get_container(self.name, path=filename)
            for i in items:
                self.conn.delete_object(self.name, i["name"])

    def copy(self, filename, target):
        dest = "/".join((self.name, target))
        self.conn.copy_object(self.name, filename, destination=dest)

    def list_files(self):
        _, items = self.conn.get_container(self.name)
        for i in items:
            yield i["name"]

    def get_metadata(self, filename):
        data = self.conn.head_object(self.name, filename)
        return {
            "checksum": "md5:{0}".format(data["etag"]),
            "size": int(data["content-length"]),
            "mime": data["content-type"],
            "modified": parser.parse(data["last-modified"]),
        }

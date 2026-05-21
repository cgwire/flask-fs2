import hashlib
import io
import logging

from contextlib import contextmanager
from dateutil import parser

import swiftclient

try:
    from gevent.queue import Queue as _Queue
    from gevent.queue import Empty as _QueueEmpty
except ImportError:
    from queue import Queue as _Queue
    from queue import Empty as _QueueEmpty

from . import BaseBackend

log = logging.getLogger(__name__)

DEFAULT_POOL_SIZE = 20
DEFAULT_TIMEOUT = 60
DEFAULT_RETRIES = 5
DEFAULT_POOL_TIMEOUT = 30
_READ_CHUNK = 1024 * 1024

ETAG_POLICY_LOG = "log"
ETAG_POLICY_RAISE = "raise"
ETAG_POLICY_RAISE_AND_DELETE = "raise_and_delete"
_ETAG_POLICIES = (
    ETAG_POLICY_LOG,
    ETAG_POLICY_RAISE,
    ETAG_POLICY_RAISE_AND_DELETE,
)
DEFAULT_ETAG_MISMATCH_POLICY = ETAG_POLICY_LOG


def _md5(data):
    try:
        return hashlib.md5(data, usedforsecurity=False)
    except TypeError:
        return hashlib.md5(data)


class PoolExhaustedError(Exception):
    """Raised when no Connection becomes available within pool_timeout."""


class SwiftBackend(BaseBackend):
    """
    An OpenStack Swift backend with a per-process Connection pool.

    The pool makes the backend safe under concurrent gevent / threaded workers
    where multiple greenlets or threads would otherwise share a single
    ``swiftclient.Connection`` and corrupt the underlying HTTP socket and
    auth-token state.

    Expect the following settings:

    - `authurl`: The Swift Auth URL.
    - `user`: The Swift user.
    - `key`: The user API Key.
    - `auth_version`: The OpenStack auth version (optional, default: '3').
    - `tenant_name`: OpenStack tenant/project (optional).
    - `region_name`: OpenStack region (optional).
    - `create_container`: Create the container if it does not exist
        (optional, default: False).
    - `pool_size`: Number of Connections kept in the pool per process
        (optional, default: 20).
    - `timeout`: Per-request socket timeout in seconds (optional, default: 60).
    - `retries`: Number of swiftclient retries on transient errors
        (optional, default: 5).
    - `pool_timeout`: Seconds to wait for a free Connection from the pool
        before raising ``PoolExhaustedError`` (optional, default: 30).
    - `os_options`: Extra OpenStack options dict merged over ``tenant_name``
        / ``region_name`` — needed for Keystone v3 (``user_domain_name``,
        ``project_domain_name``, ...).
    - `etag_mismatch_policy`: Behavior when the server-returned ETag differs
        from the locally computed MD5 (optional, default: ``"log"``). One of:

        * ``"log"`` — log an error, keep the object (legacy behavior).
        * ``"raise"`` — log + raise ``swiftclient.ClientException``, keep
          the object in Swift.
        * ``"raise_and_delete"`` — log + delete the object + raise
          ``swiftclient.ClientException``.
    """

    def __init__(self, name, config):
        super().__init__(name, config)

        self._auth_version = getattr(config, "auth_version", "3")
        self._user = config.user
        self._key = config.key
        self._authurl = config.authurl
        os_options = {
            "tenant_name": getattr(config, "tenant_name", None),
            "region_name": getattr(config, "region_name", None),
        }
        extra_os_options = getattr(config, "os_options", None)
        if extra_os_options:
            os_options.update(extra_os_options)
        self._os_options = os_options
        self._timeout = int(getattr(config, "timeout", DEFAULT_TIMEOUT))
        self._retries = int(getattr(config, "retries", DEFAULT_RETRIES))
        self._pool_size = int(getattr(config, "pool_size", DEFAULT_POOL_SIZE))
        self._pool_timeout = float(
            getattr(config, "pool_timeout", DEFAULT_POOL_TIMEOUT)
        )
        policy = getattr(
            config, "etag_mismatch_policy", DEFAULT_ETAG_MISMATCH_POLICY
        )
        if policy not in _ETAG_POLICIES:
            raise ValueError(
                "Invalid etag_mismatch_policy {0!r}, expected one of {1}".format(
                    policy, _ETAG_POLICIES
                )
            )
        self._etag_mismatch_policy = policy

        self._pool = _Queue(maxsize=self._pool_size)
        for _ in range(self._pool_size):
            self._pool.put(None)

        if getattr(config, "create_container", False):
            with self._borrow() as conn:
                try:
                    conn.head_container(self.name)
                except swiftclient.exceptions.ClientException:
                    conn.put_container(self.name)

    def _new_connection(self):
        return swiftclient.Connection(
            user=self._user,
            key=self._key,
            authurl=self._authurl,
            auth_version=self._auth_version,
            os_options=dict(self._os_options),
            timeout=self._timeout,
            retries=self._retries,
        )

    def _acquire_slot(self):
        try:
            return self._pool.get(timeout=self._pool_timeout)
        except _QueueEmpty:
            raise PoolExhaustedError(
                "Swift connection pool exhausted after %.1fs "
                "(pool_size=%d) — likely slot leak from an unclosed "
                "read_chunks() stream."
                % (self._pool_timeout, self._pool_size)
            )

    @contextmanager
    def _borrow(self):
        slot = self._acquire_slot()
        conn = slot if slot is not None else self._new_connection()
        keep = True
        try:
            yield conn
        except swiftclient.ClientException as e:
            status = getattr(e, "http_status", None)
            if status is None or status >= 500 or status in (401, 403):
                keep = False
            raise
        except (OSError, IOError):
            keep = False
            raise
        finally:
            if not keep:
                try:
                    conn.close()
                except Exception:
                    pass
                self._pool.put(None)
            else:
                self._pool.put(conn)

    def exists(self, filename):
        with self._borrow() as conn:
            try:
                conn.head_object(self.name, filename)
                return True
            except swiftclient.ClientException as e:
                status = getattr(e, "http_status", None)
                if status not in (404, None):
                    log.error(
                        "Error checking existence of %s in %s: %s",
                        filename,
                        self.name,
                        e,
                    )
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
        else:
            f = io.BytesIO() if "b" in mode else io.StringIO()
            yield f
            self.write(filename, f.getvalue())

    def read(self, filename):
        with self._borrow() as conn:
            _, data = conn.get_object(self.name, filename)
            return data

    def read_chunks(self, filename, chunks_size=_READ_CHUNK):
        slot = self._acquire_slot()
        conn = slot if slot is not None else self._new_connection()
        try:
            _, data = conn.get_object(
                self.name, filename, resp_chunk_size=chunks_size
            )
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            self._pool.put(None)
            raise
        return _PoolReleasingStream(data, self._pool, conn)

    def _release(self, conn, healthy):
        if not healthy:
            try:
                conn.close()
            except Exception:
                pass
            self._pool.put(None)
        else:
            self._pool.put(conn)

    def write(self, filename, content):
        binary = self.as_binary(content)
        content_length, etag = self._precompute(binary)

        with self._borrow() as conn:
            returned_etag = conn.put_object(
                self.name,
                filename,
                contents=binary,
                content_length=content_length,
                etag=etag,
            )
            if (
                etag
                and returned_etag
                and returned_etag.lower() != etag.lower()
            ):
                self._handle_etag_mismatch(
                    conn, filename, etag, returned_etag
                )

    def _handle_etag_mismatch(self, conn, filename, etag, returned_etag):
        message = (
            "ETag mismatch for {0} in {1}: local={2} remote={3}".format(
                filename, self.name, etag, returned_etag
            )
        )
        log.error(message)
        policy = self._etag_mismatch_policy
        if policy == ETAG_POLICY_LOG:
            return
        if policy == ETAG_POLICY_RAISE_AND_DELETE:
            try:
                conn.delete_object(self.name, filename)
            except swiftclient.ClientException:
                log.exception(
                    "Failed to delete corrupted object %s in %s",
                    filename,
                    self.name,
                )
        raise swiftclient.ClientException(message)

    def delete(self, filename):
        with self._borrow() as conn:
            if self._head(conn, filename):
                conn.delete_object(self.name, filename)
                return
            _, items = conn.get_container(self.name, path=filename)
            for i in items:
                conn.delete_object(self.name, i["name"])

    def _head(self, conn, filename):
        try:
            conn.head_object(self.name, filename)
            return True
        except swiftclient.ClientException:
            return False

    def copy(self, filename, target):
        dest = "/".join((self.name, target))
        with self._borrow() as conn:
            src_meta = conn.head_object(self.name, filename)
            response_headers = {}
            conn.copy_object(
                self.name,
                filename,
                destination=dest,
                response_dict=response_headers,
            )
            src_etag = (src_meta.get("etag") or "").lower()
            headers = response_headers.get("headers") or {}
            dst_etag = (headers.get("etag") or "").lower()
            if src_etag and dst_etag and src_etag != dst_etag:
                log.error(
                    "ETag mismatch on copy %s -> %s in %s: src=%s dst=%s",
                    filename,
                    target,
                    self.name,
                    src_etag,
                    dst_etag,
                )

    def list_files(self):
        with self._borrow() as conn:
            _, items = conn.get_container(self.name, full_listing=True)
        for i in items:
            yield i["name"]

    def get_metadata(self, filename):
        with self._borrow() as conn:
            data = conn.head_object(self.name, filename)
        return {
            "checksum": "md5:{0}".format(data["etag"]),
            "size": int(data["content-length"]),
            "mime": data["content-type"],
            "modified": parser.parse(data["last-modified"]),
        }

    def _precompute(self, binary):
        """Return (content_length, etag) for upload.

        Only bytes/bytearray are precomputed. File-likes are passed through
        to swiftclient unchanged (chunked transfer-encoding, no client-side
        ETag) to avoid reading the payload twice.
        """
        if isinstance(binary, (bytes, bytearray)):
            return len(binary), _md5(binary).hexdigest()
        return None, None


class _PoolReleasingStream:
    """Wrap a swiftclient chunk iterator so the Connection returns to the pool
    when the consumer finishes iterating or calls ``close()``.

    Callers must either iterate to completion or call ``close()`` explicitly;
    a dropped stream will leak its pool slot until process exit. This is
    deliberate: releasing the slot from ``__del__`` is unsafe under gevent
    because gc may run in an arbitrary greenlet/thread context.
    """

    def __init__(self, inner, pool, conn):
        self._inner = inner
        self._iter = iter(inner)
        self._pool = pool
        self._conn = conn
        self._released = False
        self._healthy = True

    def __iter__(self):
        return self

    def __next__(self):
        if self._released:
            raise StopIteration
        try:
            return next(self._iter)
        except StopIteration:
            self.close()
            raise
        except BaseException:
            self._healthy = False
            self.close()
            raise

    def close(self):
        if self._released:
            return
        self._released = True
        try:
            inner_close = getattr(self._inner, "close", None)
            if inner_close is not None:
                try:
                    inner_close()
                except Exception:
                    self._healthy = False
        finally:
            try:
                if self._healthy:
                    self._pool.put(self._conn)
                else:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                    self._pool.put(None)
            except Exception:
                log.exception(
                    "Failed to release Swift connection back to pool"
                )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self._healthy = False
        self.close()
        return False

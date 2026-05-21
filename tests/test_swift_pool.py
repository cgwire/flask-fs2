import pytest

try:
    import gevent

    HAS_GEVENT = True
except ImportError:
    HAS_GEVENT = False

pytestmark = pytest.mark.skipif(
    not HAS_GEVENT, reason="gevent is required for pool concurrency tests"
)

import swiftclient  # noqa: E402

from flask_fs.backends.swift import SwiftBackend  # noqa: E402
from flask_fs.storage import Config  # noqa: E402

USER = "test:tester"
KEY = "testing"
AUTHURL = "http://127.0.0.1:8085/auth/v1.0"


def _config(**overrides):
    cfg = {
        "user": USER,
        "key": KEY,
        "authurl": AUTHURL,
        "tenant_name": "",
        "region_name": "",
        "auth_version": 1,
        "create_container": True,
        "pool_size": 5,
    }
    cfg.update(overrides)
    return Config(cfg)


def _container_name(request):
    raw = "pooltest-{0}".format(request.function.__name__)
    return raw.replace("_", "-")


def _admin_conn():
    return swiftclient.Connection(
        user=USER, key=KEY, authurl=AUTHURL, auth_version=1
    )


def _drop_container(conn, name):
    try:
        _, items = conn.get_container(name, full_listing=True)
        for i in items:
            try:
                conn.delete_object(name, i["name"])
            except swiftclient.ClientException:
                pass
        conn.delete_container(name)
    except swiftclient.ClientException:
        pass


@pytest.fixture
def admin_conn():
    return _admin_conn()


@pytest.fixture
def container_name(request, admin_conn):
    name = _container_name(request)
    _drop_container(admin_conn, name)
    yield name
    _drop_container(admin_conn, name)


@pytest.fixture
def backend(container_name):
    return SwiftBackend(container_name, _config())


def _payload(i):
    return ("payload-{0}-".format(i) * 200).encode("utf-8")


def test_concurrent_writes(backend):
    keys = ["obj-{0}".format(i) for i in range(50)]
    payloads = [_payload(i) for i in range(50)]

    jobs = [gevent.spawn(backend.write, k, p) for k, p in zip(keys, payloads)]
    gevent.joinall(jobs, timeout=120)

    for j in jobs:
        assert j.successful(), "greenlet raised: {0}".format(j.exception)

    listed = set(backend.list_files())
    assert set(keys).issubset(listed), "missing keys: {0}".format(
        set(keys) - listed
    )

    for k, p in zip(keys, payloads):
        assert backend.read(k) == p, "content mismatch for {0}".format(k)


def test_concurrent_writes_then_reads(backend):
    keys = ["dual-{0}".format(i) for i in range(50)]
    payloads = [_payload(i) for i in range(50)]

    writes = [
        gevent.spawn(backend.write, k, p) for k, p in zip(keys, payloads)
    ]
    gevent.joinall(writes, timeout=120)
    for j in writes:
        assert j.successful(), "write failed: {0}".format(j.exception)

    reads = [gevent.spawn(backend.read, k) for k in keys]
    gevent.joinall(reads, timeout=120)

    for j, expected in zip(reads, payloads):
        assert j.successful(), "read failed: {0}".format(j.exception)
        assert j.value == expected, "content mix-up detected"


def test_etag_mismatch_raises_and_deletes(container_name, monkeypatch):
    backend = SwiftBackend(
        container_name, _config(etag_mismatch_policy="raise_and_delete")
    )
    original = swiftclient.Connection.put_object

    def liar(self, container, name, contents, **kwargs):
        original(self, container, name, contents, **kwargs)
        return "0" * 32

    monkeypatch.setattr(swiftclient.Connection, "put_object", liar)

    from flask_fs.backends.swift import ETagMismatchError

    with pytest.raises(ETagMismatchError) as exc:
        backend.write("bad-etag", b"hello world")
    assert "ETag mismatch" in str(exc.value)
    assert isinstance(exc.value, swiftclient.ClientException)

    assert not backend.exists("bad-etag")


def test_pool_size_respected(container_name):
    created = []

    class CountingBackend(SwiftBackend):
        def _new_connection(self):
            conn = super()._new_connection()
            created.append(id(conn))
            return conn

    backend = CountingBackend(container_name, _config(pool_size=2))

    def borrow_and_yield(i):
        with backend._borrow() as conn:
            gevent.sleep(0.05)
            conn.put_object(container_name, "k-{0}".format(i), contents=b"x")

    jobs = [gevent.spawn(borrow_and_yield, i) for i in range(10)]
    gevent.joinall(jobs, timeout=60)

    for j in jobs:
        assert j.successful(), "borrow failed: {0}".format(j.exception)

    assert (
        len(created) <= 2
    ), "pool created {0} connections, expected <= 2".format(len(created))
    assert len(set(created)) == len(
        created
    ), "_new_connection returned duplicates"

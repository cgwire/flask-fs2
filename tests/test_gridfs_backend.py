from gridfs import GridFS
from pymongo import MongoClient
import hashlib

from .test_backend_mixin import BackendTestCase

from flask_fs.backends.gridfs import GridFsBackend
from flask_fs.storage import Config

import pytest
import mimetypes

TEST_DB = "fstest"


class GridFsBackendTest(BackendTestCase):
    hasher = "md5"

    @pytest.fixture
    def pngimage(self, pngfile):
        with open(pngfile, "rb") as f:
            yield f

    @pytest.fixture
    def jpgimage(self, jpgfile):
        with open(jpgfile, "rb") as f:
            yield f

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = MongoClient()
        self.db = self.client[TEST_DB]
        self.gfs = GridFS(self.db, "test")

        self.config = Config(
            {
                "mongo_url": "mongodb://localhost:27017",
                "mongo_db": TEST_DB,
            }
        )
        self.backend = GridFsBackend("test", self.config)
        yield
        self.client.drop_database(TEST_DB)

    def put_file(self, filename, content):
        hasher = getattr(hashlib, self.hasher)
        if isinstance(content, str):
            hashed = hasher(content.encode("utf8")).hexdigest()
        else:
            hashed = hasher(content).hexdigest()
        self.gfs.put(content, filename=filename, encoding="utf-8", md5=hashed)

    def get_file(self, filename):
        file = self.gfs.get_last_version(filename)
        assert file is not None
        return file.read()

    def file_exists(self, filename):
        return self.gfs.exists(filename=filename)

    def test_default_bucket(self):
        backend = GridFsBackend("test_bucket", self.config)
        assert backend.fs._GridFS__collection.name == "test_bucket"

    def test_config(self):
        self.backend.client.start_session()
        assert self.backend.client.address == ("localhost", 27017)
        assert self.backend.db.name == TEST_DB

    def test_delete_with_versions(self, faker):
        filename = "test.txt"
        self.put_file(filename, faker.sentence())
        self.put_file(filename, faker.sentence())
        assert len(list(self.gfs.find({"filename": filename}))) == 2

        self.backend.delete(filename)
        assert not self.file_exists(filename)

    def test_write_pngimage(self, pngimage, utils):
        filename = "test.png"
        content = bytes(pngimage.read())
        content_type = mimetypes.guess_type(filename)[0]
        f = utils.filestorage(filename, content, content_type)
        self.backend.write(filename, f)

        with self.backend.open(filename, "rb") as f:
            assert f.content_type == content_type

        self.assert_bin_equal(filename, content)

    def test_write_jpgimage(self, jpgimage, utils):
        filename = "test.jpg"
        content = bytes(jpgimage.read())
        content_type = mimetypes.guess_type(filename)[0]
        f = utils.filestorage(filename, content, content_type)
        self.backend.write(filename, f)

        with self.backend.open(filename, "rb") as f:
            assert f.content_type == content_type

        self.assert_bin_equal(filename, content)

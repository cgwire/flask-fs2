import os
import time
import typing
import base64
import binascii
import io
import tempfile

from cryptography import utils
from cryptography.fernet import InvalidToken, _MAX_CLOCK_SKEW
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.hmac import HMAC
from pathlib import Path


class AES256FileEncryptor:
    def __init__(
        self,
        key: typing.Union[bytes, str],
    ) -> None:
        try:
            key = base64.urlsafe_b64decode(key)
        except binascii.Error as exc:
            raise ValueError(
                "Fernet key must be 32 url-safe base64-encoded bytes."
            ) from exc
        if len(key) != 32:
            raise ValueError(
                "Fernet key must be 32 url-safe base64-encoded bytes."
            )

        self._signing_key = key[:16]
        self._encryption_key = key[16:]

    @classmethod
    def generate_key(cls) -> bytes:
        return base64.urlsafe_b64encode(os.urandom(32))

    def encrypt_content(
        self,
        content: bytes,
    ) -> bytes:
        utils._check_bytes("data", content)

        current_time = int(time.time())
        iv = os.urandom(16)
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(content) + padder.finalize()
        encryptor = Cipher(
            algorithms.AES(self._encryption_key),
            modes.CBC(iv),
        ).encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        basic_parts = (
            b"\x80"
            + current_time.to_bytes(length=8, byteorder="big")
            + iv
            + ciphertext
        )

        h = HMAC(self._signing_key, hashes.SHA256())
        h.update(basic_parts)
        hmac = h.finalize()
        return basic_parts + hmac

    def encrypt_file(
        self,
        src_content: typing.Union[Path, str, io.TextIOBase],
        dest_file_path: typing.Union[Path, str] = None,
        chunk_size: int = 1024 * algorithms.AES.block_size,
    ) -> typing.Union[Path, str]:
        if hasattr(src_content, "read"):
            src_stream = src_content
        elif os.path.isfile(src_content):
            src_stream = open(src_content, "rb")
        else:
            raise TypeError(
                "src_content must be a file stream or a pathlike object."
            )

        if dest_file_path is not None:
            dest_stream = open(dest_file_path, "wb")
        else:
            dest_stream = tempfile.NamedTemporaryFile(delete=False)
            dest_file_path = dest_stream.name

        current_time = int(time.time())
        iv = os.urandom(16)
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        encryptor = Cipher(
            algorithms.AES(self._encryption_key), modes.CBC(iv)
        ).encryptor()
        h = HMAC(self._signing_key, hashes.SHA256())

        with src_stream as src_file, dest_stream as dest_file:
            basic_parts = (
                b"\x80"
                + int(current_time).to_bytes(length=8, byteorder="big")
                + iv
            )
            h.update(basic_parts)
            dest_file.write(basic_parts)

            while chunk := src_file.read(chunk_size):
                padded_data = padder.update(chunk)
                ciphertext = encryptor.update(padded_data)
                h.update(ciphertext)
                dest_file.write(ciphertext)

            last_chunk = (
                encryptor.update(padder.finalize()) + encryptor.finalize()
            )
            h.update(last_chunk)
            hmac = h.finalize()
            dest_file.write(last_chunk + hmac)

        return dest_file_path

    def decrypt_file(
        self,
        src_file_path: typing.Union[Path, str],
        dest_file_path: typing.Union[Path, str],
        ttl: typing.Optional[int] = None,
        chunk_size: int = 1024 * algorithms.AES.block_size,
    ) -> typing.Union[Path, str]:
        def create_generator() -> typing.Generator:
            with open(src_file_path, "rb") as src_file:
                while data := src_file.read(chunk_size):
                    yield data

        with open(dest_file_path, "wb") as dest_file:
            for chunk in self.decrypt_file_from_generator(
                create_generator(), ttl
            ):
                dest_file.write(chunk)

        return dest_file_path

    def decrypt_file_from_generator(
        self,
        file_generator: typing.Generator,
        ttl: typing.Optional[int] = None,
    ) -> Path:
        h = HMAC(self._signing_key, hashes.SHA256())

        chunk = next(file_generator, None)

        if chunk is None or len(chunk) < 25 or chunk[0] != 0x80:
            raise InvalidToken

        header, chunk = chunk[:25], chunk[25:]
        h.update(header)

        timestamp = int.from_bytes(header[1:9], byteorder="big")

        if ttl is not None:
            current_time = int(time.time())
            if timestamp + ttl < current_time:
                raise InvalidToken

            if current_time + _MAX_CLOCK_SKEW < timestamp:
                raise InvalidToken

        iv = header[9:25]
        decryptor = Cipher(
            algorithms.AES(self._encryption_key), modes.CBC(iv)
        ).decryptor()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()

        while chunk is not None:
            next_chunk = next(file_generator, None)
            if next_chunk is None:
                hmac = chunk[-32:]
                chunk = chunk[:-32]

            h.update(chunk)
            try:
                decrypted_data = unpadder.update(decryptor.update(chunk))
                if decrypted_data:
                    yield decrypted_data
            except ValueError:
                raise InvalidToken

            chunk = next_chunk

        try:
            decrypted_data = (
                unpadder.update(decryptor.finalize()) + unpadder.finalize()
            )
        except ValueError:
            raise InvalidToken

        try:
            h.verify(hmac)
        except InvalidSignature:
            raise InvalidToken

        yield decrypted_data

    def decrypt_entire_file(
        self, file_data: bytes, ttl: typing.Optional[int] = None
    ):
        return b"".join(
            self.decrypt_file_from_generator(iter([file_data]), ttl)
        )

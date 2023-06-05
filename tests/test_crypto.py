import pytest
import tempfile
import os
from flask_fs.crypto import AES256FileEncryptor


@pytest.fixture
def encryptor():
    key = AES256FileEncryptor.generate_key()
    return AES256FileEncryptor(key)


@pytest.fixture
def plaintext_file():
    with tempfile.NamedTemporaryFile(delete=False) as file:
        file.write(b"Hello, World!")
        file.close()
        yield file.name
        os.unlink(file.name)


@pytest.fixture
def encrypted_file(encryptor, plaintext_file):
    with tempfile.NamedTemporaryFile(delete=False) as file:
        encryptor.encrypt_file(plaintext_file, file.name)
        file.close()
        yield file.name
        os.unlink(file.name)


def test_encrypt_content(encryptor):
    content = b"Hello, World!"
    encrypted_content = encryptor.encrypt_content(content)
    assert encrypted_content != content


def test_encrypt_file(encryptor, plaintext_file):
    encrypted_file_path = encryptor.encrypt_file(
        plaintext_file, "encrypted.bin"
    )
    assert os.path.exists(encrypted_file_path)
    assert os.path.getsize(encrypted_file_path) > 0


def test_decrypt_file(encryptor, encrypted_file):
    decrypted_file_path = encryptor.decrypt_file(
        encrypted_file, "decrypted.txt"
    )
    assert os.path.exists(decrypted_file_path)
    assert os.path.getsize(decrypted_file_path) > 0

    with open(decrypted_file_path, "rb") as file:
        decrypted_content = file.read()

    assert decrypted_content == b"Hello, World!"


def test_decrypt_entire_file(encryptor, encrypted_file):
    with open(encrypted_file, "rb") as file:
        encrypted_content = file.read()

    decrypted_content = encryptor.decrypt_entire_file(encrypted_content)
    assert decrypted_content == b"Hello, World!"


def test_decrypt_file_invalid_token(encryptor, plaintext_file):
    encrypted_file_path = encryptor.encrypt_file(
        plaintext_file, "encrypted.bin"
    )

    with open(encrypted_file_path, "r+b") as file:
        file.seek(10)
        file.write(b"\x00")  # Modify one byte in the IV

    with pytest.raises(Exception):
        encryptor.decrypt_file(encrypted_file_path, "decrypted.txt")


def test_already_encrypted_file():
    key = b"jHEyo0GjTZDCUEnCkMcaF-LIxmnOix8b3JH633I7dls="
    encryptor = AES256FileEncryptor(key)

    with open(
        os.path.join(os.path.dirname(__file__), "test.encrypted"), "rb"
    ) as encrypted_file:
        encrypted_content = encrypted_file.read()

    assert b"It's an encrypted file." == encryptor.decrypt_entire_file(
        encrypted_content
    )

"""Scrypt password records shared by the web process and the offline VM setup."""
import hashlib
import hmac
import secrets


def digest(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768,
                          r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024).hex()


def encode(password):
    salt = secrets.token_hex(16)
    return salt + ":" + digest(password, salt)


def matches(password, record):
    salt, expected = record.split(":")
    return hmac.compare_digest(digest(password, salt), expected)


# Copyright 2013 Donald Stufft and individual contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import nacl.bindings
from nacl import encoding
from nacl import exceptions as exc
from nacl.utils import EncryptedMessage, StringFixer, random


class SecretBox(encoding.Encodable, StringFixer):
    """
    The SecretBox class encrypts and decrypts messages using the given secret
    key.

    The ciphertexts generated by :class:`~nacl.secret.Secretbox` include a 16
    byte authenticator which is checked as part of the decryption. An invalid
    authenticator will cause the decrypt function to raise an exception. The
    authenticator is not a signature. Once you've decrypted the message you've
    demonstrated the ability to create arbitrary valid message, so messages you
    send are repudiable. For non-repudiable messages, sign them after
    encryption.

    Encryption is done using `XSalsa20-Poly1305`_, and there are no practical
    limits on the number or size of messages (up to 2⁶⁴ messages, each up to 2⁶⁴
    bytes).

    .. _XSalsa20-Poly1305: https://doc.libsodium.org/secret-key_cryptography/secretbox#algorithm-details

    :param key: The secret key used to encrypt and decrypt messages
    :param encoder: The encoder class used to decode the given key

    :cvar KEY_SIZE: The size that the key is required to be.
    :cvar NONCE_SIZE: The size that the nonce is required to be.
    :cvar MACBYTES: The size of the authentication MAC tag in bytes.
    :cvar MESSAGEBYTES_MAX: The maximum size of a message which can be
                            safely encrypted with a single key/nonce
                            pair.
    """

    KEY_SIZE = nacl.bindings.crypto_secretbox_KEYBYTES
    NONCE_SIZE = nacl.bindings.crypto_secretbox_NONCEBYTES
    MACBYTES = nacl.bindings.crypto_secretbox_MACBYTES
    MESSAGEBYTES_MAX = nacl.bindings.crypto_secretbox_MESSAGEBYTES_MAX

    def __init__(self, key, encoder=encoding.RawEncoder):
        key = encoder.decode(key)
        if not isinstance(key, bytes):
            raise exc.TypeError("SecretBox must be created from 32 bytes")

        if len(key) != self.KEY_SIZE:
            raise exc.ValueError(
                "The key must be exactly %s bytes long" % self.KEY_SIZE,
            )

        self._key = key

    def __bytes__(self):
        return self._key

    def encrypt(self, plaintext, nonce=None, encoder=encoding.RawEncoder):
        """
        Encrypts the plaintext message using the given `nonce` (or generates
        one randomly if omitted) and returns the ciphertext encoded with the
        encoder.

        .. warning:: It is **VITALLY** important that the nonce is a nonce,
            i.e. it is a number used only once for any given key. If you fail
            to do this, you compromise the privacy of the messages encrypted.
            Give your nonces a different prefix, or have one side use an odd
            counter and one an even counter. Just make sure they are different.

        :param plaintext: [:class:`bytes`] The plaintext message to encrypt
        :param nonce: [:class:`bytes`] The nonce to use in the encryption
        :param encoder: The encoder to use to encode the ciphertext
        :rtype: [:class:`nacl.utils.EncryptedMessage`]
        """
        if nonce is None:
            nonce = random(self.NONCE_SIZE)

        if len(nonce) != self.NONCE_SIZE:
            raise exc.ValueError(
                "The nonce must be exactly %s bytes long" % self.NONCE_SIZE,
            )

        ciphertext = nacl.bindings.crypto_secretbox(
            plaintext, nonce, self._key
        )

        encoded_nonce = encoder.encode(nonce)
        encoded_ciphertext = encoder.encode(ciphertext)

        return EncryptedMessage._from_parts(
            encoded_nonce,
            encoded_ciphertext,
            encoder.encode(nonce + ciphertext),
        )

    def decrypt(self, ciphertext, nonce=None, encoder=encoding.RawEncoder):
        """
        Decrypts the ciphertext using the `nonce` (explicitly, when passed as a
        parameter or implicitly, when omitted, as part of the ciphertext) and
        returns the plaintext message.

        :param ciphertext: [:class:`bytes`] The encrypted message to decrypt
        :param nonce: [:class:`bytes`] The nonce used when encrypting the
            ciphertext
        :param encoder: The encoder used to decode the ciphertext.
        :rtype: [:class:`bytes`]
        """
        # Decode our ciphertext
        ciphertext = encoder.decode(ciphertext)

        if nonce is None:
            # If we were given the nonce and ciphertext combined, split them.
            nonce = ciphertext[: self.NONCE_SIZE]
            ciphertext = ciphertext[self.NONCE_SIZE :]

        if len(nonce) != self.NONCE_SIZE:
            raise exc.ValueError(
                "The nonce must be exactly %s bytes long" % self.NONCE_SIZE,
            )

        plaintext = nacl.bindings.crypto_secretbox_open(
            ciphertext, nonce, self._key
        )

        return plaintext


class Aead(encoding.Encodable, StringFixer, object):
    """
    The AEAD class encrypts and decrypts messages using the given secret key.

    Unlike :class:`~nacl.secret.SecretBox`, AEAD supports authenticating
    non-confidential data received alongside the message, such as a length
    or type tag.

    Like :class:`~nacl.secret.Secretbox`, this class provides authenticated
    encryption. An inauthentic message will cause the decrypt function to raise
    an exception.

    Likewise, the authenticator should not be mistaken for a (public-key)
    signature: recipients (with the ability to decrypt messages) are capable of
    creating arbitrary valid message; in particular, this means AEAD messages
    are repudiable. For non-repudiable messages, sign them after encryption.

    The cryptosystem used is `XChacha20-Poly1305`_ as specified for
    `standardization`_. There are `no practical limits`_ to how much can safely
    be encrypted under a given key (up to 2⁶⁴ messages each containing up
    to 2⁶⁴ bytes).

    .. _standardization: https://datatracker.ietf.org/doc/html/draft-irtf-cfrg-xchacha
    .. _XChacha20-Poly1305: https://doc.libsodium.org/secret-key_cryptography/aead#xchacha-20-poly1305
    .. _no practical limits: https://doc.libsodium.org/secret-key_cryptography/aead#limitations

    :param key: The secret key used to encrypt and decrypt messages
    :param encoder: The encoder class used to decode the given key

    :cvar KEY_SIZE: The size that the key is required to be.
    :cvar NONCE_SIZE: The size that the nonce is required to be.
    :cvar MACBYTES: The size of the authentication MAC tag in bytes.
    :cvar MESSAGEBYTES_MAX: The maximum size of a message which can be
                            safely encrypted with a single key/nonce
                            pair.
    """

    KEY_SIZE = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_KEYBYTES
    NONCE_SIZE = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
    MACBYTES = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_ABYTES
    MESSAGEBYTES_MAX = (
        nacl.bindings.crypto_aead_xchacha20poly1305_ietf_MESSAGEBYTES_MAX
    )

    def __init__(self, key, encoder=encoding.RawEncoder):
        key = encoder.decode(key)
        if not isinstance(key, bytes):
            raise exc.TypeError("AEAD must be created from 32 bytes")

        if len(key) != self.KEY_SIZE:
            raise exc.ValueError(
                "The key must be exactly %s bytes long" % self.KEY_SIZE,
            )

        self._key = key

    def __bytes__(self):
        return self._key

    def encrypt(
        self, plaintext, aad=b"", nonce=None, encoder=encoding.RawEncoder
    ):
        """
        Encrypts the plaintext message using the given `nonce` (or generates
        one randomly if omitted) and returns the ciphertext encoded with the
        encoder.

        .. warning:: It is vitally important for :param nonce: to be unique.
            By default, it is generated randomly; [:class:`Aead`] uses XChacha20
            for extended (192b) nonce size, so the risk of reusing random nonces
            is negligible.  It is *strongly recommended* to keep this behaviour,
            as nonce reuse will compromise the privacy of encrypted messages.
            Should implicit nonces be inadequate for your application, the
            second best option is using split counters; e.g. if sending messages
            encrypted under a shared key between 2 users, each user can use the
            number of messages it sent so far, prefixed or suffixed with a 1bit
            user id.  Note that the counter must **never** be rolled back (due
            to overflow, on-disk state being rolled back to an earlier backup,
            ...)

        :param plaintext: [:class:`bytes`] The plaintext message to encrypt
        :param nonce: [:class:`bytes`] The nonce to use in the encryption
        :param encoder: The encoder to use to encode the ciphertext
        :rtype: [:class:`nacl.utils.EncryptedMessage`]
        """
        if nonce is None:
            nonce = random(self.NONCE_SIZE)

        if len(nonce) != self.NONCE_SIZE:
            raise exc.ValueError(
                "The nonce must be exactly %s bytes long" % self.NONCE_SIZE,
            )

        ciphertext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
            plaintext, aad, nonce, self._key
        )

        encoded_nonce = encoder.encode(nonce)
        encoded_ciphertext = encoder.encode(ciphertext)

        return EncryptedMessage._from_parts(
            encoded_nonce,
            encoded_ciphertext,
            encoder.encode(nonce + ciphertext),
        )

    def decrypt(
        self, ciphertext, aad=b"", nonce=None, encoder=encoding.RawEncoder
    ):
        """
        Decrypts the ciphertext using the `nonce` (explicitly, when passed as a
        parameter or implicitly, when omitted, as part of the ciphertext) and
        returns the plaintext message.

        :param ciphertext: [:class:`bytes`] The encrypted message to decrypt
        :param nonce: [:class:`bytes`] The nonce used when encrypting the
            ciphertext
        :param encoder: The encoder used to decode the ciphertext.
        :rtype: [:class:`bytes`]
        """
        # Decode our ciphertext
        ciphertext = encoder.decode(ciphertext)

        if nonce is None:
            # If we were given the nonce and ciphertext combined, split them.
            nonce = ciphertext[: self.NONCE_SIZE]
            ciphertext = ciphertext[self.NONCE_SIZE :]

        if len(nonce) != self.NONCE_SIZE:
            raise exc.ValueError(
                "The nonce must be exactly %s bytes long" % self.NONCE_SIZE,
            )

        plaintext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
            ciphertext, aad, nonce, self._key
        )

        return plaintext

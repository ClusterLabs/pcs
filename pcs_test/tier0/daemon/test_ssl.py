import os
import ssl
from unittest import (
    TestCase,
    mock,
)

from pcs.daemon.ssl import (
    CertKeyPair,
    PcsdSSL,
    SSLCertKeyException,
)

from pcs_test.tools.misc import get_tmp_dir

SERVER_NAME = "pcsd-daemon"
SSL_OPTIONS = 0
SSL_CIPHERS = "DEFAULT:!RC4"


class SslFilesMixin:
    def setUp(self):
        self.ssl_dir = get_tmp_dir("tier0_daemon_ssl")
        self.cert_path = os.path.join(self.ssl_dir.name, "daemon.cert")
        self.key_path = os.path.join(self.ssl_dir.name, "daemon.key")

    def tearDown(self):
        self.ssl_dir.cleanup()

    def damage_ssl_files(self):
        with open(self.cert_path, "w") as cert:
            cert.write("bad content")
        with open(self.key_path, "w") as key:
            key.write("bad content")


class Pair(SslFilesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pair = CertKeyPair(self.cert_path, self.key_path)

    def test_generated_key_check_success(self):
        self.pair.regenerate(SERVER_NAME)
        self.assertEqual(self.pair.check(), [])

    def test_error_if_files_with_bad_content(self):
        self.damage_ssl_files()
        errors = self.pair.check()
        self.assertEqual(len(errors), 1)
        self.assertRegex(
            errors[0],
            r"^SSL certificate does not match the key: "
            r"\[SSL\] PEM lib \(_ssl\.c:\d+\)",
        )

    @mock.patch("pcs.daemon.ssl.ssl.SSLContext.load_cert_chain")
    def test_error_if_short_key(self, mock_load_cert_chain):
        mock_load_cert_chain.side_effect = ssl.SSLError(
            # These are the real args of the exception.
            336245135,
            "[SSL: EE_KEY_TOO_SMALL] ee key too small (_ssl.c:3542)",
        )
        # If a short key, which would cause the SSL library error, is used,
        # then we get a FIPS error instead. If a key long enough for FIPS is
        # used, then the SSL library doesn't produce any error, as the key is
        # sufficiently long for it. Therefore, we use a key long enough for
        # FIPS, and mock SSL library to throw an error.
        self.pair.regenerate(SERVER_NAME, 2048)
        errors = self.pair.check()
        self.assertEqual(
            errors,
            [
                "SSL certificate does not match the key: "
                "[SSL: EE_KEY_TOO_SMALL] ee key too small (_ssl.c:3542)",
            ],
        )

    def test_error_if_cert_does_not_match_key(self):
        self.pair.regenerate(SERVER_NAME)
        with open(self.key_path, "rb") as key_file:
            key_content = key_file.read()
        self.pair.regenerate(SERVER_NAME)
        with open(self.key_path, "wb") as key_file:
            key_file.write(key_content)

        errors = self.pair.check()
        self.assertEqual(len(errors), 1)
        self.assertRegex(
            errors[0],
            r"SSL certificate does not match the key: "
            r"\[X509: KEY_VALUES_MISMATCH\] key values mismatch \(_ssl\.c:\d+\)",
        )


class PcsdSSLTest(SslFilesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pcsd_ssl = PcsdSSL(
            SERVER_NAME, self.cert_path, self.key_path, SSL_OPTIONS, SSL_CIPHERS
        )

    def test_is_ok_when_ssl_files_does_not_exist(self):
        self.pcsd_ssl.guarantee_valid_certs()

    def test_raises_when_ssl_files_are_damaged(self):
        self.damage_ssl_files()
        with self.assertRaises(SSLCertKeyException) as ctx_manager:
            self.pcsd_ssl.guarantee_valid_certs()
        errors = ctx_manager.exception.args
        self.assertEqual(len(errors), 1)
        self.assertRegex(
            errors[0],
            r"SSL certificate does not match the key: "
            r"\[SSL\] PEM lib \(_ssl\.c:\d+\)",
        )

    def test_context_uses_given_options(self):
        self.pcsd_ssl.guarantee_valid_certs()
        ssl_context = self.pcsd_ssl.create_context()
        self.assertEqual(ssl_context.options, SSL_OPTIONS)

import os
from unittest import mock, TestCase

from OpenSSL import SSL

from pcs_test.tools.misc import get_tmp_dir

from pcs.daemon.ssl import PcsdSSL, CertKeyPair, SSLCertKeyException

SERVER_NAME = "pcsd-daemon"
SSL_OPTIONS = 0
SSL_CIPHERS = "DEFAULT:!RC4"


class SslFilesMixin:
    def setUp(self):
        # pylint cannot possibly know this is being mixed into TestCase classes
        # pylint: disable=invalid-name
        self.ssl_dir = get_tmp_dir("tier0_daemon_ssl")
        self.cert_path = os.path.join(self.ssl_dir.name, "daemon.cert")
        self.key_path = os.path.join(self.ssl_dir.name, "daemon.key")
        # various versions of OpenSSL / PyOpenSSL emit different messages
        self.DAMAGED_SSL_FILES_ERRORS_1 = (
            f"Invalid SSL certificate '{self.cert_path}':"
            " 'PEM routines:PEM_read_bio:no start line'",
            f"Invalid SSL key '{self.key_path}':"
            " 'PEM routines:PEM_read_bio:no start line'",
        )
        self.DAMAGED_SSL_FILES_ERRORS_2 = (
            f"Invalid SSL certificate '{self.cert_path}':"
            " 'PEM routines:get_name:no start line'",
            f"Invalid SSL key '{self.key_path}':"
            " 'PEM routines:get_name:no start line'",
        )

    def tearDown(self):
        # pylint cannot possibly know this is being mixed into TestCase classes
        # pylint: disable=invalid-name
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
        self.assertTrue(
            self.pair.check()
            in [
                list(self.DAMAGED_SSL_FILES_ERRORS_1),
                list(self.DAMAGED_SSL_FILES_ERRORS_2),
            ]
        )

    @mock.patch("pcs.daemon.ssl.SSL.Context.use_privatekey")
    def test_error_if_short_key(self, mock_use_key):
        mock_use_key.side_effect = SSL.Error("reason")
        self.pair.regenerate(SERVER_NAME, 1024)
        errors = self.pair.check()
        self.assertEqual(
            errors, ["Unable to load SSL certificate and/or key: reason"]
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
        self.assertTrue(
            errors[0].startswith("SSL certificate does not match the key:")
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
        self.assertTrue(
            ctx_manager.exception.args
            in [
                self.DAMAGED_SSL_FILES_ERRORS_1,
                self.DAMAGED_SSL_FILES_ERRORS_2,
            ]
        )

    def test_context_uses_given_options(self):
        self.pcsd_ssl.guarantee_valid_certs()
        ssl_context = self.pcsd_ssl.create_context()
        self.assertEqual(ssl_context.options, SSL_OPTIONS)

import os
import ssl
from unittest import TestCase

from pcs.daemon.ssl import PcsdSSL
from pcs.test.tools.misc import get_test_resource as rc

CERT = rc("daemon.cert")
KEY = rc("daemon.key")

SERVER_NAME = "pcsd-daemon"

class CheckCertKey(TestCase):
    def setUp(self):
        self.remove_cert_key()
        self.pcsd_ssl = PcsdSSL(CERT, KEY)

    def tearDown(self):
        self.remove_cert_key()

    def remove_cert_key(self):
        if os.path.exists(CERT):
            os.remove(CERT)
        if os.path.exists(KEY):
            os.remove(KEY)

    def test_generated_key_check_success(self):
        self.pcsd_ssl.regenerate_cert_key(SERVER_NAME)
        self.assertEqual(self.pcsd_ssl.check_cert_key(), [])

    def test_error_if_files_not_found(self):
        no_such_file = "[Errno 2] No such file or directory: "
        self.assertEqual(self.pcsd_ssl.check_cert_key(), [
            f"Unable to read certificate: '{no_such_file}'{CERT}''",
            f"Unable to read key: '{no_such_file}'{KEY}''",
        ])

    def test_error_if_cert_does_not_match_key(self):
        self.pcsd_ssl.regenerate_cert_key(SERVER_NAME)
        with open(KEY, "rb") as key_file:
            key_content = key_file.read()
        self.pcsd_ssl.regenerate_cert_key(SERVER_NAME)
        with open(KEY, "wb") as key_file:
            key_file.write(key_content)

        self.assertEqual(self.pcsd_ssl.check_cert_key(), [
            "Certificate does not match the key"
        ])

    def test_context_uses_given_options(self):
        self.pcsd_ssl.regenerate_cert_key(SERVER_NAME)
        ciphers = "DEFAULT:!RC4"
        options = ssl.OP_NO_SSLv2
        ssl_context = self.pcsd_ssl.create_context(options, ciphers)
        self.assertEqual(ssl_context.options, options)

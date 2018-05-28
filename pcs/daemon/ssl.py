import os
import ssl
from time import time, gmtime, strftime

from OpenSSL import crypto, SSL

def cert_date_format(timestamp):
    return str.encode(strftime("%Y%m%d%H%M%SZ", gmtime(timestamp)))

def generate_key():
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    return key

def generate_cert(key, server_name):
    now = time()
    cert = crypto.X509()

    subject = cert.get_subject()
    subject.countryName = "US"
    subject.stateOrProvinceName = "MN"
    subject.localityName = "Minneapolis"
    subject.organizationName = "pcsd"
    subject.organizationalUnitName = "pcsd"
    subject.commonName = server_name

    cert.set_version(2)
    cert.set_serial_number(int(now*1000))
    cert.set_notBefore(cert_date_format(now))
    cert.set_notAfter(cert_date_format(now + 60*60*24*365*10)) # 10 years
    cert.set_issuer(subject)
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')

    return cert

def check_cert_key(cert_path, key_path):
    errors = []
    def load(load_ssl_file, label, path):
        try:
            with open(path) as ssl_file:
                return load_ssl_file(crypto.FILETYPE_PEM, ssl_file.read())
        except EnvironmentError as e:
            errors.append(f"Unable to read SSL {label} '{path}': '{e}'")
        except crypto.Error as e:
            msg = ""
            if e.args and e.args[0] and e.args[0][0]:
                msg = f": '{':'.join(e.args[0][0])}'"
            errors.append(f"Invalid SSL {label} '{path}'{msg}")

    cert = load(crypto.load_certificate, "certificate", cert_path)
    key = load(crypto.load_privatekey, "key", key_path)

    if errors:
        return errors

    context = SSL.Context(SSL.TLSv1_METHOD)
    context.use_privatekey(key)
    context.use_certificate(cert)
    try:
        context.check_privatekey()
    except (crypto.Error, SSL.Error):
        errors.append("SSL certificate does not match the key")
    return errors

def open_ssl_file_to_rewrite(path):
    return os.fdopen(os.open(path, os.O_CREAT|os.O_WRONLY, 0o600), "wb")

def regenerate_cert_key(server_name, cert_path, key_path):
    key = generate_key()
    with open_ssl_file_to_rewrite(cert_path) as cert_file:
        cert_file.write(
            crypto.dump_certificate(
                crypto.FILETYPE_PEM,
                generate_cert(key, server_name)
            )
        )
    with open_ssl_file_to_rewrite(key_path) as key_file:
        key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

class CertKeyPair:
    def __init__(self, cert_location, key_location):
        self.__cert_location = cert_location
        self.__key_location = key_location

    @property
    def cert_location(self):
        return self.__cert_location

    @property
    def key_location(self):
        return self.__key_location

    def exists(self):
        return (
            os.path.isfile(self.cert_location)
            and
            os.path.isfile(self.key_location)
        )

    def check(self):
        return check_cert_key(self.cert_location, self.key_location)

    def regenerate(self, server_name):
        regenerate_cert_key(server_name, self.cert_location, self.key_location)

class SSLCertKeyException(Exception):
    pass

class PcsdSSL:
    def __init__(
        self, server_name, cert_location, key_location, ssl_options, ssl_ciphers
    ):
        self.__server_name = server_name
        self.__ssl_options = ssl_options
        self.__ssl_ciphers = ssl_ciphers
        self.__ck_pair = CertKeyPair(cert_location, key_location)

    def create_context(self) -> ssl.SSLContext:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.set_ciphers(self.__ssl_ciphers)
        ssl_context.options = self.__ssl_options
        ssl_context.load_cert_chain(
            self.__ck_pair.cert_location,
            self.__ck_pair.key_location
        )
        return ssl_context

    def guarantee_valid_certs(self):
        if not self.__ck_pair.exists():
            self.__ck_pair.regenerate(self.__server_name)
            return

        error_list = self.__ck_pair.check()
        if error_list:
            raise SSLCertKeyException(*error_list)

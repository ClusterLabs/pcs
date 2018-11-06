import time
from OpenSSL import crypto

def cert_date_format(timestamp):
    return str.encode(time.strftime("%Y%m%d%H%M%SZ", time.gmtime(timestamp)))

def generate_key(length=3072):
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, length)
    return key

def generate_cert(key, server_name):
    now = time.time()
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

def dump_cert(certificate):
    return crypto.dump_certificate(crypto.FILETYPE_PEM, certificate)

def dump_key(key):
    return crypto.dump_privatekey(crypto.FILETYPE_PEM, key)

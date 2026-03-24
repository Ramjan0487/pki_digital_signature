from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import datetime,os
def generate_user_certificate(username):
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,username)])
 cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject) .public_key(key.public_key()).serial_number(x509.random_serial_number()) .not_valid_before(datetime.datetime.utcnow()) .not_valid_after(datetime.datetime.utcnow()+datetime.timedelta(days=365)) .sign(key,hashes.SHA256())
 os.makedirs("pki",exist_ok=True)
 cert_path=f"pki/{username}.crt"
 key_path=f"pki/{username}.key"
 open(cert_path,"wb").write(cert.public_bytes(serialization.Encoding.PEM))
 open(key_path,"wb").write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
 return cert_path

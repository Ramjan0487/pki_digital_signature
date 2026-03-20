#!/usr/bin/env bash
# scripts/gen_certs.sh
# Generates a full PKI chain: CA → server cert → client cert
# Usage: bash scripts/gen_certs.sh [output_dir]
# Requires: openssl

set -euo pipefail

OUT="${1:-certs}"
CA_DIR="$OUT/ca"
SRV_DIR="$OUT/server"
CLI_DIR="$OUT/client"

mkdir -p "$CA_DIR" "$SRV_DIR" "$CLI_DIR"

SUBJ_CA="/C=RW/ST=Kigali/L=Kigali/O=GovCA/OU=PKI/CN=GovCA-Root-CA"
SUBJ_SRV="/C=RW/ST=Kigali/L=Kigali/O=GovCA/OU=Server/CN=govca.rw"
SUBJ_CLI="/C=RW/ST=Kigali/L=Kigali/O=GovCA/OU=Client/CN=govca-client"

echo "==> 1. Generating Root CA key and self-signed certificate..."
openssl genrsa -out "$CA_DIR/ca.key" 4096
openssl req -new -x509 -days 3650 -key "$CA_DIR/ca.key" \
  -subj "$SUBJ_CA" -out "$CA_DIR/ca.crt"

echo "==> 2. Generating server key and CSR..."
openssl genrsa -out "$SRV_DIR/server.key" 2048
openssl req -new -key "$SRV_DIR/server.key" \
  -subj "$SUBJ_SRV" -out "$SRV_DIR/server.csr"

# SAN extension for localhost + govca.rw
cat > "$SRV_DIR/san.ext" <<EOF
[req_ext]
subjectAltName = @alt_names
[alt_names]
DNS.1 = govca.rw
DNS.2 = www.govca.rw
DNS.3 = localhost
IP.1  = 127.0.0.1
EOF

echo "==> 3. Signing server certificate with CA..."
openssl x509 -req -days 365 -in "$SRV_DIR/server.csr" \
  -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
  -extfile "$SRV_DIR/san.ext" -extensions req_ext \
  -out "$SRV_DIR/server.crt"

echo "==> 4. Generating client key and CSR..."
openssl genrsa -out "$CLI_DIR/client.key" 2048
openssl req -new -key "$CLI_DIR/client.key" \
  -subj "$SUBJ_CLI" -out "$CLI_DIR/client.csr"

echo "==> 5. Signing client certificate with CA..."
openssl x509 -req -days 365 -in "$CLI_DIR/client.csr" \
  -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
  -out "$CLI_DIR/client.crt"

echo "==> 6. Creating client PKCS#12 bundle (for browser import)..."
openssl pkcs12 -export \
  -in "$CLI_DIR/client.crt" \
  -inkey "$CLI_DIR/client.key" \
  -certfile "$CA_DIR/ca.crt" \
  -out "$CLI_DIR/client.p12" \
  -passout pass:govca2024

echo ""
echo "✅ Certificates generated in: $OUT/"
echo ""
echo "Files:"
echo "  CA:     $CA_DIR/ca.crt           (trust anchor)"
echo "  Server: $SRV_DIR/server.crt      (TLS server cert)"
echo "          $SRV_DIR/server.key      (server private key)"
echo "  Client: $CLI_DIR/client.crt      (mTLS client cert)"
echo "          $CLI_DIR/client.key      (client private key)"
echo "          $CLI_DIR/client.p12      (import into browser, password: govca2024)"
echo ""
echo "To verify the chain:"
echo "  openssl verify -CAfile $CA_DIR/ca.crt $SRV_DIR/server.crt"
echo "  openssl verify -CAfile $CA_DIR/ca.crt $CLI_DIR/client.crt"

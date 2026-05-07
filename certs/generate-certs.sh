#!/bin/bash
# =============================================================================
# generate-certs.sh — TLS Certificate Generator for Secure Microservices Network
# =============================================================================
# Generates a self-signed CA and individual signed certificates for each service.
# This script is idempotent — safe to run multiple times (overwrites existing files).
#
# Usage: bash certs/generate-certs.sh    (run from repo root)
#   OR:  cd certs && bash generate-certs.sh
# =============================================================================

set -e

# Determine script directory so it works from any cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo " Generating TLS Certificates"
echo " Output directory: $SCRIPT_DIR"
echo "============================================"

# --- 1. Certificate Authority (CA) ---
echo ""
echo "[1/7] Creating Certificate Authority (CA)..."

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout ca.key \
  -out ca.crt \
  -days 365 \
  -subj "/CN=NPS-Project-CA" \
  2>/dev/null

echo "  ✓ CA created: ca.crt, ca.key (CN=NPS-Project-CA)"

# --- 2. Service certificates ---
SERVICES=("apisix" "users" "products" "orders" "auth" "prometheus")

STEP=2
for SERVICE in "${SERVICES[@]}"; do
  echo ""
  echo "[$STEP/7] Creating certificate for service: $SERVICE ..."

  # Generate private key and CSR
  openssl req -newkey rsa:2048 -nodes \
    -keyout "${SERVICE}.key" \
    -out "${SERVICE}.csr" \
    -subj "/CN=${SERVICE}" \
    2>/dev/null

  # Sign the CSR with our CA
  # Add SAN (Subject Alternative Name) for proper TLS hostname matching
  openssl x509 -req \
    -in "${SERVICE}.csr" \
    -CA ca.crt \
    -CAkey ca.key \
    -CAcreateserial \
    -out "${SERVICE}.crt" \
    -days 365 \
    -extfile <(printf "subjectAltName=DNS:${SERVICE},DNS:localhost,IP:127.0.0.1") \
    2>/dev/null

  # Clean up CSR (not needed after signing)
  rm -f "${SERVICE}.csr"

  echo "  ✓ ${SERVICE}.crt, ${SERVICE}.key (CN=${SERVICE})"

  STEP=$((STEP + 1))
done

echo ""
echo "============================================"
echo " All certificates generated successfully!"
echo "============================================"
echo ""
echo "Files created:"
ls -la *.crt *.key 2>/dev/null
echo ""
echo "IMPORTANT: Run this script BEFORE 'docker compose up'."
echo "           Cert files are bind-mounted into containers."
echo "============================================"

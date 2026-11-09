#!/usr/bin/env bash
# datadump.sh - export the OLTP database with mysqldump.        Task H5 (Eng. Hussein).
# Output: 01_oltp/backups/ecommerce_oltp_YYYY-MM-DD.sql.gz   (compressed, dated)
# Run from the repository root:  bash 01_oltp/scripts/datadump.sh
set -euo pipefail

STAMP=$(date +%F)
OUT="01_oltp/backups/ecommerce_oltp_${STAMP}.sql.gz"
mkdir -p 01_oltp/backups

# 1) read MYSQL_ROOT_PASSWORD from .env, fall back to the compose default
if [ -f .env ]; then
    MYSQL_ROOT_PASSWORD=$(grep -E '^MYSQL_ROOT_PASSWORD=' .env | head -n1 | cut -d= -f2- | tr -d '\r"')
fi
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-rootpassword}

# 2) dump inside the container (mysqldump is present in mysql:8.0) and gzip on the host
docker exec ecommerce-mysql \
    mysqldump -uroot -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction --routines --triggers --databases ecommerce_oltp \
    | gzip > "${OUT}"

# 3) verify the file is non-empty and readable
if [ ! -s "${OUT}" ]; then
    echo "ERROR: dump is empty: ${OUT}" >&2
    exit 1
fi
SIZE=$(stat -c%s "${OUT}" 2>/dev/null || stat -f%z "${OUT}")
echo "dump written: ${OUT} (${SIZE} bytes)"
echo "--- first 5 lines ---"
zcat "${OUT}" | head -n 5
echo "--- table count ---"
zcat "${OUT}" | grep -c '^CREATE TABLE' || true
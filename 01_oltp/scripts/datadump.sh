#!/usr/bin/env bash
# datadump.sh - export the OLTP database with mysqldump.        SKELETON - task H5 (Eng. Hussein), due 3-Nov.
# Output: 01_oltp/backups/ecommerce_oltp_YYYY-MM-DD.sql.gz   (compressed, dated)
# Run from the repository root:  bash 01_oltp/scripts/datadump.sh
set -euo pipefail

STAMP=$(date +%F)
OUT="01_oltp/backups/ecommerce_oltp_${STAMP}.sql.gz"

# TODO H5: read MYSQL_ROOT_PASSWORD from .env, then run mysqldump inside the container, for example:
#   docker exec ecommerce-mysql mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines ecommerce_oltp | gzip > "$OUT"
#   echo "dump written: $OUT"; zcat "$OUT" | head -n 5
echo "TODO H5: finish datadump.sh" >&2
exit 1

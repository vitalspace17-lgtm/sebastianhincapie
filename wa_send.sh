#!/usr/bin/env bash
set -euo pipefail

CSV="/home/taylerk/Documentos/smtpppp/actividad_final.csv"
REPORT_DIR="/home/taylerk/Documentos/smtpppp/reports"
REPORT="$REPORT_DIR/wa_$(date +%F).csv"
API="http://127.0.0.1:8000/send"
SUBJECT="Washington Annual Report | 2025 Filing Reminder"
DELAY="1.0"

# Opcional WordPress magic-link: deja vacíos si no usas
WP_MAGIC_URL=""
WP_API_KEY=""
PREFER="business_id"   # o "email"

mkdir -p "$REPORT_DIR"

# Ejecuta el envío (usa el Python del venv del proyecto)
exec /home/taylerk/Documentos/smtpppp/.venv/bin/python3 \
  /home/taylerk/Documentos/smtpppp/send.py \
  --csv "$CSV" \
  --report "$REPORT" \
  --subject "$SUBJECT" \
  --api "$API" \
  --delay "$DELAY" \
  --wp-magic-url "$WP_MAGIC_URL" \
  --wp-api-key "$WP_API_KEY" \
  --prefer "$PREFER"

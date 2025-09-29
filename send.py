#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send.py — Envío de campaña (Washington)

Soporta:
  * CSV legado con columna 'gmail'
  * CSV clientes con: BusinessID, UBI Number, Business Name,
    Responsible Person, Email, Address, NextARDueDate

- Pide magic-link a WordPress (prefill real) y lo usa en el botón.
- Escribe reporte en VIVO (append por cada envío) con timestamp.
"""

import csv
import time
import requests
import sys
import argparse
import re
import urllib.parse
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Iterable

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UPPER_TOKENS = {"llc","inc","corp","ltd","pllc","pc","co","sa","sas","srl","gmbh","foundation"}

# --------------------------- Utilidades --------------------------------------

def infer_name_from_email(addr: str) -> str:
    local = addr.split("@", 1)[0]
    # FIX: regex segura para -, +, _ y .
    local = re.sub(r"[._+\-]+", " ", local)
    local = re.sub(r"\s+", " ", local).strip()
    if not local:
        return "Customer"
    norm = []
    for t in local.split(" "):
        b = t.strip().lower()
        if not b:
            continue
        if b in UPPER_TOKENS:
            norm.append(b.upper())
        elif b.isdigit():
            norm.append(t)
        else:
            norm.append(b.capitalize())
    return " ".join(norm)


def norm_business_id(v: str) -> str:
    v = (v or "").strip()
    # FIX: sin dobles escapes
    m = re.match(r"^(\d+)\.0$", v)
    return m.group(1) if m else v


def safe_get(row: Dict[str, str], key: str) -> str:
    if key in row:
        return row.get(key) or ""
    key_l = key.strip().lower()
    for k in row.keys():
        if k.strip().lower() == key_l:
            return row.get(k) or ""
    return ""

# --------------------------- Lectura CSV -------------------------------------

def iter_emails_legacy(csv_path: Path) -> Iterable[Dict[str, str]]:
    """CSV con columna 'gmail' (una o varias separadas por coma)."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        keys = {k.lower().strip(): k for k in (reader.fieldnames or [])}
        if "gmail" not in keys:
            sys.exit("ERROR: Column 'gmail' not found in the CSV (legacy mode).")
        col = keys["gmail"]
        for row in reader:
            raw = (row.get(col) or "").strip()
            if not raw:
                continue
            for email in [a.strip() for a in raw.split(",") if a.strip()]:
                yield {"email": email, "row": row}


def iter_clients(csv_path: Path) -> Iterable[Dict[str, str]]:
    """CSV clientes. Requiere BusinessID y Email (mínimo)."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        required = ["BusinessID", "Email"]
        have = [c.strip().lower() for c in (r.fieldnames or [])]
        missing = [x for x in required if x.lower() not in have]
        if missing:
            sys.exit(f"ERROR: faltan columnas requeridas: {missing}")
        for row in r:
            yield {
                "business_id": norm_business_id(safe_get(row, "BusinessID")),
                "ubi_number": safe_get(row, "UBI Number"),
                "business_name": safe_get(row, "Business Name"),
                "responsible_person": safe_get(row, "Responsible Person"),
                "email": (safe_get(row, "Email") or "").strip(),
                "address": safe_get(row, "Address"),
                "next_due": safe_get(row, "NextARDueDate"),
                "row": row,
            }

# --------------------------- Magic-link WP -----------------------------------

def get_magic_link(api_url: str, api_key: str, prefer: str, client_row: Dict[str, str]) -> Tuple[str, str]:
    """
    Devuelve (url, error). prefer in {"business_id","email"}.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-comown-key"] = api_key

    payload: Dict[str, str] = {}
    if prefer == "business_id":
        bid = (client_row.get("business_id") or "").strip()
        if not bid:
            return "", "no_business_id"
        payload["business_id"] = bid
    else:
        em = (client_row.get("email") or "").strip()
        if not em:
            return "", "no_email_for_magic"
        payload["email"] = em

    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=20)
        if r.status_code != 200:
            return "", f"magic_http_{r.status_code}"
        j = r.json()
        url = j.get("url")
        if not url:
            return "", "magic_no_url"
        return url, ""
    except Exception as e:
        return "", f"magic_exc:{str(e)[:160]}"

# --------------------------- Templates WA ------------------------------------

def build_html(name: str, link: str, business_name: str = "", address: str = "", due: str = "") -> str:
    """
    Copy específico para Washington.
    """
    extra = ""
    if business_name or address or due:
        extra = f"""
        <p><strong>Business:</strong> {business_name or ''}<br>
           <strong>Address:</strong> {address or ''}<br>
           <strong>Next Annual Report Due:</strong> {due or ''}</p>"""

    return f"""<!doctype html>
<html lang="en"><head>
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
</head><body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7fb;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.06);padding:28px;">
<tr><td style="color:#333;line-height:1.6;">
  <h2 style="margin:0 0 12px;color:#111;">Dear {name},</h2>
  <p>This is a reminder to file your <strong>2025 Washington annual report</strong>. Filing is required to keep your business in good standing with the State of Washington. Filing by the due date helps avoid state late fees.</p>
  {extra}
  <p>Our service streamlines the process and keeps your business compliant. We are not affiliated with the Washington Secretary of State or any government agency.</p>
  <div style="text-align:center;margin:28px 0 22px;">
    <a href="{link}" target="_blank" style="display:inline-block;padding:14px 22px;background:#1a73e8;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold;">
      File Your Washington Annual Report
    </a>
  </div>
  <hr style="border:none;border-top:1px solid #eee;margin:18px 0">
  <p style="font-size:12px;color:#666;">National Filing Corporation is not affiliated with, approved, or endorsed by any government agency. This email is confidential and intended only for the recipient.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""

def build_text(name: str, link: str) -> str:
    return f"""Dear {name},

This is a reminder to file your 2025 Washington annual report. Filing is required to keep your business in good standing with the State of Washington. Filing by the due date helps avoid state late fees.

File here:
{link}

National Filing Corporation is not affiliated with, approved, or endorsed by any government agency."""

# --------------------------- Transporte FastAPI -------------------------------

def send_via_fastapi(api_send_url: str, email_to: str, subject: str, html: str, text: str, bearer: str = "") -> Tuple[bool, str]:
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    try:
        r = requests.post(
            api_send_url,
            json={
                "to": [email_to],
                "subject": subject,
                "body_text": text,
                "body_html": html,
                "headers": {"List-Unsubscribe": "<mailto:unsubscribe@e-filemycorporation.com>"}
            },
            headers=headers,
            timeout=45
        )
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:500]}"
        return True, ""
    except Exception as e:
        return False, str(e)

# --------------------------- Reporte en vivo ---------------------------------

def open_report_writer(path: str):
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    fh = open(path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=["ts", "row", "email", "status", "error"])
    if not exists:
        writer.writeheader()
        fh.flush()
        os.fsync(fh.fileno())
    return fh, writer

def write_report_row(fh, writer, row_idx: int, email: str, status: str, error: str = ""):
    ts = datetime.now(timezone.utc).isoformat()
    writer.writerow({"ts": ts, "row": row_idx, "email": email, "status": status, "error": error})
    fh.flush()
    os.fsync(fh.fileno())

# --------------------------- Main --------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Send Washington Annual Report Reminder emails")
    ap.add_argument("--csv", required=True, help="Ruta al CSV (legacy: 'gmail'; clientes: BusinessID+Email)")
    ap.add_argument("--api", default="http://127.0.0.1:8000/send", help="FastAPI /send endpoint")
    ap.add_argument("--api-bearer", default="", help="Bearer para /send si aplica")
    ap.add_argument("--delay", type=float, default=1.0, help="Pausa entre envíos (seg)")
    ap.add_argument("--subject", default="Washington Annual Report | 2025 Filing Reminder", help="Asunto")
    ap.add_argument("--link", default="https://renewals.nationalfilingcorporation.com/renewal-form/", help="CTA base (fallback si no hay magic-link)")
    ap.add_argument("--report", required=True, help="CSV de resultados (append en vivo)")
    ap.add_argument("--name-fallback", default="", help="Nombre fijo si no se puede inferir")
    ap.add_argument("--wp-magic-url", default="", help="https://.../wp-json/comown/v1/magic-link")
    ap.add_argument("--wp-api-key", default="", help="x-comown-key")
    ap.add_argument("--prefer", choices=["business_id", "email"], default="business_id", help="Identificador para magic-link")
    args = ap.parse_args()

    src = Path(args.csv).expanduser()
    if not src.exists():
        sys.exit(f"CSV no encontrado: {src}")

    with src.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        headers = [h.strip().lower() for h in (r.fieldnames or [])]
    is_legacy = ("gmail" in headers)
    is_clients = ("businessid" in headers or "business id" in headers) and ("email" in headers)
    if not is_legacy and not is_clients:
        sys.exit("CSV no reconocido: usa 'gmail' (legacy) o 'BusinessID' + 'Email' (clientes).")

    report_fh, report_writer = open_report_writer(args.report)

    ok, fail = 0, 0
    seen = set()
    iterator = iter_emails_legacy(src) if is_legacy else iter_clients(src)

    try:
        for idx, item in enumerate(iterator, 1):
            if is_legacy:
                email_to = (item["email"] or "").strip()
            else:
                email_to = (item.get("email") or "").strip()

            if not EMAIL_RE.match(email_to):
                write_report_row(report_fh, report_writer, idx, email_to, "skipped", "invalid_email")
                continue

            low = email_to.lower()
            if low in seen:
                continue
            seen.add(low)

            if not is_legacy and args.wp_magic_url:
                link, merr = get_magic_link(args.wp_magic_url, args.wp_api_key, args.prefer, item)
                if not link:
                    fail += 1
                    write_report_row(report_fh, report_writer, idx, email_to, "failed", merr or "no_link")
                    continue
            else:
                sep = "&" if "?" in args.link else "?"
                link = f"{args.link}{sep}email={urllib.parse.quote(email_to)}"

            if is_legacy:
                name = args.name_fallback or infer_name_from_email(email_to)
                html = build_html(name, link)
            else:
                name = (item.get("responsible_person") or item.get("business_name") or args.name_fallback or "").strip() \
                       or infer_name_from_email(email_to)
                html = build_html(
                    name=name,
                    link=link,
                    business_name=item.get("business_name", ""),
                    address=item.get("address", ""),
                    due=item.get("next_due", ""),
                )

            text = build_text(name, link)

            ok_send, err = send_via_fastapi(args.api, email_to, args.subject, html, text, bearer=args.api_bearer)
            if ok_send:
                ok += 1
                write_report_row(report_fh, report_writer, idx, email_to, "sent", "")
            else:
                fail += 1
                write_report_row(report_fh, report_writer, idx, email_to, "failed", err)

            time.sleep(args.delay)

    finally:
        try:
            report_fh.close()
        except Exception:
            pass

    print(f"Done. OK={ok} FAIL={fail}")
    print(f"Report appended to: {Path(args.report).resolve()}")

if __name__ == "__main__":
    main()

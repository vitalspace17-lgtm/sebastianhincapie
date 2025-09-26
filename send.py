#!/usr/bin/env python3
import csv, time, requests, sys, argparse, re, urllib.parse
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

UPPER_TOKENS = {"llc","inc","corp","ltd","pllc","pc","co","sa","sas","srl","gmbh","foundation"}

def infer_name_from_email(addr: str) -> str:
    local = addr.split("@", 1)[0]
    local = re.sub(r"[._\-+]+", " ", local)
    local = re.sub(r"\s+", " ", local).strip()
    if not local:
        return "Customer"
    norm = []
    for t in local.split(" "):
        b = t.strip().lower()
        if not b: continue
        if b in UPPER_TOKENS: norm.append(b.upper())
        elif b.isdigit(): norm.append(t)
        else: norm.append(b.capitalize())
    return " ".join(norm)

def read_gmails(csv_path: Path):
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        keys = {k.lower().strip(): k for k in (reader.fieldnames or [])}
        if "gmail" not in keys:
            sys.exit("ERROR: Column 'gmail' not found in the CSV.")
        col = keys["gmail"]
        for row in reader:
            raw = (row.get(col) or "").strip()
            if not raw: continue
            for email in [a.strip() for a in raw.split(",") if a.strip()]:
                yield email

def build_html(name: str, link: str) -> str:
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta name="color-scheme" content="light dark">
    <meta name="supported-color-schemes" content="light dark">
  </head>
  <body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7fb;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.06);padding:28px;">
            <tr>
              <td style="color:#333;line-height:1.6;">
                <h2 style="margin:0 0 12px 0;color:#111;">Dear {name},</h2>

                <p>
                  This is your annual reminder of the upcoming deadline for Florida corporate annual renewals for the year 2025.
                  This report is mandatory (even if no changes were made) and must be filed between January 1st and May 1st.
                  Please act promptly to avoid $500+ in late fees. Local state filing fees will be added at checkout.
                </p>

                <p>
                  At <strong>National Filing Corporation</strong>, we have developed our annual report filing service to streamline the process
                  and help keep your business compliant with state regulations. Our service is fast, secure, and user-friendly.
                  We are not endorsed, affiliated, or approved by any government entity. If you have already filed your 2025 annual report,
                  you may disregard this message.
                </p>

                <div style="text-align:center;margin:28px 0 22px 0;">
                  <a href="{link}" target="_blank"
                     style="display:inline-block;padding:14px 22px;background:#1a73e8;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:bold;">
                    File Your 2025 Annual Report
                  </a>
                </div>

                <hr style="border:none;border-top:1px solid #eee;margin:18px 0">

                <p style="font-size:12px;color:#666;">
                  National Filing Corporation does not provide financial or legal advice and is not affiliated with, approved, or endorsed by any government agency.
                  This email is confidential and intended only for the recipient.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

def build_text(name: str, link: str) -> str:
    return (
f"""Dear {name},

This is your annual reminder of the upcoming deadline for Florida corporate annual renewals for the year 2025. This report is mandatory (even if no changes were made) and must be filed between January 1st and May 1st. Act promptly to avoid $500+ in late fees. Local state filing fees will be added at checkout.

At National Filing Corporation, we offer a fast, secure, and user-friendly annual report filing service to help you remain compliant with state regulations. We are not endorsed, affiliated, or approved by any government entity. If you already filed your 2025 annual report, please disregard this message.

File here:
{link}

Note: National Filing Corporation does not provide financial or legal advice and is not affiliated with, approved, or endorsed by any government agency. This email is confidential and intended for the recipient only.
""")

def main():
    p = argparse.ArgumentParser(description="Send Annual Report Reminder emails")
    p.add_argument("--csv", required=True, help="Path to CSV (must include 'gmail' column)")
    p.add_argument("--api", default="http://127.0.0.1:8000/send", help="FastAPI /send endpoint")
    p.add_argument("--delay", type=float, default=1.0, help="Delay between sends (seconds)")
    p.add_argument("--subject", default="Annual Report Reminder | Florida 2025", help="Email subject")
    p.add_argument("--link", default="https://renewals.nationalfilingcorporation.com/renewal-form/", help="CTA URL")
    p.add_argument("--report", default="send_results.csv", help="Output CSV report path")
    p.add_argument("--name-fallback", dest="name_fallback", default="", help="Fixed recipient name for all emails")
    args = p.parse_args()

    src = Path(args.csv).expanduser()
    dest = Path(args.report).expanduser()

    ok, fail = 0, 0
    seen = set()
    results = []

    for email in read_gmails(src):
        if email.lower() in seen:
            continue
        seen.add(email.lower())

        status, error = "sent", ""
        if not EMAIL_RE.match(email):
            status, error = "skipped", "invalid_email"
        else:
            name = args.name_fallback if args.name_fallback else infer_name_from_email(email)
            sep = "&" if "?" in args.link else "?"
            link = f"{args.link}{sep}email={urllib.parse.quote(email)}"
            body_html = build_html(name, link)
            body_text = build_text(name, link)

            try:
                r = requests.post(
                    args.api,
                    json={
                        "to": [email],
                        "subject": args.subject,
                        "body_text": body_text,
                        "body_html": body_html,
                        "headers": {"List-Unsubscribe": "<mailto:unsubscribe@e-filemycorporation.com>"}
                    },
                    timeout=45
                )
                if r.status_code != 200:
                    status, error = "failed", f"HTTP {r.status_code}: {r.text[:500]}"
            except Exception as e:
                status, error = "failed", str(e)

        if status == "sent": ok += 1
        elif status == "failed": fail += 1

        results.append({"email": email, "status": status, "error": error})
        time.sleep(args.delay)

    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email","status","error"])
        w.writeheader()
        w.writerows(results)

    print(f"Done. OK={ok} FAIL={fail} Total={len(results)}")
    print(f"Report saved to: {dest.resolve()}")

if __name__ == "__main__":
    main()

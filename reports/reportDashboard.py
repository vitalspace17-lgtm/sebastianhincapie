# Dashboard generator for wa_2025-09-28.csv
# - Loads the original and the clean file (if present)
# - Computes key metrics
# - Builds charts with matplotlib (no seaborn, no styles, one chart per figure)
# - Exports a lightweight HTML report with embedded PNGs
# - Saves summary CSVs
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import base64

base_path = Path("/home/taylerk/Documentos/smtpppp/reports/wa_2025-09-28.csv")
raw_path = base_path / "wa_2025-09-28.csv"
clean_path = base_path / "wa_2025-09-28_clean.csv"
dict_path = base_path / "wa_2025-09-28_data_dictionary.csv"

# Load
df_raw = pd.read_csv(raw_path)
df = pd.read_csv(clean_path) if clean_path.exists() else df_raw.copy()

# Ensure columns exist
for col in ["ts", "row", "email", "status", "error"]:
    if col not in df_raw.columns:
        df_raw[col] = None
    if col not in df.columns:
        df[col] = None

# Parse timestamps if possible
def parse_ts(s):
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT

df_raw["ts_dt"] = parse_ts(df_raw["ts"])
df["ts_dt"] = parse_ts(df["ts"])

# Basic metrics
total_rows = len(df_raw)
valid_email_rows = df_raw["email"].astype(str).str.contains("@", na=False).sum()
unique_emails_raw = df_raw["email"].astype(str).str.strip().str.lower()
unique_emails_raw = unique_emails_raw[unique_emails_raw.str.contains("@", na=False)].nunique()

unique_emails_clean = df["email"].astype(str).str.strip().str.lower()
unique_emails_clean = unique_emails_clean[unique_emails_clean.str.contains("@", na=False)].nunique()

null_email = df_raw["email"].isna().sum()
status_counts = df_raw["status"].fillna("EMPTY").value_counts()
top_errors = df_raw["error"].dropna().astype(str).value_counts().head(10)

# Time series (by day)
if df_raw["ts_dt"].notna().any():
    ts_daily = df_raw.dropna(subset=["ts_dt"]).assign(day=lambda x: x["ts_dt"].dt.date).groupby("day").size()
else:
    ts_daily = pd.Series(dtype=int)

# Output dirs / filenames
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = base_path / f"wa_dashboard_{ts}"
out_dir.mkdir(parents=True, exist_ok=True)

# Save summary CSVs
status_counts.to_csv(out_dir / "status_counts.csv", header=["count"])
top_errors.to_csv(out_dir / "top_errors.csv", header=["count"])
if len(ts_daily) > 0:
    ts_daily.to_csv(out_dir / "daily_counts.csv", header=["count"])

# Figures
fig_paths = []

# 1) Status distribution
plt.figure()
status_counts.plot(kind="bar")
plt.title("Distribución de 'status' (raw)")
plt.xlabel("status")
plt.ylabel("conteo")
p1 = out_dir / "status_distribution.png"
plt.tight_layout()
plt.savefig(p1)
plt.close()
fig_paths.append(p1)

# 2) Top error messages
if len(top_errors) > 0:
    plt.figure()
    top_errors.plot(kind="barh")
    plt.title("Top 10 mensajes de error (raw)")
    plt.xlabel("conteo")
    plt.ylabel("error")
    p2 = out_dir / "top_errors.png"
    plt.tight_layout()
    plt.savefig(p2)
    plt.close()
    fig_paths.append(p2)

# 3) Daily volume (if timestamps available)
if len(ts_daily) > 0:
    plt.figure()
    ts_daily.sort_index().plot(kind="line", marker="o")
    plt.title("Volumen diario (raw)")
    plt.xlabel("día")
    plt.ylabel("registros")
    p3 = out_dir / "daily_volume.png"
    plt.tight_layout()
    plt.savefig(p3)
    plt.close()
    fig_paths.append(p3)

# Build HTML report
def img_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

fig_imgs = "".join(
    f'<h3>{path.name.replace("_"," ").replace(".png","").title()}</h3>\n'
    f'<img src="data:image/png;base64,{img_to_base64(path)}" style="max-width:100%;height:auto;"/>\n'
    for path in fig_paths
)

metrics_table = pd.DataFrame([
    {"Métrica": "Filas (raw)", "Valor": total_rows},
    {"Métrica": "Filas con email válido (raw)", "Valor": int(valid_email_rows)},
    {"Métrica": "Emails únicos (raw)", "Valor": int(unique_emails_raw)},
    {"Métrica": "Emails únicos (clean)", "Valor": int(unique_emails_clean)},
    {"Métrica": "Emails vacíos (raw)", "Valor": int(null_email)},
])

metrics_csv_path = out_dir / "metrics_summary.csv"
metrics_table.to_csv(metrics_csv_path, index=False)

# Convert small tables to HTML snippets
status_html = status_counts.reset_index().rename(columns={"index":"status","status":"count"}).to_html(index=False)
errors_html = top_errors.reset_index().rename(columns={"index":"error","error":"count"}).to_html(index=False) if len(top_errors) > 0 else "<p>Sin errores.</p>"
daily_html = ts_daily.reset_index().rename(columns={"index":"day",0:"count"}).to_html(index=False) if len(ts_daily) > 0 else "<p>No hay timestamps válidos para serie diaria.</p>"
metrics_html = metrics_table.to_html(index=False)

html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard WA 2025-09-28</title>
<style>
 body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; }}
 h1,h2,h3 {{ margin: 0 0 12px; }}
 section {{ margin-bottom: 28px; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 14px; }}
 th {{ text-align: left; }}
 .grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
 .foot {{ color:#666; font-size:12px; margin-top:24px; }}
</style>
</head>
<body>
  <h1>Dashboard: WA 2025-09-28</h1>
  <p>Generado: {datetime.now().isoformat(timespec='seconds')}</p>

  <section>
    <h2>Resumen</h2>
    {metrics_html}
  </section>

  <section>
    <h2>Tablas</h2>
    <h3>Distribución de status</h3>
    {status_html}
    <h3>Top errores</h3>
    {errors_html}
    <h3>Volumen diario</h3>
    {daily_html}
  </section>

  <section>
    <h2>Gráficas</h2>
    <div class="grid">
      {fig_imgs}
    </div>
  </section>

  <div class="foot">
    <p>Fuente de datos: {raw_path.name}{' + ' + clean_path.name if clean_path.exists() else ''}</p>
  </div>
</body>
</html>
"""

report_path = out_dir / "dashboard_report.html"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(html)

{
 "report_path": str(report_path),
 "metrics_csv": str(metrics_csv_path),
 "status_counts_csv": str(out_dir / "status_counts.csv"),
 "top_errors_csv": str(out_dir / "top_errors.csv") if len(top_errors)>0 else None,
 "daily_counts_csv": str(out_dir / "daily_counts.csv") if len(ts_daily)>0 else None,
 "figures": [str(p) for p in fig_paths]
}

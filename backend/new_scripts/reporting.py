from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _risk_level(score: float) -> str:
    if score < 15:
        return "Low"
    if score < 35:
        return "Medium"
    return "High"


def _display_risk_band(metric_payload: dict, score: float) -> str:
  band = str(metric_payload.get("risk_band", "")).strip().lower()
  if band == "critical":
    return "Critical"
  if band == "high":
    return "High"
  if band == "moderate":
    return "Moderate"
  if band == "low":
    return "Low"

  if score >= 80:
    return "Critical"
  if score >= 50:
    return "High"
  if score >= 20:
    return "Moderate"
  return "Low"


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_plain_pdf(lines: list[str], pdf_path: Path) -> str:
    content_lines = ["BT", "/F1 11 Tf", "50 780 Td"]
    for idx, line in enumerate(lines):
        if idx > 0:
            content_lines.append("0 -14 Td")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("utf-8")

    objects: list[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
    )
    stream_obj = (
        f"4 0 obj << /Length {len(content_stream)} >> stream\n".encode("utf-8")
        + content_stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(stream_obj)
    objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(obj)

    xref_offset = len(pdf_bytes)
    size = len(objects) + 1
    pdf_bytes.extend(f"xref\n0 {size}\n".encode("utf-8"))
    pdf_bytes.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf_bytes.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    pdf_bytes.extend(f"trailer << /Size {size} /Root 1 0 R >>\n".encode("utf-8"))
    pdf_bytes.extend(b"startxref\n")
    pdf_bytes.extend(f"{xref_offset}\n".encode("utf-8"))
    pdf_bytes.extend(b"%%EOF")

    pdf_path.write_bytes(pdf_bytes)
    return str(pdf_path)


def _summarize_report(site: dict, metrics: dict, aggregate: float, reference_validation: dict) -> list[str]:
    defo_val = reference_validation.get("deforestation_validation", {})
    water_val = reference_validation.get("water_validation", {})
    deforestation_score = float(metrics.get("deforestation", {}).get("risk_score", 0.0))
    water_score = float(metrics.get("water_change", {}).get("risk_score", 0.0))
    uhi_score = float(metrics.get("uhi", {}).get("risk_score", 0.0))
    deforestation_band = _display_risk_band(metrics.get("deforestation", {}), deforestation_score)
    water_band = _display_risk_band(metrics.get("water_change", {}), water_score)
    uhi_band = _display_risk_band(metrics.get("uhi", {}), uhi_score)
    lines = [
        "NovaRisk ESG Site Report",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
      "Risk band legend: Low 0-20, Moderate 20-50, High 50-80, Critical 80-100.",
        "",
        f"Site: lat {site.get('lat')} / lon {site.get('lon')}",
        f"Date range: {site.get('date_range')}",
        "",
        f"Aggregate risk: {aggregate:.2f} ({_risk_level(aggregate)})",
        "",
        f"Deforestation risk: {deforestation_score:.2f} ({deforestation_band})",
        f"Deforestation confidence: {float(metrics.get('deforestation', {}).get('confidence', 0.0)):.2f}",
        f"Water change risk: {water_score:.2f} ({water_band})",
        f"Water confidence: {float(metrics.get('water_change', {}).get('confidence', 0.0)):.2f}",
        f"UHI intensity risk: {uhi_score:.2f} ({uhi_band})",
        f"UHI confidence: {float(metrics.get('uhi', {}).get('confidence', 0.0)):.2f}",
        "",
        f"Deforestation validation IoU/F1: {float(defo_val.get('iou', 0.0)):.2f} / {float(defo_val.get('f1_score', 0.0)):.2f}",
        f"Water validation IoU/F1: {float(water_val.get('iou', 0.0)):.2f} / {float(water_val.get('f1_score', 0.0)):.2f}",
        "",
        "Caveats:",
        "- Land-use and water are proxy indicators in demo mode.",
        "- UHI is ERA5-Land air-temperature differential proxy, not direct LST.",
        "- Cloud/revisit gaps may lower monthly certainty.",
    ]
    return lines


def generate_site_report_pdf(report_payload: dict, output_dir: str = "data/reports") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    site = report_payload.get("site", {})
    metrics = report_payload.get("metrics", {})
    reference_validation = metrics.get("reference_validation", {})
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    deforestation_score = float(metrics.get("deforestation", {}).get("risk_score", 0.0))
    water_score = float(metrics.get("water_change", {}).get("risk_score", 0.0))
    uhi_score = float(metrics.get("uhi", {}).get("risk_score", 0.0))
    deforestation_band = _display_risk_band(metrics.get("deforestation", {}), deforestation_score)
    water_band = _display_risk_band(metrics.get("water_change", {}), water_score)
    uhi_band = _display_risk_band(metrics.get("uhi", {}), uhi_score)
    aggregate = (deforestation_score + water_score + uhi_score) / 3.0

    defo_val = reference_validation.get("deforestation_validation", {})
    water_val = reference_validation.get("water_validation", {})
    defo_iou = float(defo_val.get("iou", 0.0))
    water_iou = float(water_val.get("iou", 0.0))
    defo_f1 = float(defo_val.get("f1_score", 0.0))
    water_f1 = float(water_val.get("f1_score", 0.0))

    html = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
          h1 {{ margin-bottom: 4px; }}
          .muted {{ color: #6b7280; font-size: 12px; margin-bottom: 18px; }}
          .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; margin-bottom: 10px; }}
          .label {{ font-size: 12px; color: #6b7280; }}
          .value {{ font-size: 24px; font-weight: 700; }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
          th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
          th {{ background: #f9fafb; }}
        </style>
      </head>
      <body>
        <h1>NovaRisk ESG Site Report</h1>
        <div class="muted">Generated: {generated_at}</div>
        <div class="muted">Risk band legend: Low 0-20, Moderate 20-50, High 50-80, Critical 80-100.</div>

        <div class="card">
          <div><strong>Site Coordinates:</strong> {site.get('lat')}, {site.get('lon')}</div>
          <div><strong>Date Range:</strong> {site.get('date_range')}</div>
        </div>

        <div class="card">
          <div class="label">Aggregate Risk Score</div>
          <div class="value">{aggregate:.2f}</div>
          <div><strong>Risk Level:</strong> {_risk_level(aggregate)}</div>
        </div>

        <table>
          <tr><th>Metric</th><th>Risk Score</th><th>Risk Band</th><th>Key Signal</th></tr>
          <tr>
            <td>Deforestation / Land-use</td>
            <td>{deforestation_score:.2f}</td>
            <td>{deforestation_band}</td>
            <td>Vegetation Change: {metrics.get('deforestation', {}).get('vegetation_change_pct', 0.0):.2f}% (Confidence: {metrics.get('deforestation', {}).get('confidence', 0.0):.2f})</td>
          </tr>
          <tr>
            <td>Water Body Change</td>
            <td>{water_score:.2f}</td>
            <td>{water_band}</td>
            <td>Water Change: {metrics.get('water_change', {}).get('water_change_pct', 0.0):.2f}% (Confidence: {metrics.get('water_change', {}).get('confidence', 0.0):.2f})</td>
          </tr>
          <tr>
            <td>Urban Heat Island Intensity</td>
            <td>{uhi_score:.2f}</td>
            <td>{uhi_band}</td>
            <td>UHI Intensity: {metrics.get('uhi', {}).get('uhi_intensity_c', 0.0):.2f}°C (Confidence: {metrics.get('uhi', {}).get('confidence', 0.0):.2f})</td>
          </tr>
          <tr>
            <td>Reference Validation (Deforestation)</td>
            <td>{defo_f1:.2f}</td>
            <td>n/a</td>
            <td>IoU: {defo_iou:.2f}, F1: {defo_f1:.2f}</td>
          </tr>
          <tr>
            <td>Reference Validation (Water)</td>
            <td>{water_f1:.2f}</td>
            <td>n/a</td>
            <td>IoU: {water_iou:.2f}, F1: {water_f1:.2f}</td>
          </tr>
        </table>

        <h2 style="margin-top:20px;">ESRS Mapping Summary</h2>
        <table>
          <tr><th>Indicator</th><th>Standard</th><th>Risk Band</th><th>Traceability</th></tr>
          <tr>
            <td>Deforestation / Land-use</td>
            <td>ESRS E4</td>
            <td>{deforestation_band}</td>
            <td>NDVI change + WorldCover validation</td>
          </tr>
          <tr>
            <td>Water Body Change</td>
            <td>ESRS E3</td>
            <td>{water_band}</td>
            <td>MNDWI/SAR change + JRC-style validation</td>
          </tr>
          <tr>
            <td>Urban Heat Island Intensity</td>
            <td>ESRS E1</td>
            <td>{uhi_band}</td>
            <td>ERA5-Land percentile-based UHI intensity</td>
          </tr>
        </table>

        <h2 style="margin-top:20px;">Assumptions & Caveats</h2>
        <ul>
          <li>Water and UHI are proxy indicators in demo mode and should be interpreted with disclosed uncertainty.</li>
          <li>Cloud contamination and revisit gaps can affect certainty for optical monthly composites.</li>
          <li>Sector materiality weighting and score thresholds are configurable and must be disclosed in governance notes.</li>
        </ul>
      </body>
    </html>
    """

    filename = f"site_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = output_path / filename

    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(str(pdf_path))
        return str(pdf_path)
    except Exception:
        summary_lines = _summarize_report(site, metrics, aggregate, reference_validation)
        return _write_plain_pdf(summary_lines, pdf_path)

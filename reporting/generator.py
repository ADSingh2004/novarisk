import csv
from io import StringIO, BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_csv_report(latitude: float, longitude: float, metrics: dict) -> str:
    """Generates a CSV string containing the ESG report data."""
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["NovaRisk ESG - Compliance Report"])
    writer.writerow(["Generated At", datetime.utcnow().isoformat() + "Z"])
    writer.writerow(["Facility Latitude", latitude])
    writer.writerow(["Facility Longitude", longitude])
    writer.writerow([])
    
    writer.writerow(["Metric", "Score (0-100)", "Status"])
    
    def get_status(score, high, med):
        if score > high: return "High Risk"
        if score > med: return "Medium Risk"
        return "Good"
        
    writer.writerow(["Deforestation Risk", metrics.get("deforestation_risk", 0), get_status(metrics.get("deforestation_risk", 0), 50, 20)])
    writer.writerow(["Water Stress Proxy", metrics.get("water_stress_proxy", 0), get_status(metrics.get("water_stress_proxy", 0), 60, 30)])
    writer.writerow(["UHI Intensity", metrics.get("heat_island_index", 0), get_status(metrics.get("heat_island_index", 0), 5, 2)])
    
    return output.getvalue()


def generate_pdf_report(latitude: float, longitude: float, metrics: dict) -> bytes:
    """Generates a PDF byte stream containing the ESG report."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom Title Style
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#059669'), # Emerald 600
        spaceAfter=30
    )
    
    elements = []
    
    # Header
    elements.append(Paragraph("NovaRisk ESG", title_style))
    elements.append(Paragraph("Satellite Intelligence Compliance Report", styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    # Facility Details
    elements.append(Paragraph(f"<b>Facility Location:</b> {latitude:.4f}, {longitude:.4f}", styles['Normal']))
    elements.append(Paragraph(f"<b>Generated At:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", styles['Normal']))
    elements.append(Spacer(1, 30))
    
    # Metrics Table
    data = [
        ['ESG Indicator', 'Risk Score (0-100)', 'Risk Level']
    ]
    
    def get_status(score, high, med):
        if score > high: return 'HIGH RISK'
        if score > med: return 'MEDIUM RISK'
        return 'GOOD'
        
    data.append([
        'Deforestation Risk', 
        f"{metrics.get('deforestation_risk', 0):.2f}", 
        get_status(metrics.get('deforestation_risk', 0), 50, 20)
    ])
    
    data.append([
        'Water Stress Proxy', 
        f"{metrics.get('water_stress_proxy', 0):.2f}", 
        get_status(metrics.get('water_stress_proxy', 0), 60, 30)
    ])
    
    data.append([
        'Urban Heat Island (UHI)', 
        f"{metrics.get('heat_island_index', 0):.2f}", 
        get_status(metrics.get('heat_island_index', 0), 5, 2)
    ])
    
    t = Table(data, colWidths=[200, 150, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')), # Slate 100
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#334155')), # Slate 700
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#475569')), # Slate 600
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')), # Slate 200
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 40))
    
    # Methodology Note
    elements.append(Paragraph("<b>Methodology:</b>", styles['Heading3']))
    methodology_text = """
    This report is generated using satellite imagery from Microsoft Planetary Computer.
    Deforestation and Water Stress are calculated by comparing current vegetation (NDVI) and water (NDWI) indices against a historical baseline from Sentinel-2.
    Urban Heat Island (UHI) intensity is calculated by comparing Land Surface Temperature (LST) around the facility to a 10km regional buffer using Landsat Collection 2.
    """
    elements.append(Paragraph(methodology_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

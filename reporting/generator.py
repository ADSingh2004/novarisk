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


def generate_ai_land_features_pdf(latitude: float, longitude: float, land_cover_percentages: dict) -> bytes:
    """
    Generates a PDF report for AI-predicted land cover features and classification breakdown.
    
    Args:
        latitude, longitude: Facility coordinates
        land_cover_percentages: Dict with keys like forest_percentage, water_percentage, etc.
    
    Returns:
        PDF byte stream
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom Title Style
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0891b2'),  # Cyan 600
        spaceAfter=30
    )
    
    elements = []
    
    # Header
    elements.append(Paragraph("NovaRisk ESG - AI Land Cover Analysis", title_style))
    elements.append(Paragraph("Deep Learning Land Feature Classification Report", styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    # Facility Details
    elements.append(Paragraph(f"<b>Facility Location:</b> {latitude:.4f}, {longitude:.4f}", styles['Normal']))
    elements.append(Paragraph(f"<b>Analysis Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", styles['Normal']))
    elements.append(Spacer(1, 30))
    
    # Land Cover Classification Results
    elements.append(Paragraph("<b>Land Cover Classification Results</b>", styles['Heading3']))
    elements.append(Spacer(1, 10))
    
    # Define land cover classes with descriptions
    class_descriptions = {
        "forest_percentage": ("Forest", "Dense vegetation including trees, shrubs, and woodland areas. Indicators of ecosystem health and biodiversity."),
        "water_percentage": ("Surface Water", "Lakes, rivers, wetlands, and water bodies. Critical for water availability and hydrological assessment."),
        "urban_percentage": ("Urban/Built-up", "Developed areas including buildings, roads, and infrastructure. Indicators of industrial/residential density."),
        "agriculture_percentage": ("Agriculture", "Croplands and cultivated areas. Important for land-use and food production assessment."),
        "barren_percentage": ("Barren/Sparse", "Rocky areas, sand, barren land with minimal vegetation. Indicators of erosion risk or environmental stress."),
    }
    
    # Create detailed breakdown table
    data = [
        ['Land Cover Class', 'Coverage (%)', 'Description']
    ]
    
    for key, (class_name, description) in class_descriptions.items():
        percentage = land_cover_percentages.get(key, 0.0)
        data.append([
            class_name,
            f"{percentage:.2f}%",
            description
        ])
    
    t = Table(data, colWidths=[120, 100, 280])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#c7f0d8')),  # Emerald 200
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#065f46')),   # Emerald 900
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#374151')),  # Gray 700
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#d1fae5')),    # Emerald 100
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 30))
    
    # Methodology
    elements.append(Paragraph("<b>AI Classification Methodology</b>", styles['Heading3']))
    methodology_text = """
    <b>Model Architecture:</b> Lightweight U-Net with ResNet18 encoder (pre-trained on ImageNet)<br/>
    <b>Input Data:</b> Sentinel-2 RGB composite (B04=Red, B03=Green, B02=Blue) at 40m resolution<br/>
    <b>Output:</b> 5-class pixel-wise land cover prediction<br/>
    <b>Processing:</b> Median composite from 30-day satellite time series, cloud-masked<br/>
    <b>Performance:</b> CPU inference optimized for <10s latency<br/>
    <br/>
    <b>Classes Recognized:</b><br/>
    • <b>Forest:</b> NDVI > 0.4, dense vegetation<br/>
    • <b>Water:</b> NDWI > 0.2, spectral water signature<br/>
    • <b>Urban:</b> High reflectance, built-up infrastructure<br/>
    • <b>Agriculture:</b> Intermediate NDVI (0.2-0.4), cultivated patterns<br/>
    • <b>Barren:</b> Low NDVI, high thermal signature<br/>
    """
    elements.append(Paragraph(methodology_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Key Insights
    elements.append(Paragraph("<b>Key Insights</b>", styles['Heading3']))
    
    # Determine dominant land cover
    max_coverage = 0.0
    dominant_class = "N/A"
    for key, (class_name, _) in class_descriptions.items():
        coverage = land_cover_percentages.get(key, 0.0)
        if coverage > max_coverage:
            max_coverage = coverage
            dominant_class = class_name
    
    insights_text = f"""
    <b>Dominant Land Cover:</b> {dominant_class} ({max_coverage:.2f}%)<br/>
    <b>Vegetation Coverage:</b> {land_cover_percentages.get('forest_percentage', 0.0) + land_cover_percentages.get('agriculture_percentage', 0.0):.2f}%<br/>
    <b>Water Coverage:</b> {land_cover_percentages.get('water_percentage', 0.0):.2f}%<br/>
    <b>Urban/Built-up Coverage:</b> {land_cover_percentages.get('urban_percentage', 0.0):.2f}%<br/>
    <br/>
    <i>Note: This classification uses artificial intelligence trained on global satellite imagery. 
    For site-specific validation, ground-truth surveys are recommended.</i>
    """
    elements.append(Paragraph(insights_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

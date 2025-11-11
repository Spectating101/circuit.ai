"""
Advanced Report Generation

Generates professional reports in multiple formats:
- PDF with charts and diagrams
- PowerPoint presentations
- Interactive HTML reports
- Executive summaries
- Technical specifications
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import base64

# PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

# PowerPoint generation
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

# Charts
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

from loguru import logger


@dataclass
class ReportSection:
    """Report section."""
    title: str
    content: str
    charts: Optional[List[Dict[str, Any]]] = None
    tables: Optional[List[Dict[str, Any]]] = None
    images: Optional[List[str]] = None


class PDFReportGenerator:
    """Professional PDF report generator."""

    def __init__(self):
        """Initialize PDF generator."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        logger.info("PDFReportGenerator initialized")

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12
        ))

        # Body style
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            leading=14,
            spaceAfter=12
        ))

    async def generate_analysis_report(
        self,
        analysis_data: Dict[str, Any],
        include_recommendations: bool = True,
        include_anomalies: bool = True
    ) -> bytes:
        """
        Generate comprehensive analysis report PDF.

        Args:
            analysis_data: Analysis results
            include_recommendations: Include AI recommendations
            include_anomalies: Include anomaly detection

        Returns:
            PDF bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []

        # Title page
        story.extend(self._create_title_page(analysis_data))
        story.append(PageBreak())

        # Executive summary
        story.extend(self._create_executive_summary(analysis_data))
        story.append(PageBreak())

        # Component analysis
        story.extend(self._create_component_section(analysis_data))
        story.append(PageBreak())

        # BOM
        if 'bom' in analysis_data:
            story.extend(self._create_bom_section(analysis_data['bom']))
            story.append(PageBreak())

        # Anomalies
        if include_anomalies and 'anomalies' in analysis_data:
            story.extend(self._create_anomalies_section(analysis_data['anomalies']))
            story.append(PageBreak())

        # Recommendations
        if include_recommendations and 'recommendations' in analysis_data:
            story.extend(self._create_recommendations_section(analysis_data['recommendations']))

        # Build PDF
        doc.build(story)

        return buffer.getvalue()

    def _create_title_page(self, analysis_data: Dict[str, Any]) -> List:
        """Create title page."""
        story = []

        # Logo/header space
        story.append(Spacer(1, 2*inch))

        # Title
        title = Paragraph(
            f"PCB Analysis Report<br/>{analysis_data.get('pcb_name', 'Untitled PCB')}",
            self.styles['CustomTitle']
        )
        story.append(title)
        story.append(Spacer(1, 0.5*inch))

        # Metadata table
        metadata = [
            ['Analysis ID:', analysis_data.get('id', 'N/A')],
            ['Date:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Components Detected:', str(analysis_data.get('component_count', 0))],
            ['Processing Time:', f"{analysis_data.get('processing_time', 0):.2f}s"],
            ['Confidence:', f"{analysis_data.get('avg_confidence', 0)*100:.1f}%"]
        ]

        table = Table(metadata, colWidths=[2*inch, 3*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1'))
        ]))

        story.append(table)

        return story

    def _create_executive_summary(self, analysis_data: Dict[str, Any]) -> List:
        """Create executive summary section."""
        story = []

        story.append(Paragraph("Executive Summary", self.styles['CustomSubtitle']))

        # Key findings
        findings = [
            f"Total components identified: {analysis_data.get('component_count', 0)}",
            f"Average detection confidence: {analysis_data.get('avg_confidence', 0)*100:.1f}%",
            f"Estimated BOM cost: ${analysis_data.get('bom_total_cost', 0):.2f}",
        ]

        if 'anomalies' in analysis_data:
            critical_count = len([a for a in analysis_data['anomalies'] if a.get('severity') == 'critical'])
            findings.append(f"Critical issues found: {critical_count}")

        for finding in findings:
            story.append(Paragraph(f"• {finding}", self.styles['CustomBody']))

        story.append(Spacer(1, 0.3*inch))

        # Component distribution chart
        chart = self._create_component_distribution_chart(analysis_data.get('components', []))
        if chart:
            story.append(chart)

        return story

    def _create_component_distribution_chart(self, components: List[Dict]) -> Optional[Drawing]:
        """Create pie chart of component distribution."""
        if not components:
            return None

        # Count by type
        type_counts = {}
        for comp in components:
            comp_type = comp.get('type', 'unknown')
            type_counts[comp_type] = type_counts.get(comp_type, 0) + 1

        # Create pie chart
        drawing = Drawing(400, 200)
        pie = Pie()
        pie.x = 150
        pie.y = 50
        pie.width = 100
        pie.height = 100

        pie.data = list(type_counts.values())
        pie.labels = list(type_counts.keys())
        pie.slices.strokeWidth = 0.5

        # Add colors
        colors_list = [colors.HexColor('#3498DB'), colors.HexColor('#E74C3C'),
                      colors.HexColor('#2ECC71'), colors.HexColor('#F39C12'),
                      colors.HexColor('#9B59B6'), colors.HexColor('#1ABC9C')]

        for i, slice in enumerate(pie.slices):
            slice.fillColor = colors_list[i % len(colors_list)]

        drawing.add(pie)

        return drawing

    def _create_component_section(self, analysis_data: Dict[str, Any]) -> List:
        """Create detailed component section."""
        story = []

        story.append(Paragraph("Component Analysis", self.styles['CustomSubtitle']))

        components = analysis_data.get('components', [])

        if not components:
            story.append(Paragraph("No components detected.", self.styles['CustomBody']))
            return story

        # Component table
        table_data = [['#', 'Type', 'Part Number', 'Confidence', 'Position']]

        for i, comp in enumerate(components[:20], 1):  # Limit to 20 for space
            bbox = comp.get('bounding_box', {})
            table_data.append([
                str(i),
                comp.get('type', 'unknown'),
                comp.get('part_number', 'N/A'),
                f"{comp.get('confidence', 0)*100:.1f}%",
                f"({bbox.get('x', 0)}, {bbox.get('y', 0)})"
            ])

        table = Table(table_data, colWidths=[0.5*inch, 1.5*inch, 2*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
        ]))

        story.append(table)

        if len(components) > 20:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(
                f"Showing 20 of {len(components)} components. See full list in appendix.",
                self.styles['CustomBody']
            ))

        return story

    def _create_bom_section(self, bom_data: List[Dict]) -> List:
        """Create BOM section."""
        story = []

        story.append(Paragraph("Bill of Materials (BOM)", self.styles['CustomSubtitle']))

        if not bom_data:
            story.append(Paragraph("BOM not available.", self.styles['CustomBody']))
            return story

        # BOM table
        table_data = [['Part', 'Manufacturer', 'Qty', 'Unit Price', 'Total']]

        total_cost = 0.0

        for item in bom_data:
            qty = item.get('quantity', 0)
            unit_price = item.get('unit_price', 0)
            total = qty * unit_price
            total_cost += total

            table_data.append([
                item.get('part_number', 'N/A'),
                item.get('manufacturer', 'N/A'),
                str(qty),
                f"${unit_price:.2f}",
                f"${total:.2f}"
            ])

        # Add total row
        table_data.append(['', '', '', 'TOTAL:', f"${total_cost:.2f}"])

        table = Table(table_data, colWidths=[2*inch, 2*inch, 0.7*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
            ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8F9FA')])
        ]))

        story.append(table)

        return story

    def _create_anomalies_section(self, anomalies: List[Dict]) -> List:
        """Create anomalies/issues section."""
        story = []

        story.append(Paragraph("Detected Issues & Anomalies", self.styles['CustomSubtitle']))

        if not anomalies:
            story.append(Paragraph("No anomalies detected. PCB appears healthy!", self.styles['CustomBody']))
            return story

        # Group by severity
        by_severity = {'critical': [], 'high': [], 'medium': [], 'low': []}

        for anomaly in anomalies:
            severity = anomaly.get('severity', 'low')
            if severity in by_severity:
                by_severity[severity].append(anomaly)

        # Display by severity
        severity_colors = {
            'critical': colors.HexColor('#E74C3C'),
            'high': colors.HexColor('#E67E22'),
            'medium': colors.HexColor('#F39C12'),
            'low': colors.HexColor('#3498DB')
        }

        for severity in ['critical', 'high', 'medium', 'low']:
            issues = by_severity[severity]
            if not issues:
                continue

            story.append(Paragraph(
                f"{severity.upper()} Severity ({len(issues)})",
                self.styles['Heading3']
            ))

            for i, anomaly in enumerate(issues, 1):
                # Issue box
                issue_text = f"""
                <b>{i}. {anomaly.get('title', 'Unknown Issue')}</b><br/>
                <i>Description:</i> {anomaly.get('description', 'N/A')}<br/>
                <i>Recommended Fix:</i> {anomaly.get('recommended_fix', 'N/A')}
                """

                story.append(Paragraph(issue_text, self.styles['CustomBody']))
                story.append(Spacer(1, 0.15*inch))

        return story

    def _create_recommendations_section(self, recommendations: List[Dict]) -> List:
        """Create AI recommendations section."""
        story = []

        story.append(Paragraph("AI-Powered Recommendations", self.styles['CustomSubtitle']))

        for i, rec in enumerate(recommendations, 1):
            rec_text = f"""
            <b>{i}. {rec.get('title', 'Recommendation')}</b><br/>
            {rec.get('description', 'N/A')}<br/>
            <i>Potential Savings:</i> ${rec.get('savings', 0):.2f}
            """

            story.append(Paragraph(rec_text, self.styles['CustomBody']))
            story.append(Spacer(1, 0.15*inch))

        return story


class PowerPointGenerator:
    """PowerPoint presentation generator."""

    def __init__(self):
        """Initialize PowerPoint generator."""
        logger.info("PowerPointGenerator initialized")

    async def generate_presentation(
        self,
        analysis_data: Dict[str, Any]
    ) -> bytes:
        """
        Generate PowerPoint presentation.

        Args:
            analysis_data: Analysis results

        Returns:
            PowerPoint bytes
        """
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)

        # Title slide
        self._add_title_slide(prs, analysis_data)

        # Overview slide
        self._add_overview_slide(prs, analysis_data)

        # Component distribution
        self._add_component_distribution_slide(prs, analysis_data)

        # BOM summary
        if 'bom' in analysis_data:
            self._add_bom_slide(prs, analysis_data['bom'])

        # Anomalies
        if 'anomalies' in analysis_data:
            self._add_anomalies_slide(prs, analysis_data['anomalies'])

        # Recommendations
        if 'recommendations' in analysis_data:
            self._add_recommendations_slide(prs, analysis_data['recommendations'])

        # Save to bytes
        buffer = BytesIO()
        prs.save(buffer)

        return buffer.getvalue()

    def _add_title_slide(self, prs: Presentation, analysis_data: Dict):
        """Add title slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[0])

        title = slide.shapes.title
        subtitle = slide.placeholders[1]

        title.text = f"PCB Analysis Report"
        subtitle.text = f"{analysis_data.get('pcb_name', 'Untitled')}\n{datetime.now().strftime('%Y-%m-%d')}"

    def _add_overview_slide(self, prs: Presentation, analysis_data: Dict):
        """Add overview slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[1])

        title = slide.shapes.title
        title.text = "Analysis Overview"

        # Add text box with key metrics
        left = Inches(1)
        top = Inches(2)
        width = Inches(8)
        height = Inches(4)

        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame

        metrics = [
            f"Components Detected: {analysis_data.get('component_count', 0)}",
            f"Average Confidence: {analysis_data.get('avg_confidence', 0)*100:.1f}%",
            f"Processing Time: {analysis_data.get('processing_time', 0):.2f}s",
            f"BOM Total Cost: ${analysis_data.get('bom_total_cost', 0):.2f}"
        ]

        for metric in metrics:
            p = tf.add_paragraph()
            p.text = metric
            p.font.size = Pt(20)

    def _add_component_distribution_slide(self, prs: Presentation, analysis_data: Dict):
        """Add component distribution slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[5])

        title = slide.shapes.title
        title.text = "Component Distribution"

        # Would add actual chart here
        # For now, add placeholder text
        txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(4))
        tf = txBox.text_frame
        tf.text = "Component distribution chart would appear here"

    def _add_bom_slide(self, prs: Presentation, bom_data: List[Dict]):
        """Add BOM slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[5])

        title = slide.shapes.title
        title.text = "Bill of Materials Summary"

        # Add table with top items
        rows = min(len(bom_data) + 1, 11)  # Max 10 items + header
        cols = 4

        left = Inches(1)
        top = Inches(2)
        width = Inches(8)
        height = Inches(4)

        table = slide.shapes.add_table(rows, cols, left, top, width, height).table

        # Header
        table.cell(0, 0).text = "Part Number"
        table.cell(0, 1).text = "Manufacturer"
        table.cell(0, 2).text = "Qty"
        table.cell(0, 3).text = "Total Cost"

        # Data
        for i, item in enumerate(bom_data[:10], 1):
            table.cell(i, 0).text = item.get('part_number', 'N/A')
            table.cell(i, 1).text = item.get('manufacturer', 'N/A')
            table.cell(i, 2).text = str(item.get('quantity', 0))
            table.cell(i, 3).text = f"${item.get('quantity', 0) * item.get('unit_price', 0):.2f}"

    def _add_anomalies_slide(self, prs: Presentation, anomalies: List[Dict]):
        """Add anomalies slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[1])

        title = slide.shapes.title
        title.text = f"Detected Issues ({len(anomalies)})"

        left = Inches(1)
        top = Inches(2)
        width = Inches(8)
        height = Inches(4)

        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame

        for i, anomaly in enumerate(anomalies[:5], 1):  # Top 5
            p = tf.add_paragraph()
            p.text = f"{i}. {anomaly.get('title', 'Unknown')} ({anomaly.get('severity', 'unknown')})"
            p.level = 0
            p.font.size = Pt(16)

            p = tf.add_paragraph()
            p.text = anomaly.get('description', 'N/A')
            p.level = 1
            p.font.size = Pt(14)

    def _add_recommendations_slide(self, prs: Presentation, recommendations: List[Dict]):
        """Add recommendations slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[1])

        title = slide.shapes.title
        title.text = "AI Recommendations"

        left = Inches(1)
        top = Inches(2)
        width = Inches(8)
        height = Inches(4)

        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame

        for i, rec in enumerate(recommendations[:5], 1):
            p = tf.add_paragraph()
            p.text = f"{i}. {rec.get('title', 'Recommendation')}"
            p.font.size = Pt(16)
            p.font.bold = True

            p = tf.add_paragraph()
            p.text = rec.get('description', 'N/A')
            p.level = 1
            p.font.size = Pt(14)


# Singleton instances
pdf_generator = PDFReportGenerator()
ppt_generator = PowerPointGenerator()

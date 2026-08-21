"""Generate a professionally styled PDF document for the Prophecy Run & Deployment Guide."""

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(
                54, 750, "Prophecy Trading Platform — Run & Deployment Guide"
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawString(
            54, 32, "Confidential & Proprietary • Prophecy Codex Platform v1.0"
        )
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#0f172a")
    accent_color = colors.HexColor("#0284c7")
    text_color = colors.HexColor("#1e293b")
    code_bg = colors.HexColor("#f1f5f9")

    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=15,
    )
    h1_style = ParagraphStyle(
        "Header1",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )
    h2_style = ParagraphStyle(
        "Header2",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=accent_color,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=text_color,
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "BulletCustom",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=text_color,
        leftIndent=15,
        spaceAfter=3,
    )
    code_style = ParagraphStyle(
        "CodeSnippet",
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=code_bg,
        borderPadding=6,
        spaceAfter=8,
        spaceBefore=4,
    )

    story = []

    # Title Banner
    story.append(Paragraph("PROPHECY TRADING PLATFORM", title_style))
    story.append(
        Paragraph(
            "Operations, Execution, Testing & Production Deployment Guide",
            subtitle_style,
        )
    )
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=accent_color,
            spaceBefore=0,
            spaceAfter=14,
        )
    )

    # Executive Overview
    story.append(
        Paragraph(
            "<b>Overview:</b> Prophecy is an enterprise-grade options trading, backtesting, and paper-execution platform engineered for Indian derivatives (NIFTY / BANKNIFTY). It features multi-timeframe strategy evaluation across 5 synchronized timeframes (1m, 3m, 5m, 15m, 30m), an authoritative technical indicators engine, automated option contract selection, pre-trade risk management with emergency kill-switch protection, and a real-time FastAPI + Server-Sent Events (SSE) web dashboard.",
            body_style,
        )
    )
    story.append(Spacer(1, 8))

    # Section 1
    story.append(Paragraph("1. Prerequisites & System Setup", h1_style))
    story.append(
        Paragraph(
            "• <b>Python Version:</b> Python 3.9+ (Python 3.10/3.11/3.12 fully supported).",
            bullet_style,
        )
    )
    story.append(
        Paragraph(
            "• <b>Package Management:</b> <font name='Courier'>uv</font> (recommended) or standard <font name='Courier'>pip/venv</font>.",
            bullet_style,
        )
    )
    story.append(
        Paragraph(
            "• <b>Operating System:</b> Windows 10/11, Linux (Ubuntu 20.04+), or macOS.",
            bullet_style,
        )
    )
    story.append(Paragraph("• <b>Repository Clone:</b>", body_style))
    story.append(
        Paragraph(
            "git clone https://github.com/skynetukhra-coder/dev_stock_01.git<br/>cd dev_stock_01",
            code_style,
        )
    )

    # Section 2
    story.append(Paragraph("2. Running Locally", h1_style))
    story.append(
        Paragraph(
            "<b>Method A: Using <font name='Courier'>uv</font> (Fastest, zero manual venv configuration)</b>",
            h2_style,
        )
    )
    story.append(Paragraph("PowerShell (Windows):", body_style))
    story.append(
        Paragraph(
            '$env:PYTHONPATH = "engine/src;backend"<br/>uv run --with fastapi --with uvicorn --with pydantic uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload',
            code_style,
        )
    )
    story.append(Paragraph("Bash (Linux / macOS):", body_style))
    story.append(
        Paragraph(
            'export PYTHONPATH="engine/src:backend"<br/>uv run --with fastapi --with uvicorn --with pydantic uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload',
            code_style,
        )
    )

    story.append(
        Paragraph(
            "<b>Method B: Using Standard Python Virtual Environment</b>", h2_style
        )
    )
    story.append(
        Paragraph(
            'python -m venv .venv<br/>source .venv/bin/activate  # On Windows: .venv\\Scripts\\Activate.ps1<br/>pip install fastapi uvicorn pydantic httpx<br/>export PYTHONPATH="engine/src:backend"<br/>uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload',
            code_style,
        )
    )

    # Section 3
    story.append(
        Paragraph("3. Web Dashboard & Testing Strategy Cases 1 to 6", h1_style)
    )
    story.append(
        Paragraph(
            "Once launched, navigate to <b>http://127.0.0.1:8000/dashboard</b> to access the real-time operator matrix.",
            body_style,
        )
    )

    cases_data = [
        [
            "Case #",
            "Strategy Name",
            "5-Timeframe Condition Rule",
            "PCR Rule",
            "Resolved Contract",
        ],
        [
            "Case 1",
            "Straddle Baseline",
            "ADX 15-30 & RSI 40-60 on 1m, 3m, 5m, 15m, 30m",
            "PCR <= 0.60",
            "ATM CE + ATM PE",
        ],
        [
            "Case 2",
            "Straddle Special",
            "ADX 0-10 & RSI 40-60 on all 5 timeframes",
            "PCR <= 0.50",
            "ATM CE + ATM PE",
        ],
        [
            "Case 3",
            "Directional Call",
            "ADX 15-30 & RSI 0-60 on all 5 timeframes",
            "PCR < 0.80",
            "ATM/ITM-1 CE",
        ],
        [
            "Case 4",
            "Directional Put",
            "ADX 15-30 & RSI 45-100 on all 5 timeframes",
            "PCR > 1.25",
            "ATM/ITM-1 PE",
        ],
        [
            "Case 5",
            "Call Special",
            "RSI <= 25.0 (extreme oversold) on all 5 timeframes",
            "Extreme Low",
            "ATM/ITM-1 CE",
        ],
        [
            "Case 6",
            "Put Special",
            "RSI >= 70.0 (extreme overbought) on all 5 timeframes",
            "Extreme High",
            "ATM/ITM-1 PE",
        ],
    ]
    t = Table(cases_data, colWidths=[45, 95, 185, 65, 114])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f1f5f9")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 8))

    # Section 4
    story.append(Paragraph("4. Automated Verification & Quality Assurance", h1_style))
    story.append(
        Paragraph(
            "The platform carries <b>100 automated unit and integration tests</b> with a 100% pass rate:",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "# 1. Run 93 Engine Unit Tests (indicators, strategy cases, contract selector, risk manager)<br/>"
            "uv run python -m unittest discover -s engine/tests -v<br/><br/>"
            "# 2. Run 7 FastAPI Integration Tests (REST endpoints, SSE events, kill switch, backtester)<br/>"
            "uv run --with fastapi --with uvicorn --with pydantic --with httpx python -m unittest discover -s backend/app/tests -v<br/><br/>"
            "# 3. Run PEP-8 & Linter Quality Checks<br/>"
            "uv run --with ruff ruff check engine/src engine/tests backend/app<br/>"
            "uv run --with ruff ruff format --check engine/src engine/tests backend/app",
            code_style,
        )
    )

    # Section 5
    story.append(Paragraph("5. Environment & Safety Parameters (.env)", h1_style))
    story.append(
        Paragraph(
            "PROPHECY_EXECUTION_MODE=MANUAL_CONFIRMATION  # SIGNAL_ONLY | MANUAL_CONFIRMATION | AUTO_PAPER | LIVE<br/>"
            "PROPHECY_MAX_DAILY_REALIZED_LOSS=10000.0   # Max daily loss ceiling in INR<br/>"
            "PROPHECY_MAX_DAILY_TOTAL_LOSS=15000.0      # Max total drawdown ceiling in INR<br/>"
            "PROPHECY_MAX_OPEN_POSITIONS=3              # Max concurrent open positions<br/>"
            "PROPHECY_MAX_TRADE_NOTIONAL=50000.0        # Max rupee notional per trade<br/>"
            "PROPHECY_LIVE_TRADING_ACKNOWLEDGED=FALSE   # Mandatory live gate flag<br/>"
            "PROPHECY_OPERATOR_SIGNATURE=               # Live operator cryptographic authorization",
            code_style,
        )
    )

    # Section 6
    story.append(Paragraph("6. Production Deployment Architectures", h1_style))
    story.append(
        Paragraph(
            "<b>Option 1: Containerized Docker Deployment (Recommended)</b>", h2_style
        )
    )
    story.append(
        Paragraph(
            "# Build Docker image<br/>"
            "docker build -t prophecy-engine:latest -f infra/docker/Dockerfile .<br/><br/>"
            "# Run container with auto-restart and environment mapping<br/>"
            "docker run -d --name prophecy-app -p 8000:8000 --env-file .env --restart unless-stopped prophecy-engine:latest",
            code_style,
        )
    )

    story.append(
        Paragraph(
            "<b>Option 2: Linux Systemd Daemon + NGINX (with SSE Buffer Bypass)</b>",
            h2_style,
        )
    )
    story.append(
        Paragraph(
            "NGINX reverse-proxy configuration (<font name='Courier'>/etc/nginx/sites-available/prophecy</font>):",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "server {<br/>"
            "    listen 80;<br/>"
            "    server_name trading.yourdomain.com;<br/><br/>"
            "    location / {<br/>"
            "        proxy_pass http://127.0.0.1:8000;<br/>"
            "        proxy_set_header Host $host;<br/>"
            "        proxy_set_header X-Real-IP $remote_addr;<br/>"
            "        proxy_set_header X-Forwarded-Proto $scheme;<br/><br/>"
            "        # CRITICAL: Disable buffering for Server-Sent Events (SSE) real-time streaming<br/>"
            "        proxy_buffering off;<br/>"
            "        proxy_cache off;<br/>"
            "        proxy_set_header Connection '';<br/>"
            "        proxy_http_version 1.1;<br/>"
            "        proxy_read_timeout 86400s;<br/>"
            "    }<br/>"
            "}",
            code_style,
        )
    )

    # Section 7
    story.append(Paragraph("7. Operational Runbooks & Emergency Procedures", h1_style))
    story.append(
        Paragraph(
            "• <b>Emergency Kill Switch:</b> In case of abnormal exchange volatility, click <b>STOP KILL SWITCH</b> on the web dashboard or send <font name='Courier'>POST /kill-switch {\"active\": true}</font>. All new entries are blocked instantly while liquidation exits remain active.",
            bullet_style,
        )
    )
    story.append(
        Paragraph(
            "• <b>Loss Limit Lockdown:</b> If daily realized loss exceeds ₹10,000, the Risk Manager automatically transitions to lockdown until the next trading session (09:15 IST).",
            bullet_style,
        )
    )
    story.append(
        Paragraph(
            "• <b>6-Lock Live Execution Gate:</b> Real broker orders require multi-key authorization, single-use token nonces (60s TTL), size ceilings (max 100 units / ₹35,000), and 10% fat-finger price sanity checks.",
            bullet_style,
        )
    )

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {filename}")


if __name__ == "__main__":
    out_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "Prophecy_Run_and_Deployment_Guide.pdf"
    )
    build_pdf(os.path.abspath(out_path))

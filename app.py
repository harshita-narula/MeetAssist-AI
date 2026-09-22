import os
import re
import base64
import subprocess
import tempfile
from datetime import date, time
from io import BytesIO
from pathlib import Path

import imageio_ffmpeg
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from speech import transcribe_audio

from foundry import (
    sign_in_with_microsoft,
    clean_meeting_transcript,
    analyze_transcript,
    ask_meeting_question,
    generate_mom,
)

from video_indexer import (
    load_video_indexer_json,
    parse_video_indexer,
    build_video_context,
    build_video_timeline,
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="MeetAssist AI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "raw_transcript": "",
    "transcript": "",
    "analysis": "",
    "mom": "",
    "segments": [],
    "uploaded_name": "",
    "uploaded_id": "",
    "is_video_upload": False,

    # Video Indexer
    "video_indexer_data": {},
    "video_indexer_parsed": {},
    "video_context": "",
    "video_name": "",
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


# =========================================================
# MICROSOFT SIGN-IN — UI / AUTH FLOW ONLY
# =========================================================

if not st.session_state.authenticated:

    st.markdown(
        """
        <style>
        .login-shell {
            min-height: 78vh;
            display:flex;
            align-items:center;
            justify-content:center;
            padding:40px 20px;
        }
        .login-card {
            width:min(560px, 100%);
            background:#ffffff;
            border:1px solid #dbe4f0;
            border-radius:28px;
            padding:44px 42px 38px;
            text-align:center;
            box-shadow:0 25px 70px rgba(15,23,42,.12);
        }
        .login-icon {
            width:68px; height:68px; margin:0 auto 18px;
            border-radius:20px; display:grid; place-items:center;
            background:linear-gradient(135deg,#2563eb,#1e3a8a);
            color:#fff; font-size:30px;
            box-shadow:0 12px 30px rgba(37,99,235,.25);
        }
        .login-title {
            font-size:36px; font-weight:800; letter-spacing:-1.2px;
            color:#0f172a; margin-bottom:8px;
        }
        .login-subtitle {
            color:#64748b; font-size:16px; line-height:1.65;
            margin:0 auto 24px; max-width:430px;
        }
        .login-note {
            color:#94a3b8; font-size:12px; margin-top:14px;
        }

        /* Streamlit button is rendered immediately below this HTML card.
           These rules visually pull it into the card so the Microsoft
           button is part of the login panel rather than a separate bar. */
        div[data-testid="stButton"] {
            display:flex;
            justify-content:center;
            margin-top:-96px;
            position:relative;
            z-index:5;
        }
        div[data-testid="stButton"] > button {
            width:min(470px, calc(100vw - 80px)) !important;
            height:52px !important;
            border-radius:13px !important;
            border:1px solid #1d4ed8 !important;
            background:linear-gradient(135deg,#2563eb,#1e40af) !important;
            color:#ffffff !important;
            font-size:15px !important;
            font-weight:750 !important;
            box-shadow:0 12px 26px rgba(30,64,175,.22) !important;
        }
        div[data-testid="stButton"] > button:hover {
            background:linear-gradient(135deg,#1d4ed8,#1e3a8a) !important;
            border-color:#1e3a8a !important;
            transform:translateY(-1px);
            box-shadow:0 15px 30px rgba(30,64,175,.28) !important;
        }
        .login-footer {
            text-align:center;
            color:#94a3b8;
            font-size:12px;
            margin-top:58px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="login-shell">
            <div class="login-card">
                <div class="login-icon">🎙</div>
                <div class="login-title">MeetAssist AI</div>
                <div class="login-subtitle">
                    Your AI workspace for turning meeting conversations
                    into transcripts, decisions, action items and insights.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "🔷  Sign in with Microsoft",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("Opening secure Microsoft sign-in..."):
                sign_in_with_microsoft()

            # Authentication succeeded. Return to the main MeetAssist
            # page immediately; the Streamlit app itself does not show
            # an authentication-complete screen.
            st.session_state.authenticated = True
            st.rerun()

        except Exception as error:
            st.error(
                "Microsoft sign-in was not completed. "
                f"\n\n{error}"
            )

    st.markdown(
        '<div class="login-footer">'
        'Secure authentication powered by Microsoft Azure'
        '</div>',
        unsafe_allow_html=True,
    )

    st.stop()


# =========================================================
# CSS — UI ONLY
# =========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp {
        background: #f8fafc;
        font-family: Inter, sans-serif;
    }
    .block-container { max-width: 1480px; padding-top: 0.25rem; padding-bottom: 4rem; padding-left: 1.25rem; padding-right: 1.25rem; }
    /* Hide Streamlit's empty application header/toolbar so the website navbar is the only header. */
    header[data-testid="stHeader"] { display:none !important; }
    [data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }

    /* top navigation */
    .top-nav {
        position: sticky; top: 0; z-index: 999;
        display:flex; align-items:center; justify-content:space-between;
        padding: 14px 0; margin-bottom: 18px;
        background: rgba(248,250,252,.92); backdrop-filter: blur(14px);
        border-bottom: 1px solid #e2e8f0;
    }
    .brand { display:flex; align-items:center; gap:11px; font-weight:800; font-size:21px; color:#0f172a; }
    .brand-icon { width:44px; height:44px; border-radius:12px; display:grid; place-items:center; background:linear-gradient(135deg,#4f46e5,#06b6d4); color:#fff; font-size:20px; box-shadow:0 8px 20px rgba(79,70,229,.22); }
    .nav-links { display:flex; gap:28px; font-size:15px; font-weight:600; color:#64748b; }
    .nav-links a { color:#475569; text-decoration:none; }
    .nav-links a:hover { color:#4f46e5; }

    /* homepage hero */
    .home-hero {
        display:grid; grid-template-columns:1.02fr .98fr; gap:46px; align-items:center;
        padding:42px 0 34px;
    }
    .eyebrow { display:inline-flex; padding:7px 12px; border-radius:999px; background:#eef2ff; color:#4f46e5; font-size:12px; font-weight:800; letter-spacing:.6px; }
    .home-title { font-size:56px; line-height:1.05; letter-spacing:-2.4px; font-weight:800; color:#0f172a; margin:16px 0; white-space:nowrap; }
    .home-title span { color:#4f46e5; }
    .home-tagline { font-size:20px; line-height:1.7; color:#64748b; max-width:650px; margin-bottom:24px; }
    .hero-points { display:flex; gap:10px; flex-wrap:wrap; }
    .hero-pill { padding:9px 13px; border:1px solid #e2e8f0; border-radius:999px; background:white; color:#475569; font-size:13px; font-weight:600; box-shadow:0 5px 18px rgba(15,23,42,.04); }
    .hero-visual { border-radius:28px; padding:10px; background:linear-gradient(135deg,#eef2ff,#ecfeff); box-shadow:0 25px 60px rgba(15,23,42,.12); animation:float 5s ease-in-out infinite; overflow:hidden; }
    .hero-visual img { width:100%; height:auto; aspect-ratio:16/9; object-fit:cover; display:block; border-radius:20px; }
    @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)} }

    /* feature cards */
    .feature-heading { text-align:center; font-size:35px; font-weight:800; color:#0f172a; margin:24px 0 8px; }
    .feature-sub { text-align:center; color:#64748b; font-size:16px; margin-bottom:22px; }
    .feature-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:50px; }
    .feature-card { background:#fff; border:1px solid #e2e8f0; border-radius:20px; padding:26px 22px; min-height:170px; transition:transform .25s ease, box-shadow .25s ease, border-color .25s ease; animation:cardIn .65s ease both; }
    .feature-card:nth-child(2){animation-delay:.08s}.feature-card:nth-child(3){animation-delay:.16s}.feature-card:nth-child(4){animation-delay:.24s}
    .feature-card:hover { transform:translateY(-7px); box-shadow:0 18px 38px rgba(15,23,42,.10); border-color:#c7d2fe; }
    .feature-icon { width:45px;height:45px;border-radius:13px;display:grid;place-items:center;background:#eef2ff;font-size:21px;margin-bottom:16px; }
    .feature-card h4 { margin:0 0 8px; color:#0f172a; font-size:16px; }
    .feature-card p { margin:0; color:#64748b; font-size:13px; line-height:1.6; }
    @keyframes cardIn { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }

    .section-title { font-size:30px; font-weight:800; letter-spacing:-.5px; margin:30px 0 14px; color:#0f172a; }
    .analysis-banner { padding:22px 24px; border-radius:18px; background:linear-gradient(135deg,#111827,#312e81); color:white; margin:8px 0 24px; box-shadow:0 16px 35px rgba(49,46,129,.18); }
    .analysis-banner h3 {margin:0 0 6px;font-size:21px}.analysis-banner p{margin:0;color:#cbd5e1;font-size:14px}

    div[data-testid="stMetric"] { background:#fff; border:1px solid #e2e8f0; border-radius:16px; padding:15px; box-shadow:0 7px 22px rgba(15,23,42,.05); }
    div[data-testid="stMetricValue"] { font-weight:800; color:#0f172a; }
    div[data-testid="stFileUploader"] section { border:1.5px dashed #94a3b8; border-radius:16px; background:#fff; }
    div[data-baseweb="select"] > div, div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea, div[data-testid="stDateInput"] input, div[data-testid="stTimeInput"] input { border-radius:12px !important; }
    .stButton > button, .stDownloadButton > button { border-radius:12px; min-height:44px; font-weight:750; transition:transform .15s ease,box-shadow .15s ease; }
    /* Primary buttons — dark navy to purple */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #111827, #312e81) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 750 !important;
    min-height: 44px !important;
    transition: all 0.2s ease !important;
}

/* Primary button hover */
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #111827, #312e81) !important;
    color: white !important;
    border: none !important;
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(49, 46, 129, 0.20) !important;
}
    .stButton > button:hover, .stDownloadButton > button:hover { transform:translateY(-1px); box-shadow:0 8px 20px rgba(15,23,42,.10); }
    div[data-testid="stExpander"] { border:1px solid #e2e8f0; border-radius:14px; background:#fff; }
    div[data-testid="stAlert"] { border-radius:13px; }
    button[data-baseweb="tab"] { font-weight:650; }
    @media(max-width:900px){ .home-hero{grid-template-columns:1fr;}.feature-grid{grid-template-columns:repeat(2,1fr)} .home-title{font-size:45px; white-space:normal}.nav-links{display:none} }
    @media(max-width:600px){ .feature-grid{grid-template-columns:1fr}.home-title{font-size:38px}.home-hero{padding-top:30px} }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HOMEPAGE / NAVIGATION — UI ONLY
# =========================================================

# Hero image generated specifically for MeetAssist AI.
HERO_IMAGE_PATH = Path(__file__).parent / "hero_meeting.jpeg"
if HERO_IMAGE_PATH.exists():
    HERO_IMAGE_DATA = base64.b64encode(HERO_IMAGE_PATH.read_bytes()).decode("utf-8")
    HERO_IMAGE_SRC = f"data:image/png;base64,{HERO_IMAGE_DATA}"
else:
    HERO_IMAGE_SRC = ""



st.markdown(
    f"""
    <div class="top-nav">
        <div class="brand"><div class="brand-icon">🎙</div> MeetAssist AI</div>
        <div class="nav-links">
            <a href="#home">Home</a>
            <a href="#features">Features</a>
            <a href="#analyze">Analyze Meeting</a>
        </div>
    </div>

    <div id="home" class="home-hero">
        <div>
            <div class="eyebrow">AI-POWERED MEETING INTELLIGENCE</div>
            <div class="home-title">Capture the Conversation<br><span>Unlock the Insight</span></div>
            <div class="home-tagline">Turn every meeting into a clear record of what was said, what was decided, and what happens next — powered by AI.</div>
            <div class="hero-points">
                <div class="hero-pill">🎙 Speech Intelligence</div>
                <div class="hero-pill">🎥 Video Insights</div>
                <div class="hero-pill">🤖 AI Analysis</div>
                <div class="hero-pill">📄 Smart MoM</div>
            </div>
        </div>
        <div class="hero-visual"><img src="{HERO_IMAGE_SRC}" alt="MeetAssist AI meeting intelligence illustration"></div>
    </div>

    <div id="features" class="feature-heading">Everything you need after a meeting</div>
    <div class="feature-sub">One workspace for turning conversations into useful, actionable intelligence.</div>
    <div class="feature-grid">
        <div class="feature-card"><div class="feature-icon">🎙️</div><h4>Smart Transcription</h4><p>Convert meeting audio into a clean transcript with timestamps and timeline context.</p></div>
        <div class="feature-card"><div class="feature-icon">🎥</div><h4>Video Intelligence</h4><p>Combine speech with OCR, scenes, topics, keywords and visual evidence from the meeting.</p></div>
        <div class="feature-card"><div class="feature-icon">🧠</div><h4>Meeting Analysis</h4><p>Surface summaries, decisions, action items, risks, open questions and unresolved issues.</p></div>
        <div class="feature-card"><div class="feature-icon">💬</div><h4>Ask My Meeting</h4><p>Search your meeting context and ask questions about what was discussed.</p></div>
    </div>

    <div id="analyze" class="analysis-banner">
        <h3>Turn your next meeting into actionable intelligence.</h3>
        <p>Upload a meeting recording to uncover the conversation, decisions, action items and insights already inside it.</p>
    </div>

    <div class="section-title">🎬 Analyze Your Meeting</div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# MEDIA DISPLAY — detect actual video stream
# =========================================================

def has_video_stream(uploaded_file):

    suffix = Path(uploaded_file.name).suffix.lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        temp_path = temp_file.name

    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        command = [ffmpeg, "-hide_banner", "-i", temp_path]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return bool(re.search(r"Stream #.*?: Video:", result.stderr, flags=re.IGNORECASE))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# =========================================================
# MEDIA → WAV
# =========================================================

def convert_media_to_wav(uploaded_file):

    suffix = Path(
        uploaded_file.name
    ).suffix.lower()

    if suffix not in [
        ".wav",
        ".mp4",
    ]:

        raise ValueError(
            "Only WAV and MP4 files are supported."
        )

    temp_paths = []

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as input_file:

        input_file.write(
            uploaded_file.getbuffer()
        )

        input_path = input_file.name

    temp_paths.append(
        input_path
    )

    wav_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav",
    )

    wav_path = wav_file.name

    wav_file.close()

    temp_paths.append(
        wav_path
    )

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg,
        "-y",
        "-i",
        input_path,
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        wav_path,
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:

        details = (
            result.stderr[-1500:]
            if result.stderr
            else "Unknown FFmpeg error."
        )

        raise RuntimeError(
            "Could not extract audio.\n\n"
            + details
        )

    return wav_path, temp_paths


# =========================================================
# AUDIO TIMELINE
# =========================================================

def build_audio_timeline(
    segments,
):

    lines = []

    for segment in segments:

        text = segment.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        lines.append(
            f"[{segment.get('start_time', '00:00')} - "
            f"{segment.get('end_time', '00:00')}] "
            f"{text}"
        )

    return "\n".join(lines)


# =========================================================
# REPORT PARSING
# =========================================================

def extract_meeting_iq(report):

    match = re.search(
        r"##\s*MEETING IQ(.*?)(?=\n##\s|\Z)",
        report,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:

        return match.group(1).strip()

    return ""


def extract_metric(
    section_text,
    label,
):

    match = re.search(
        rf"{re.escape(label)}\s*:\s*(\d+)",
        section_text,
        flags=re.IGNORECASE,
    )

    if match:

        return int(
            match.group(1)
        )

    return 0


def extract_section(
    report,
    heading,
):

    match = re.search(
        rf"##\s*{re.escape(heading)}"
        rf"(.*?)(?=\n##\s|\Z)",
        report,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:

        return match.group(1).strip()

    return ""


# =========================================================
# PDF
# =========================================================

def clean_pdf_text(text):

    text = str(text)

    text = (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    text = re.sub(
        r"\*\*(.*?)\*\*",
        r"<b>\1</b>",
        text,
    )

    text = re.sub(
        r"`(.*?)`",
        r"\1",
        text,
    )

    return text


def markdown_to_pdf(
    markdown_text: str,
    title: str,
) -> bytes:

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=title,
        author="MeetAssist AI",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MeetAssistTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=14,
    )

    h1_style = ParagraphStyle(
        "MeetAssistH1",
        parent=styles["Heading1"],
        fontSize=15,
        leading=19,
        spaceBefore=10,
        spaceAfter=7,
    )

    h2_style = ParagraphStyle(
        "MeetAssistH2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=5,
    )

    body_style = ParagraphStyle(
        "MeetAssistBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        "MeetAssistBullet",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-7,
        spaceAfter=3,
    )

    story = [
        Paragraph(
            title,
            title_style,
        )
    ]

    lines = markdown_text.splitlines()

    i = 0

    while i < len(lines):

        line = lines[i].strip()

        if not line:

            story.append(
                Spacer(1, 3)
            )

            i += 1

            continue

        if line.startswith("# "):

            story.append(
                Paragraph(
                    clean_pdf_text(
                        line[2:]
                    ),
                    h1_style,
                )
            )

            i += 1

            continue

        if line.startswith("## "):

            story.append(
                Paragraph(
                    clean_pdf_text(
                        line[3:]
                    ),
                    h1_style,
                )
            )

            i += 1

            continue

        if line.startswith("### "):

            story.append(
                Paragraph(
                    clean_pdf_text(
                        line[4:]
                    ),
                    h2_style,
                )
            )

            i += 1

            continue

        # -------------------------------------------------
        # TABLE
        # -------------------------------------------------

        if (
            "|" in line
            and i + 1 < len(lines)
            and "|" in lines[i + 1]
        ):

            separator = (
                lines[i + 1]
                .replace("|", "")
                .replace("-", "")
                .replace(":", "")
                .replace(" ", "")
            )

            if separator == "":

                rows = []

                header = [
                    x.strip()
                    for x in line.strip("|").split("|")
                ]

                rows.append(header)

                i += 2

                while (
                    i < len(lines)
                    and "|" in lines[i]
                ):

                    row = [
                        x.strip()
                        for x in lines[i]
                        .strip("|")
                        .split("|")
                    ]

                    rows.append(row)

                    i += 1

                column_count = max(
                    len(row)
                    for row in rows
                )

                for row in rows:

                    while len(row) < column_count:

                        row.append("")

                formatted = []

                for row in rows:

                    formatted.append(
                        [
                            Paragraph(
                                clean_pdf_text(
                                    cell
                                ),
                                body_style,
                            )
                            for cell in row
                        ]
                    )

                width = (
                    170 * mm
                    / max(column_count, 1)
                )

                table = Table(
                    formatted,
                    repeatRows=1,
                    colWidths=[
                        width
                    ] * column_count,
                )

                table.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, 0),
                                colors.lightgrey,
                            ),
                            (
                                "FONTNAME",
                                (0, 0),
                                (-1, 0),
                                "Helvetica-Bold",
                            ),
                            (
                                "GRID",
                                (0, 0),
                                (-1, -1),
                                0.5,
                                colors.grey,
                            ),
                            (
                                "VALIGN",
                                (0, 0),
                                (-1, -1),
                                "TOP",
                            ),
                            (
                                "LEFTPADDING",
                                (0, 0),
                                (-1, -1),
                                4,
                            ),
                            (
                                "RIGHTPADDING",
                                (0, 0),
                                (-1, -1),
                                4,
                            ),
                        ]
                    )
                )

                story.append(
                    table
                )

                story.append(
                    Spacer(1, 8)
                )

                continue

        # -------------------------------------------------
        # BULLET
        # -------------------------------------------------

        if (
            line.startswith("- ")
            or line.startswith("* ")
        ):

            story.append(
                Paragraph(
                    "• "
                    + clean_pdf_text(
                        line[2:]
                    ),
                    bullet_style,
                )
            )

            i += 1

            continue

        story.append(
            Paragraph(
                clean_pdf_text(line),
                body_style,
            )
        )

        i += 1

    document.build(
        story
    )

    return buffer.getvalue()


# =========================================================
# STEP 1 — UPLOAD
# =========================================================

st.markdown(
    '<div class="section-title">'
    "1️⃣ Upload Meeting"
    "</div>",
    unsafe_allow_html=True,
)


language = st.selectbox(
    "🌐 Meeting language",
    [
        ("English (India)", "en-IN"),
        ("English (US)", "en-US"),
    ],
    format_func=lambda x: x[0],
)


date_col, time_col = st.columns(2)

with date_col:

    meeting_date = st.date_input(
        "📅 Meeting date",
        value=date.today(),
    )

with time_col:

    meeting_time = st.time_input(
        "🕒 Meeting start time",
        value=time(10, 0),
    )


uploaded_file = st.file_uploader(
    "Upload a meeting recording",
    type=["wav", "mp4"],
    help="Upload a WAV or MP4 meeting recording.",
)


if uploaded_file is not None:

    current_upload_id = (
        f"{uploaded_file.name}_"
        f"{uploaded_file.size}"
    )

    if (
        st.session_state.uploaded_id
        and st.session_state.uploaded_id
        != current_upload_id
    ):

        st.session_state.raw_transcript = ""
        st.session_state.transcript = ""
        st.session_state.analysis = ""
        st.session_state.mom = ""
        st.session_state.segments = []

        st.session_state.video_indexer_data = {}
        st.session_state.video_indexer_parsed = {}
        st.session_state.video_context = ""
        st.session_state.video_name = ""

        # Detect whether this upload contains an actual video stream.
        # Audio-only MP4 files are treated as audio and will not show
        # the Video Intelligence section.
        try:
            st.session_state.is_video_upload = has_video_stream(
                uploaded_file
            )
        except Exception:
            st.session_state.is_video_upload = False

    elif not st.session_state.uploaded_id:
        try:
            st.session_state.is_video_upload = has_video_stream(
                uploaded_file
            )
        except Exception:
            st.session_state.is_video_upload = False

    st.session_state.uploaded_id = (
        current_upload_id
    )

    st.session_state.uploaded_name = (
        uploaded_file.name
    )


    try:

        if has_video_stream(uploaded_file):
            st.video(uploaded_file)
        else:
            st.audio(uploaded_file)

    except Exception:

        # Safe fallback for audio files
        st.audio(uploaded_file)

    st.caption(
        f"Selected file: **{uploaded_file.name}**"
    )


    # =====================================================
    # TRANSCRIBE
    # =====================================================

    if st.button(
        "🎤 Transcribe Meeting",
        type="primary",
        use_container_width=True,
    ):

        wav_path = None
        temp_paths = []

        try:

            with st.spinner(
                "Preparing meeting audio..."
            ):

                wav_path, temp_paths = (
                    convert_media_to_wav(
                        uploaded_file
                    )
                )

            with st.spinner(
                "Azure AI Speech is transcribing..."
            ):

                speech_result = (
                    transcribe_audio(
                        wav_path,
                        language[1],
                    )
                )

            raw_text = speech_result[
                "text"
            ]

            segments = speech_result[
                "segments"
            ]

            st.session_state.raw_transcript = (
                raw_text
            )

            st.session_state.segments = (
                segments
            )

            with st.spinner(
                "MeetAssist AI is cleaning the transcript..."
            ):

                cleaned = (
                    clean_meeting_transcript(
                        raw_text
                    )
                )

            st.session_state.transcript = (
                cleaned
            )

            st.session_state.analysis = ""
            st.session_state.mom = ""

            st.success(
                "✅ Meeting transcription completed!"
            )

        except Exception as error:

            st.error(
                f"❌ Processing failed:\n\n{error}"
            )

        finally:

            for path in temp_paths:

                if (
                    path
                    and os.path.exists(path)
                ):

                    try:
                        os.remove(path)
                    except OSError:
                        pass


# =========================================================
# VIDEO INDEXER IMPORT
# =========================================================

if (
    st.session_state.transcript
    and uploaded_file is not None
    and st.session_state.is_video_upload
):

    st.divider()

    st.markdown(
        '<div class="section-title">'
        "🎥 Video Intelligence"
        "</div>",
        unsafe_allow_html=True,
    )

    st.info(
        "For the current Video Indexer Trial workflow, "
        "export the video's **Insights JSON** from the "
        "Video Indexer portal and upload it here. "
        "The app will combine those real Video Indexer "
        "insights with the speech transcript."
    )

    video_json_file = st.file_uploader(
        "Upload Video Indexer Insights JSON",
        type=["json"],
        key="video_indexer_json",
        help=(
            "In Video Indexer: Download → "
            "Insights (JSON), then save the JSON file "
            "and upload it here."
        ),
    )

    if video_json_file is not None:

        try:

            raw_json = load_video_indexer_json(
                video_json_file.getvalue()
            )

            parsed = parse_video_indexer(
                raw_json
            )

            context = build_video_context(
                parsed
            )

            st.session_state.video_indexer_data = (
                raw_json
            )

            st.session_state.video_indexer_parsed = (
                parsed
            )

            st.session_state.video_context = (
                context
            )

            st.session_state.video_name = (
                parsed["metadata"].get(
                    "name",
                    "",
                )
            )

            st.success(
                "✅ Video Indexer insights loaded!"
            )

        except Exception as error:

            st.error(
                f"❌ Video Indexer JSON error:\n\n"
                f"{error}"
            )


# =========================================================
# SHOW VIDEO INTELLIGENCE
# =========================================================

if st.session_state.video_indexer_parsed:

    parsed_video = (
        st.session_state.video_indexer_parsed
    )

    metadata = parsed_video.get(
        "metadata",
        {},
    )

    st.markdown(
        "### 🎥 Video Indexer Insights"
    )

    m1, m2, m3, m4 = st.columns(4)

    with m1:

        st.metric(
            "📝 OCR items",
            len(
                parsed_video.get(
                    "ocr",
                    [],
                )
            ),
        )

    with m2:

        st.metric(
            "🔑 Keywords",
            len(
                parsed_video.get(
                    "keywords",
                    [],
                )
            ),
        )

    with m3:

        st.metric(
            "🎬 Scenes",
            len(
                parsed_video.get(
                    "scenes",
                    [],
                )
            ),
        )

    with m4:

        st.metric(
            "🏷️ Topics",
            len(
                parsed_video.get(
                    "topics",
                    [],
                )
            ),
        )


    (
        ocr_tab,
        topic_tab,
        scene_tab,
        entity_tab,
        vi_timeline_tab,
    ) = st.tabs(
        [
            "🖥️ OCR / Screen Text",
            "🔑 Topics & Keywords",
            "🎬 Scenes",
            "👤 Entities",
            "🕐 Video Timeline",
        ]
    )


    # -----------------------------------------------------
    # OCR
    # -----------------------------------------------------

    with ocr_tab:

        st.markdown(
            "#### Text detected from video frames"
        )

        ocr_items = parsed_video.get(
            "ocr",
            [],
        )

        if ocr_items:

            for item in ocr_items[:60]:

                st.markdown(
                    f"**{item['start_time']} - "
                    f"{item['end_time']}**  "
                    f"{item['text']}"
                )

        else:

            st.info(
                "No OCR text found."
            )


    # -----------------------------------------------------
    # TOPICS / KEYWORDS
    # -----------------------------------------------------

    with topic_tab:

        st.markdown(
            "#### Topics"
        )

        topics = parsed_video.get(
            "topics",
            [],
        )

        if topics:

            st.write(
                list(
                    dict.fromkeys(
                        item["name"]
                        for item in topics
                    )
                )
            )

        else:

            st.info(
                "No topics detected."
            )

        st.markdown(
            "#### Keywords"
        )

        keywords = parsed_video.get(
            "keywords",
            [],
        )

        if keywords:

            unique_keywords = list(
                dict.fromkeys(
                    item["text"]
                    for item in keywords
                )
            )

            st.write(
                unique_keywords[:40]
            )

        else:

            st.info(
                "No keywords detected."
            )


    # -----------------------------------------------------
    # SCENES
    # -----------------------------------------------------

    with scene_tab:

        scenes = parsed_video.get(
            "scenes",
            [],
        )

        if scenes:

            for scene in scenes:

                st.markdown(
                    f"**Scene {scene['id']}**  "
                    f"{scene['start_time']} - "
                    f"{scene['end_time']}"
                )

        else:

            st.info(
                "No scenes detected."
            )


    # -----------------------------------------------------
    # ENTITIES
    # -----------------------------------------------------

    with entity_tab:

        entities = parsed_video.get(
            "named_entities",
            [],
        )

        if entities:

            unique_entities = []

            for item in entities:

                if item["name"] not in unique_entities:

                    unique_entities.append(
                        item["name"]
                    )

            st.write(
                unique_entities
            )

            st.caption(
                "These are Video Indexer entity candidates; "
                "they are not automatically treated as confirmed "
                "meeting participants."
            )

        else:

            st.info(
                "No named entities detected."
            )


    # -----------------------------------------------------
    # VIDEO TIMELINE
    # -----------------------------------------------------

    with vi_timeline_tab:

        timeline_items = build_video_timeline(
            parsed_video
        )

        if timeline_items:

            for item in timeline_items[:120]:

                icon = (
                    "🗣️"
                    if item["type"] == "Speech"
                    else "🖥️"
                )

                st.markdown(
                    f"{icon} **{item['time_label']}**  "
                    f"{item['content']}"
                )

                st.divider()

        else:

            st.info(
                "No Video Indexer timeline available."
            )


# =========================================================
# STEP 2 — TRANSCRIPT
# =========================================================

if st.session_state.transcript:

    st.divider()

    st.markdown(
        '<div class="section-title">'
        "2️⃣ Meeting Transcript & Timeline"
        "</div>",
        unsafe_allow_html=True,
    )


    with st.expander(
        "🔍 Raw Transcript",
        expanded=False,
    ):

        st.text_area(
            "Raw Transcript",
            st.session_state.raw_transcript,
            height=250,
            label_visibility="collapsed",
        )


    with st.expander(
        "✨ Clean Transcript",
        expanded=True,
    ):

        st.text_area(
            "Clean Transcript",
            st.session_state.transcript,
            height=320,
            label_visibility="collapsed",
        )


    with st.expander(
        "🕐 Speech Timeline",
        expanded=False,
    ):

        if st.session_state.segments:

            for segment in st.session_state.segments:

                st.markdown(
                    f"**{segment['start_time']} - "
                    f"{segment['end_time']}**  "
                    f"{segment['text']}"
                )

                st.divider()

        else:

            st.info(
                "No speech timestamps available."
            )


# =========================================================
# STEP 3 — ANALYSIS
# =========================================================

if st.session_state.transcript:

    st.divider()

    st.markdown(
        '<div class="section-title">'
        "3️⃣ AI Meeting Intelligence"
        "</div>",
        unsafe_allow_html=True,
    )


    if st.button(
        "🤖 Analyze Meeting",
        type="primary",
        use_container_width=True,
    ):

        try:

            with st.spinner(
                "MeetAssist-Agent is analyzing "
                "speech + video evidence..."
            ):

                st.session_state.analysis = (
                    analyze_transcript(
                        transcript=(
                            st.session_state.transcript
                        ),
                        video_context=(
                            st.session_state.video_context
                        ),
                    )
                )

            st.success(
                "✅ Multimodal meeting analysis completed!"
            )

        except Exception as error:

            st.error(
                f"❌ AI analysis failed:\n\n{error}"
            )


# =========================================================
# STEP 4 — DASHBOARD
# =========================================================

if st.session_state.analysis:

    report = st.session_state.analysis

    st.divider()

    st.markdown(
        '<div class="section-title">'
        "📊 Meeting Intelligence Dashboard"
        "</div>",
        unsafe_allow_html=True,
    )


    iq_text = extract_meeting_iq(
        report
    )

    decisions_count = extract_metric(
        iq_text,
        "Decisions",
    )

    actions_count = extract_metric(
        iq_text,
        "Action items",
    )

    unassigned_count = extract_metric(
        iq_text,
        "Unassigned tasks",
    )

    questions_count = extract_metric(
        iq_text,
        "Open questions",
    )

    risks_count = extract_metric(
        iq_text,
        "Risks",
    )

    unresolved_count = extract_metric(
        iq_text,
        "Unresolved issues",
    )


    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "🎯 Decisions",
            decisions_count,
        )

    with c2:

        st.metric(
            "✅ Action Items",
            actions_count,
        )

    with c3:

        st.metric(
            "⚠️ Risks",
            risks_count,
        )


    c4, c5, c6 = st.columns(3)

    with c4:

        st.metric(
            "👤 Unassigned Tasks",
            unassigned_count,
        )

    with c5:

        st.metric(
            "❓ Open Questions",
            questions_count,
        )

    with c6:

        st.metric(
            "🔴 Unresolved Issues",
            unresolved_count,
        )


    st.divider()


    (
        summary_tab,
        actions_tab,
        decisions_tab,
        risks_tab,
        questions_tab,
    ) = st.tabs(
        [
            "📝 Summary",
            "✅ Action Items",
            "🎯 Decisions",
            "⚠️ Risk Radar",
            "❓ Open Questions",
        ]
    )


    with summary_tab:

        st.markdown(
            "### Summary"
        )

        summary = extract_section(
            report,
            "SUMMARY",
        )

        if summary:

            st.markdown(summary)

        else:

            st.info(
                "No summary found."
            )


        st.markdown(
            "### Key Discussion Points"
        )

        discussion = extract_section(
            report,
            "KEY DISCUSSION POINTS",
        )

        if discussion:

            st.markdown(
                discussion
            )


    with actions_tab:

        st.markdown(
            "### ✅ Action Items"
        )

        section = extract_section(
            report,
            "ACTION ITEMS",
        )

        if section:

            st.markdown(section)


    with decisions_tab:

        st.markdown(
            "### 🎯 Decisions"
        )

        section = extract_section(
            report,
            "DECISIONS",
        )

        if section:

            st.markdown(section)


        st.markdown(
            "### 🔄 Decision Changes"
        )

        section = extract_section(
            report,
            "DECISION CHANGES",
        )

        if section:

            st.markdown(section)


    with risks_tab:

        st.markdown(
            "### ⚠️ Risk Radar"
        )

        section = extract_section(
            report,
            "RISK RADAR",
        )

        if section:

            st.markdown(section)


    with questions_tab:

        st.markdown(
            "### ❓ Open Questions"
        )

        section = extract_section(
            report,
            "OPEN QUESTIONS",
        )

        if section:

            st.markdown(section)


    # =====================================================
    # VIDEO EVIDENCE FROM AGENT
    # =====================================================

    video_evidence = extract_section(
        report,
        "VIDEO EVIDENCE",
    )

    if video_evidence:

        st.divider()

        with st.expander(
            "🎥 AI Video Evidence",
            expanded=True,
        ):

            st.markdown(
                video_evidence
            )


    # =====================================================
    # FULL REPORT
    # =====================================================

    with st.expander(
        "🔧 View Full AI Report",
        expanded=False,
    ):

        st.markdown(
            report
        )


    # =====================================================
    # REPORT PDF
    # =====================================================

    report_pdf = markdown_to_pdf(
        report,
        "MeetAssist AI - Meeting Intelligence Report",
    )

    st.download_button(
        "⬇️ Download Meeting Report PDF",
        data=report_pdf,
        file_name="MeetAssist_Meeting_Report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


# =========================================================
# STEP 5 — SMART MOM
# =========================================================

if (
    st.session_state.transcript
    and st.session_state.analysis
):

    st.divider()

    st.markdown(
        '<div class="section-title">'
        "5️⃣ Smart Timeline Minutes of Meeting"
        "</div>",
        unsafe_allow_html=True,
    )

    st.write(
        "Generate chronological MoM using speech timestamps "
        "and Video Indexer visual evidence."
    )


    if st.button(
        "📄 Generate Smart MoM",
        type="primary",
        use_container_width=True,
    ):

        try:

            if not st.session_state.segments:

                st.error(
                    "Speech timeline is unavailable."
                )

            else:

                audio_timeline = (
                    build_audio_timeline(
                        st.session_state.segments
                    )
                )

                with st.spinner(
                    "MeetAssist is generating Smart MoM..."
                ):

                    st.session_state.mom = (
                        generate_mom(
                            transcript=(
                                st.session_state.transcript
                            ),
                            analysis=(
                                st.session_state.analysis
                            ),
                            timeline=(
                                audio_timeline
                            ),
                            meeting_date=(
                                meeting_date.strftime(
                                    "%d %B %Y"
                                )
                            ),
                            meeting_time=(
                                meeting_time.strftime(
                                    "%I:%M %p"
                                )
                            ),
                            video_context=(
                                st.session_state.video_context
                            ),
                        )
                    )

                st.success(
                    "✅ Smart multimodal MoM generated!"
                )

        except Exception as error:

            st.error(
                f"❌ MoM generation failed:\n\n{error}"
            )


# =========================================================
# SHOW MOM
# =========================================================

if st.session_state.mom:

    st.divider()

    st.markdown(
        "## 📄 Smart Minutes of Meeting"
    )

    st.markdown(
        st.session_state.mom
    )

    mom_pdf = markdown_to_pdf(
        st.session_state.mom,
        "MeetAssist AI - Smart Minutes of Meeting",
    )

    st.download_button(
        "⬇️ Download Smart MoM PDF",
        data=mom_pdf,
        file_name="MeetAssist_Smart_MoM.pdf",
        mime="application/pdf",
        use_container_width=True,
    )


# =========================================================
# STEP 6 — ASK MY MEETING
# =========================================================

if st.session_state.transcript:

    st.divider()

    st.markdown(
        '<div class="section-title">'
        "6️⃣ Ask My Meeting"
        "</div>",
        unsafe_allow_html=True,
    )

    st.write(
        "Ask questions about what was said or what "
        "was visible in the meeting."
    )


    question = st.text_input(
        "Your question",
        placeholder=(
            "e.g. What did the screen show when "
            "the launch decision was made?"
        ),
    )


    if st.button(
        "💬 Ask Meeting",
        use_container_width=True,
    ):

        if not question.strip():

            st.warning(
                "Please enter a question first."
            )

        else:

            try:

                with st.spinner(
                    "MeetAssist is checking speech "
                    "and video evidence..."
                ):

                    answer = ask_meeting_question(
                        transcript=(
                            st.session_state.transcript
                        ),
                        question=question,
                        video_context=(
                            st.session_state.video_context
                        ),
                    )

                st.success(
                    "✅ Answer generated"
                )

                st.markdown(
                    "### Answer"
                )

                st.markdown(
                    answer
                )

            except Exception as error:

                st.error(
                    f"❌ Question failed:\n\n{error}"
                )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "⚠️ MeetAssist AI is an AI-generated meeting assistant. "
    "Verify important decisions, owners, deadlines, "
    "visual evidence and timestamps against the original "
    "recording."
)
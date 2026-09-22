# 🎙️ MeetAssist AI

**AI-103 Group Project — Chitkara University**

MeetAssist AI is an AI-powered meeting assistant that transforms meeting audio and video into useful, structured meeting intelligence. It combines speech transcription with generative AI analysis to help users quickly understand what happened in a meeting and what needs to happen next.

## 👥 Team Members

- Kashak Thakur
- Harshita Narula
- Jasmine Kaur
- Bhavya Sharma
- Jatin Ratra

## 🎯 Problem Statement

Meeting recordings can contain important discussions, decisions, and assigned tasks, but manually listening to long recordings and preparing notes is time-consuming.

MeetAssist AI addresses this problem by automatically processing meeting recordings and generating a transcript together with concise, actionable meeting insights.

## 💡 Solution Overview

The application provides a simple web interface where a user can:

1. Sign in using Microsoft authentication.
2. Upload an audio or video meeting recording.
3. Generate a meeting transcript using AI speech capabilities.
4. Send the transcript for AI-powered analysis.
5. View structured meeting information such as:
   - Meeting summary
   - Key decisions
   - Action items
   - Important insights

For video inputs, the application also provides video-intelligence functionality.

## 🏗️ Solution Architecture

```text
                    ┌──────────────────┐
                    │       User       │
                    └────────┬─────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   MeetAssist AI     │
                  │    Streamlit UI     │
                  └──────────┬──────────┘
                             │
                       Audio / Video
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
      ┌───────────────┐             ┌────────────────┐
      │ Azure AI      │             │ Video          │
      │ Speech        │             │ Intelligence   │
      │ Transcription │             │ Processing     │
      └───────┬───────┘             └───────┬────────┘
              │                             │
              └──────────────┬──────────────┘
                             ▼
                    ┌────────────────┐
                    │   Transcript   │
                    └───────┬────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Microsoft        │
                  │ Foundry Agent    │
                  └────────┬─────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │ AI Meeting Intelligence  │
              │                          │
              │ • Summary                │
              │ • Decisions              │
              │ • Action Items           │
              │ • Insights               │
              └────────────┬─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Final Output │
                    └──────────────┘
```

## 🤖 AI-103 Concepts Applied

| AI-103 Concept | Application in MeetAssist AI |
|---|---|
| Generative AI | Generates meeting summaries and structured insights |
| Speech AI | Converts spoken meeting content into text |
| Text Analysis | Processes and interprets the generated transcript |
| AI Agents | Microsoft Foundry agent performs meeting analysis |
| Multimodal / Video Processing | Video inputs can be processed for additional intelligence |
| Responsible AI | Human review, privacy, security and reliability considerations |

## ☁️ Microsoft Azure Technologies

- **Azure AI Speech** — speech-to-text transcription
- **Microsoft Foundry** — project/agent-based generative AI processing
- **Microsoft Entra ID / Microsoft authentication** — secure user sign-in
- Azure-based AI resources configured through environment variables

> Exact resource names, endpoints, keys and secrets are intentionally not included in this repository.

## 🛠️ Technology Stack

- Python
- Streamlit
- Azure AI Speech
- Microsoft Foundry
- Azure Identity / Microsoft authentication
- HTML/CSS
- Git & GitHub

## 📁 Project Structure

```text
MeetAssist-AI/
│
├── app.py
├── foundry.py
├── speech.py
├── video_indexer.py
├── test_agent.py
├── requirements.txt
├── .gitignore
│
├── .streamlit/
│   └── config.toml
│
├── hero_meeting.jpeg
└── hero_meeting.svg
```

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/harshita-narula/MeetAssist-AI.git
cd MeetAssist-AI
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure credentials

Create the required environment/configuration values locally.

Do **not** commit API keys, passwords, access tokens, client secrets, Azure connection strings, `.env`, or production `secrets.toml`.

Use environment variables or local Streamlit secrets instead.

### 5. Run the application

```bash
streamlit run app.py
```

## 🧪 Testing

The end-to-end workflow should be tested using representative audio and video meeting recordings.

```text
Microsoft Login
      ↓
File Upload
      ↓
Audio / Video Detection
      ↓
Transcription
      ↓
Transcript Display
      ↓
AI Analysis
      ↓
Summary / Decisions / Action Items
```

Results can be affected by background noise, poor microphone quality, multiple speakers talking simultaneously, accents or unclear speech, very long recordings, and ambiguous conversations.

AI-generated meeting information should be reviewed by a human before being treated as an authoritative record.

## 🔐 Responsible AI

- **Privacy:** Meeting content should only be processed for its intended purpose.
- **Security:** Credentials and secrets are kept outside the public repository.
- **Transparency:** AI-generated summaries and action items should be identified as AI-generated.
- **Human oversight:** Users should verify important decisions and action items.
- **Reliability:** Transcription and generation errors are possible and should be reviewed.
- **Data minimization:** Avoid exposing or storing meeting information unnecessarily.

## ⚠️ Known Limitations

- Transcription quality depends on audio quality and speech clarity.
- Multiple speakers can make interpretation more difficult.
- AI-generated summaries may omit or misinterpret context.
- The current prototype primarily processes uploaded recordings rather than providing continuous real-time meeting assistance.
- Video intelligence capabilities depend on the supported input and configured Azure services.

## 🚀 Future Scope

- Real-time meeting transcription
- Speaker identification
- Multilingual meeting support
- Microsoft Teams integration
- Calendar integration
- Searchable meeting history
- Automated follow-up reminders
- More advanced meeting analytics
- Role-based access and enterprise deployment
- Improved evaluation and monitoring of AI-generated outputs

## 📚 Third-Party Resources

The project uses Microsoft Azure AI services and open-source Python packages. Their respective documentation and licenses should be acknowledged according to their terms of use.

## 🎓 Academic Context

This project was developed as part of the **AI-103 Group Project at Chitkara University**. The project focuses on applying AI-103 concepts to a practical problem through a working AI prototype.

## 📌 Project Status

**Working Prototype / Proof of Concept**

The core workflow — authentication, meeting upload, transcription and AI-powered meeting analysis — is implemented for demonstration and further evaluation.

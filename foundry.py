import os
from functools import lru_cache

from dotenv import load_dotenv
from azure.identity import InteractiveBrowserCredential
from azure.ai.projects import AIProjectClient


# =========================================================
# LOAD ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# CONFIGURATION
# =========================================================

PROJECT_ENDPOINT = os.getenv(
    "FOUNDRY_PROJECT_ENDPOINT"
)

AGENT_NAME = os.getenv(
    "FOUNDRY_AGENT_NAME",
    "MeetAssist-Agent",
)

TENANT_ID = os.getenv(
    "AZURE_TENANT_ID"
)


# =========================================================
# VALIDATION
# =========================================================

if not PROJECT_ENDPOINT:

    raise ValueError(
        "FOUNDRY_PROJECT_ENDPOINT is missing in .env"
    )

if not TENANT_ID:

    raise ValueError(
        "AZURE_TENANT_ID is missing in .env"
    )


# =========================================================
# CLIENT
# =========================================================

@lru_cache(maxsize=1)
def get_azure_credential():
    """Create one reusable Microsoft/Azure interactive credential.

    The UI calls this credential from the dedicated MeetAssist sign-in
    screen, so transcription/analysis actions do not unexpectedly launch
    a Microsoft sign-in window.
    """
    return InteractiveBrowserCredential(
        tenant_id=TENANT_ID
    )


def sign_in_with_microsoft():
    """Open Microsoft sign-in once and verify that authentication succeeds."""
    credential = get_azure_credential()

    # This token request is only used to complete/verify the Microsoft
    # sign-in. The AI Project SDK requests its own service token later.
    credential.get_token(
        "https://management.azure.com/.default"
    )

    return True


@lru_cache(maxsize=1)
def get_openai_client():

    credential = get_azure_credential()

    project = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential,
        allow_preview=True,
    )

    return project.get_openai_client(
        agent_name=AGENT_NAME
    )


# =========================================================
# TRANSCRIPT CLEANUP
# =========================================================

def clean_meeting_transcript(
    raw_transcript: str,
) -> str:

    if not raw_transcript.strip():

        raise ValueError(
            "Transcript is empty."
        )

    client = get_openai_client()

    prompt = f"""
You are the transcript-cleaning module of MeetAssist AI.

Clean the raw speech-to-text meeting transcript.

Correct obvious ASR mistakes only when context strongly
supports the correction.

Examples:
- lunch → launch when discussing a product launch
- repair → prepare when discussing a checklist
- calculate → check when discussing customer feedback

RULES:

1. Preserve original meaning.
2. Do not turn the transcript into a summary.
3. Do not invent information.
4. Do not invent names.
5. Do not invent owners.
6. Do not invent deadlines.
7. Do not invent decisions.
8. Preserve speaker labels.
9. If uncertain, leave the wording unchanged.
10. Return ONLY the cleaned transcript.

RAW TRANSCRIPT:

{raw_transcript}
"""

    response = client.responses.create(
        input=prompt
    )

    result = response.output_text.strip()

    if not result:

        raise RuntimeError(
            "Transcript cleanup returned empty output."
        )

    return result


# =========================================================
# MEETING ANALYSIS
# =========================================================

def analyze_transcript(
    transcript: str,
    video_context: str = "",
) -> str:

    if not transcript.strip():

        raise ValueError(
            "Transcript is empty."
        )

    client = get_openai_client()

    visual_section = ""

    if video_context.strip():

        visual_section = f"""
VIDEO INDEXER VISUAL CONTEXT:

{video_context}

IMPORTANT:
The spoken transcript is the primary source for what
was said. Video Indexer OCR, topics, labels and scenes
are supporting visual evidence.

Do not treat low-confidence named-entity detections as
confirmed participant identities.
"""

    prompt = f"""
You are MeetAssist-Agent, an AI meeting intelligence system.

Analyze the meeting transcript and any supporting
Video Indexer visual evidence.

Return:

## MEETING IQ

- Decisions:
- Action items:
- Unassigned tasks:
- Open questions:
- Risks:
- Unresolved issues:

## SUMMARY

## KEY DISCUSSION POINTS

## DECISIONS

| Decision | Context | Owner | Status |
|---|---|---|---|

## ACTION ITEMS

| Task | Owner | Deadline | Status |
|---|---|---|---|

## RISK RADAR

| Risk / Issue | Evidence | Follow-up |
|---|---|---|

## OPEN QUESTIONS

## DECISION CHANGES

| Earlier | Updated | Change |
|---|---|---|

## VIDEO EVIDENCE

Only mention visual evidence when it materially
supports the meeting interpretation.

Examples:

- Screen text supporting a decision
- Screen text showing an action item
- A visual scene associated with an important topic
- OCR text that clarifies terminology

IMPORTANT RULES:

1. Never invent names.
2. Never invent owners.
3. Never invent deadlines.
4. Never invent decisions.
5. Never treat a suggestion as a final decision.
6. Use "Not specified" when information is missing.
7. Risks must be grounded in the meeting.
8. Be conservative with ambiguous speech.
9. Do not treat every Video Indexer named entity as a person
   who actually attended the meeting.
10. Distinguish spoken evidence from visual evidence.

MEETING TRANSCRIPT:

{transcript}

{visual_section}
"""

    response = client.responses.create(
        input=prompt
    )

    result = response.output_text.strip()

    if not result:

        raise RuntimeError(
            "Meeting analysis returned empty output."
        )

    return result


# =========================================================
# ASK MY MEETING
# =========================================================

def ask_meeting_question(
    transcript: str,
    question: str,
    video_context: str = "",
) -> str:

    if not transcript.strip():

        raise ValueError(
            "Transcript is empty."
        )

    if not question.strip():

        raise ValueError(
            "Question is empty."
        )

    client = get_openai_client()

    visual_section = ""

    if video_context.strip():

        visual_section = f"""
SUPPORTING VIDEO INDEXER CONTEXT:

{video_context}

Use visual information only when it is directly relevant.
"""

    prompt = f"""
You are MeetAssist-Agent.

Answer the user's question using ONLY the current meeting
transcript and supporting Video Indexer context.

RULES:

- Do not use outside knowledge.
- Do not invent facts.
- Do not invent names.
- Do not invent owners.
- Do not invent deadlines.
- If the answer is unavailable, say:
  "Not specified in the meeting."
- If evidence is ambiguous, explicitly say so.
- Give the direct answer first.
- When useful, mention the timestamp or visual evidence.

MEETING TRANSCRIPT:

{transcript}

{visual_section}

USER QUESTION:

{question}
"""

    response = client.responses.create(
        input=prompt
    )

    result = response.output_text.strip()

    if not result:

        raise RuntimeError(
            "Meeting Q&A returned empty output."
        )

    return result


# =========================================================
# SMART TIMELINE MOM
# =========================================================

def generate_mom(
    transcript: str,
    analysis: str,
    timeline: str,
    meeting_date: str,
    meeting_time: str,
    video_context: str = "",
) -> str:

    if not transcript.strip():

        raise ValueError(
            "Transcript is empty."
        )

    if not timeline.strip():

        raise ValueError(
            "Timeline is empty."
        )

    client = get_openai_client()

    visual_section = ""

    if video_context.strip():

        visual_section = f"""
VIDEO INDEXER CONTEXT:

{video_context}

Use this only as supporting evidence.
When visual evidence conflicts with spoken content,
do not silently choose one; describe the ambiguity.
"""

    prompt = f"""
You are the Smart Minutes of Meeting module of MeetAssist AI.

Create professional chronological Minutes of Meeting.

The key purpose is:

1. What happened
2. When it happened
3. What was decided
4. What actions were assigned
5. What was shown on screen
6. What remains unresolved
7. What the final meeting crux was

Use exact timestamps from the timestamped source.

MEETING DATE:
{meeting_date}

MEETING START TIME:
{meeting_time}

OUTPUT:

# MINUTES OF MEETING

## Meeting Details

- Date: {meeting_date}
- Start Time: {meeting_time}
- Participants: Only participants clearly identified
- Meeting Objective:

## MEETING TIMELINE

For meaningful events:

**00:00 - 00:08**
Event description.

**00:08 - 00:20**
Discussion / decision.

Include screen evidence when useful:

**00:20 - 00:29**
Decision confirmed.
Screen evidence: "Decision Made / Launch Date: Monday."

Do not include every sentence.

## MEETING CRUX

### Main Objective

### Key Decisions

- ...

### Critical Action Items

| Time | Task | Owner | Deadline |
|---|---|---|---|

### Risks / Blockers

| Time | Risk / Blocker | Evidence |
|---|---|---|

### Open Issues

- ...

### Decision Changes

| Time | Earlier Decision | Updated Decision | Reason |
|---|---|---|---|

### Next Steps

- ...

## FINAL MEETING CRUX

Write 3–5 concise sentences.

IMPORTANT RULES:

1. Never invent timestamps.
2. Never invent participants.
3. Never invent owners.
4. Never invent deadlines.
5. Never invent decisions.
6. Use "Not specified" when information is missing.
7. Preserve chronology.
8. Spoken transcript is primary evidence.
9. OCR is supporting visual evidence.
10. Do not treat noisy named-entity detections as confirmed names.
11. Mention visual evidence only when it materially helps.
12. Clearly flag ambiguity.

TIMESTAMPED SPOKEN TRANSCRIPT:

{timeline}

CLEAN TRANSCRIPT:

{transcript}

MEETING ANALYSIS:

{analysis}

{visual_section}
"""

    response = client.responses.create(
        input=prompt
    )

    result = response.output_text.strip()

    if not result:

        raise RuntimeError(
            "Smart MoM returned empty output."
        )

    return result
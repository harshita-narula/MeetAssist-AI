import json
import re
from typing import Any, Dict, List


# =========================================================
# TIME HELPERS
# =========================================================

def time_to_seconds(value: str) -> float:
    """
    Convert Video Indexer time format into seconds.

    Examples:
        0:00:05.25
        0:01:10
        00:00:05.250
    """

    if not value:
        return 0.0

    value = str(value).strip()

    parts = value.split(":")

    try:
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])

            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])

            return (
                minutes * 60
                + seconds
            )

        return float(value)

    except (ValueError, TypeError):
        return 0.0


def format_time(seconds: float) -> str:
    """
    Convert seconds to HH:MM:SS / MM:SS.
    """

    total = max(0, int(seconds))

    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


# =========================================================
# GENERIC HELPERS
# =========================================================

def first_instance(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return first available timing instance.
    """

    instances = item.get("instances") or []

    if instances and isinstance(instances[0], dict):
        return instances[0]

    return {}


def get_instance_range(item: Dict[str, Any]):
    """
    Return start/end values from a Video Indexer insight item.
    """

    instance = first_instance(item)

    start_raw = (
        instance.get("adjustedStart")
        or instance.get("start")
        or item.get("adjustedStart")
        or item.get("start")
        or "0:00:00"
    )

    end_raw = (
        instance.get("adjustedEnd")
        or instance.get("end")
        or item.get("adjustedEnd")
        or item.get("end")
        or start_raw
    )

    start = time_to_seconds(start_raw)
    end = time_to_seconds(end_raw)

    return start, end


def safe_list(value):
    return value if isinstance(value, list) else []


# =========================================================
# LOAD INSIGHTS JSON
# =========================================================

def load_video_indexer_json(
    uploaded_bytes: bytes,
) -> Dict[str, Any]:
    """
    Load the actual Insights JSON downloaded from
    Azure AI Video Indexer.
    """

    try:

        text = uploaded_bytes.decode(
            "utf-8-sig"
        )

        data = json.loads(text)

    except UnicodeDecodeError:

        try:

            text = uploaded_bytes.decode(
                "utf-16"
            )

            data = json.loads(text)

        except Exception as error:

            raise ValueError(
                "The uploaded file is not valid JSON."
            ) from error

    except json.JSONDecodeError as error:

        raise ValueError(
            "The uploaded file is not valid "
            "Azure AI Video Indexer Insights JSON."
        ) from error

    if not isinstance(data, dict):

        raise ValueError(
            "Video Indexer JSON must contain an object."
        )

    return data


# =========================================================
# GET VIDEO OBJECT
# =========================================================

def get_video_object(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Video Indexer exports can contain a videos[] wrapper.
    """

    videos = data.get("videos")

    if (
        isinstance(videos, list)
        and videos
        and isinstance(videos[0], dict)
    ):

        return videos[0]

    return data


# =========================================================
# GET INSIGHTS OBJECT
# =========================================================

def get_insights(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return the Video Indexer insights object.
    """

    video = get_video_object(data)

    insights = video.get("insights")

    if isinstance(insights, dict):

        return insights

    if isinstance(data.get("insights"), dict):

        return data["insights"]

    return {}


# =========================================================
# TRANSCRIPT
# =========================================================

def extract_transcript(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract transcript lines with timestamps.
    """

    insights = get_insights(data)

    transcript = safe_list(
        insights.get("transcript")
    )

    results = []

    for item in transcript:

        if not isinstance(item, dict):
            continue

        text = str(
            item.get("text", "")
        ).strip()

        if not text:
            continue

        start, end = get_instance_range(item)

        results.append(
            {
                "text": text,
                "speaker_id": item.get(
                    "speakerId"
                ),
                "language": item.get(
                    "language"
                ),
                "confidence": item.get(
                    "confidence"
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
            }
        )

    results.sort(
        key=lambda x: x["start"]
    )

    return results


# =========================================================
# OCR
# =========================================================

def extract_ocr(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract OCR / on-screen text.
    """

    insights = get_insights(data)

    ocr = safe_list(
        insights.get("ocr")
    )

    results = []

    for item in ocr:

        if not isinstance(item, dict):
            continue

        text = str(
            item.get("text", "")
        ).strip()

        if not text:
            continue

        start, end = get_instance_range(item)

        # Skip simple player clock overlays
        # such as 00:00, 00:10, 00:20.
        if re.fullmatch(
            r"\d{2}:\d{2}",
            text
        ):
            continue

        results.append(
            {
                "text": text,
                "confidence": item.get(
                    "confidence"
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
            }
        )

    results.sort(
        key=lambda x: (
            x["start"],
            x["text"].lower(),
        )
    )

    # Remove exact duplicates
    unique = []
    seen = set()

    for item in results:

        key = (
            item["text"].lower(),
            round(item["start"], 2),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# =========================================================
# KEYWORDS
# =========================================================

def extract_keywords(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:

    insights = get_insights(data)

    keywords = safe_list(
        insights.get("keywords")
    )

    results = []

    for item in keywords:

        if not isinstance(item, dict):
            continue

        text = str(
            item.get("text", "")
        ).strip()

        if not text:
            continue

        start, end = get_instance_range(item)

        results.append(
            {
                "text": text,
                "confidence": item.get(
                    "confidence"
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
            }
        )

    results.sort(
        key=lambda x: x.get(
            "confidence",
            0
        ) or 0,
        reverse=True,
    )

    return results


# =========================================================
# TOPICS
# =========================================================

def extract_topics(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:

    insights = get_insights(data)

    topics = safe_list(
        insights.get("topics")
    )

    results = []

    for item in topics:

        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name", "")
        ).strip()

        if not name:
            continue

        start, end = get_instance_range(item)

        results.append(
            {
                "name": name,
                "confidence": item.get(
                    "confidence"
                ),
                "reference_id": item.get(
                    "referenceId"
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
            }
        )

    return results


# =========================================================
# LABELS
# =========================================================

def extract_labels(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:

    insights = get_insights(data)

    labels = safe_list(
        insights.get("labels")
    )

    results = []

    for item in labels:

        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name")
            or item.get("text")
            or ""
        ).strip()

        if not name:
            continue

        start, end = get_instance_range(item)

        results.append(
            {
                "name": name,
                "confidence": item.get(
                    "confidence"
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
            }
        )

    return results


# =========================================================
# SCENES
# =========================================================

def extract_scenes(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:

    insights = get_insights(data)

    scenes = safe_list(
        insights.get("scenes")
    )

    results = []

    for index, scene in enumerate(
        scenes,
        start=1,
    ):

        if not isinstance(scene, dict):
            continue

        start, end = get_instance_range(
            scene
        )

        results.append(
            {
                "id": scene.get(
                    "id",
                    index
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
                "shots": safe_list(
                    scene.get("shots")
                ),
            }
        )

    results.sort(
        key=lambda x: x["start"]
    )

    return results


# =========================================================
# NAMED ENTITIES
# =========================================================

def extract_named_entities(
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:

    insights = get_insights(data)

    entities = (
        safe_list(
            insights.get(
                "namedEntities"
            )
        )
        or safe_list(
            insights.get(
                "namedPeople"
            )
        )
    )

    results = []

    for item in entities:

        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name")
            or item.get("text")
            or ""
        ).strip()

        if not name:
            continue

        start, end = get_instance_range(item)

        results.append(
            {
                "name": name,
                "confidence": item.get(
                    "confidence"
                ),
                "source": item.get(
                    "instanceSource"
                ),
                "start": start,
                "end": end,
                "start_time": format_time(start),
                "end_time": format_time(end),
            }
        )

    results.sort(
        key=lambda x: (
            x["start"],
            -(x.get("confidence") or 0),
        )
    )

    return results


# =========================================================
# VIDEO METADATA
# =========================================================

def extract_metadata(
    data: Dict[str, Any],
) -> Dict[str, Any]:

    video = get_video_object(data)

    return {
        "name": video.get(
            "name",
            "Not specified",
        ),
        "duration": video.get(
            "duration",
            "Not specified",
        ),
        "duration_seconds": video.get(
            "durationInSeconds"
        ),
        "state": video.get(
            "state",
            "Not specified",
        ),
        "processing_progress": video.get(
            "processingProgress",
            "Not specified",
        ),
        "privacy": video.get(
            "privacyMode",
            "Not specified",
        ),
        "source_language": get_insights(
            data
        ).get(
            "sourceLanguage",
            "Not specified",
        ),
    }


# =========================================================
# MAIN PARSER
# =========================================================

def parse_video_indexer(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Parse all useful Video Indexer insights into
    a compact structure for Streamlit + Foundry.
    """

    return {
        "metadata": extract_metadata(
            data
        ),
        "transcript": extract_transcript(
            data
        ),
        "ocr": extract_ocr(
            data
        ),
        "keywords": extract_keywords(
            data
        ),
        "topics": extract_topics(
            data
        ),
        "labels": extract_labels(
            data
        ),
        "scenes": extract_scenes(
            data
        ),
        "named_entities": extract_named_entities(
            data
        ),
    }


# =========================================================
# BUILD LLM CONTEXT
# =========================================================

def build_video_context(
    parsed: Dict[str, Any],
) -> str:
    """
    Convert Video Indexer insights into a compact context
    block that can be passed to the Foundry agent.

    The transcript remains the primary spoken source.
    Visual evidence is used as supporting evidence.
    """

    parts = []

    metadata = parsed.get(
        "metadata",
        {},
    )

    parts.append(
        "VIDEO METADATA:\n"
        f"Name: {metadata.get('name')}\n"
        f"Duration: {metadata.get('duration')}\n"
        f"Source language: "
        f"{metadata.get('source_language')}\n"
    )

    # -----------------------------------------------------
    # OCR
    # -----------------------------------------------------

    ocr = parsed.get(
        "ocr",
        [],
    )

    if ocr:

        parts.append(
            "ON-SCREEN TEXT / OCR:"
        )

        # Limit context size
        for item in ocr[:80]:

            parts.append(
                f"- "
                f"[{item['start_time']}-"
                f"{item['end_time']}] "
                f"{item['text']}"
            )

    # -----------------------------------------------------
    # TOPICS
    # -----------------------------------------------------

    topics = parsed.get(
        "topics",
        [],
    )

    if topics:

        unique_topics = []

        seen = set()

        for item in topics:

            name = item["name"]

            if name.lower() in seen:
                continue

            seen.add(
                name.lower()
            )

            unique_topics.append(
                name
            )

        parts.append(
            "VIDEO INDEXER TOPICS:\n"
            + "\n".join(
                f"- {x}"
                for x in unique_topics[:20]
            )
        )

    # -----------------------------------------------------
    # KEYWORDS
    # -----------------------------------------------------

    keywords = parsed.get(
        "keywords",
        [],
    )

    if keywords:

        unique_keywords = []

        seen = set()

        for item in keywords:

            word = item["text"]

            if word.lower() in seen:
                continue

            seen.add(
                word.lower()
            )

            unique_keywords.append(
                word
            )

        parts.append(
            "VIDEO INDEXER KEYWORDS:\n"
            + "\n".join(
                f"- {x}"
                for x in unique_keywords[:30]
            )
        )

    # -----------------------------------------------------
    # LABELS
    # -----------------------------------------------------

    labels = parsed.get(
        "labels",
        [],
    )

    if labels:

        unique_labels = []

        seen = set()

        for item in labels:

            name = item["name"]

            if name.lower() in seen:
                continue

            seen.add(
                name.lower()
            )

            unique_labels.append(
                name
            )

        parts.append(
            "VISUAL LABELS:\n"
            + "\n".join(
                f"- {x}"
                for x in unique_labels[:30]
            )
        )

    # -----------------------------------------------------
    # SCENES
    # -----------------------------------------------------

    scenes = parsed.get(
        "scenes",
        [],
    )

    if scenes:

        parts.append(
            "VIDEO SCENES:"
        )

        for scene in scenes[:30]:

            parts.append(
                f"- Scene {scene['id']}: "
                f"{scene['start_time']} - "
                f"{scene['end_time']}"
            )

    # -----------------------------------------------------
    # ENTITIES
    # -----------------------------------------------------

    entities = parsed.get(
        "named_entities",
        [],
    )

    if entities:

        unique_entities = []

        seen = set()

        for item in entities:

            name = item["name"]

            if name.lower() in seen:
                continue

            seen.add(
                name.lower()
            )

            unique_entities.append(
                name
            )

        parts.append(
            "DETECTED NAMED ENTITY CANDIDATES:\n"
            + "\n".join(
                f"- {x}"
                for x in unique_entities[:30]
            )
        )

    return "\n\n".join(parts)


# =========================================================
# TIMELINE FOR UI
# =========================================================

def build_video_timeline(
    parsed: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Merge OCR and transcript observations into
    a simple chronological timeline.
    """

    timeline = []

    for item in parsed.get(
        "transcript",
        [],
    ):

        timeline.append(
            {
                "time": item["start"],
                "time_label": (
                    f"{item['start_time']} - "
                    f"{item['end_time']}"
                ),
                "type": "Speech",
                "content": item["text"],
            }
        )

    for item in parsed.get(
        "ocr",
        [],
    ):

        timeline.append(
            {
                "time": item["start"],
                "time_label": (
                    f"{item['start_time']} - "
                    f"{item['end_time']}"
                ),
                "type": "Screen",
                "content": item["text"],
            }
        )

    timeline.sort(
        key=lambda x: x["time"]
    )

    return timeline
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import dateparser

@dataclass
class Intent:
    kind: str
    raw: str
    topic: str = ""
    angle: str = ""
    assignee: str = ""
    deadline: str = ""
    status: str = ""
    url: str = ""
    feedback: str = ""

def clean_text(text: str) -> str:
    text = re.sub(r"<@[A-Z0-9]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip(" .:-")

def _strip_fields(value: str) -> str:
    value = re.split(
        r"\b(?:angle|context|assigned to|assign to|deadline|due date|due)\b\s*[:-]?",
        value,
        flags=re.I,
    )[0]
    return value.strip(" .:-")

def _extract_angle(text: str) -> str:
    match = re.search(
        r"\b(?:angle|context)\s*[:-]\s*(.+?)(?=\b(?:assigned to|assign to|deadline|due date|due)\b|$)",
        text,
        flags=re.I,
    )
    return match.group(1).strip(" .") if match else ""

def _extract_assignee(text: str) -> str:
    match = re.search(
        r"\b(?:assigned to|assign to)\s+(.+?)(?=\b(?:deadline|due date|due|angle|context)\b|$)",
        text,
        flags=re.I,
    )
    return match.group(1).strip(" .") if match else ""

def _extract_deadline(text: str) -> str:
    match = re.search(
        r"\b(?:deadline|due date|due|by)\s*[:-]?\s*([^.;\n]+)",
        text,
        flags=re.I,
    )
    if not match:
        return ""
    parsed = dateparser.parse(
        match.group(1).strip(),
        settings={
            "DATE_ORDER": "DMY",
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    return parsed.strftime("%d/%m/%Y") if parsed else ""

def _extract_url(text: str) -> str:
    match = re.search(r"https?://[^\s)>]+", text)
    if not match:
        return ""
    url = match.group(0).rstrip(".,")
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""

def _topic_after(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.I)
    return _strip_fields(match.group(1)) if match else ""

def parse_message(message: str) -> Intent:
    text = clean_text(message)
    lower = text.lower()
    
    if "help" in lower or "commands" in lower:
        return Intent(kind="help", raw=message)
    
    if "list" in lower and ("tasks" in lower or "todos" in lower):
        return Intent(kind="list_tasks", raw=message)
    
    if any(k in lower for k in ["add task", "new task", "create task"]):
        topic = _topic_after(text, r"\b(?:add task|new task|create task)\b\s*[:-]?\s*(.+)")
        return Intent(
            kind="add_task",
            raw=message,
            topic=topic or text,
            angle=_extract_angle(text),
            assignee=_extract_assignee(text),
            deadline=_extract_deadline(text),
        )
        
    return Intent(kind="unknown", raw=message)

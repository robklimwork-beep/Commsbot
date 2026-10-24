# Commsbot 
import textwrap
import zipfile

PROJECT = "commsbot"

FILES = {
    ".gitignore": r"""
.env
__pycache__/
*.py[cod]
data/
.venv/
""",

    "requirements.txt": r"""
fastapi==0.115.6
uvicorn[standard]==0.34.0
slack-bolt==1.22.0
google-api-python-client==2.159.0
google-auth==2.37.0
dateparser==1.2.0
python-dotenv==1.0.1
""",

    "runtime.txt": r"""
python-3.11.11
""",

    "Procfile": r"""
web: uvicorn app.main:api --host 0.0.0.0 --port $PORT
""",

    "render.yaml": r"""
services:
  - type: web
    name: commsbot
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:api --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    autoDeploy: true
""",

    ".env.example": r"""
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret

# Google Sheets
GOOGLE_SHEETS_SPREADSHEET_ID=14wJzqgt6X7W0FSdGpA0aG5UavbXy1_ykiZq-z11qWpc

# Use ONE of the following:
# 1. Entire service-account JSON on one line:
GOOGLE_SERVICE_ACCOUNT_JSON=

# 2. Recommended for Render: base64-encoded service-account JSON:
GOOGLE_SERVICE_ACCOUNT_JSON_B64=

# Slack channel IDs, not channel names.
CONTENT_WRITERS_CHANNEL_ID=
REVIEW_GROUP_CHANNEL_ID=
GENERAL_COMMS_CHANNEL_ID=

# Slack member IDs to tag when work is ready for review.
# Separate multiple IDs with commas.
COORDINATOR_SLACK_USER_IDS=

# Map Slack user IDs to active reviewer initials.
# Only LD and VAF are active. TH and CR are inactive.
REVIEWER_SLACK_MAP_JSON={"U_LISA_SLACK_ID":"LD","U_VICTORIA_SLACK_ID":"VAF"}

# Optional: use exact tab names if they differ from defaults.
BLOG_SHEET_NAME=Blog
BLOG_TOPICS_SHEET_NAME=Blog Topics to be Scheduled
MASTER_TRACKER_SHEET_NAME=Master Comms Tracker

# Date/time settings.
DEFAULT_TIMEZONE=Europe/London
DATE_OUTPUT_FORMAT=%d/%m/%Y

# Optional: map your actual sheet status labels if they differ.
# Example:
# STATUS_MAPPING_JSON={"to do":"To Do","in progress":"In Progress","in review":"In Review","approved":"Approved","scheduled":"Scheduled","sent":"Sent","published":"Published","blocked":"Blocked"}
STATUS_MAPPING_JSON={}

# Optional custom spreadsheet-header mappings.
# Only add these if CommsBot cannot find a header automatically.
# Example:
# HEADER_OVERRIDES_JSON={"Master Comms Tracker":{"task":"Task title","assigned_to":"Owner","status":"Workflow status"}}
HEADER_OVERRIDES_JSON={}
""",

    "slack-app-manifest.yaml": r"""
display_information:
  name: CommsBot
  description: Coordinates communications, blog workflows and tracker updates.
  background_color: "#2c2d30"

features:
  bot_user:
    display_name: CommsBot
    always_online: true

  slash_commands:
    - command: /comms
      description: Send a CommsBot request without mentioning the bot.
      usage_hint: "show tasks in progress"
      should_escape: false

oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - commands
      - users:read

settings:
  event_subscriptions:
    request_url: https://YOUR-RENDER-URL.onrender.com/slack/events
    bot_events:
      - app_mention

  interactivity:
    is_enabled: false

  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
""",

    "app/__init__.py": r"""
""",

    "app/config.py": r"""
import base64
import json
import os
from dataclasses import dataclass
from typing import Any


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} must contain valid JSON.") from exc


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_signing_secret: str
    spreadsheet_id: str
    google_service_account: str

    content_writers_channel_id: str
    review_group_channel_id: str
    general_comms_channel_id: str
    coordinator_ids: list[str]

    reviewer_slack_map: dict[str, str]
    status_mapping: dict[str, str]
    header_overrides: dict[str, dict[str, str]]

    blog_sheet_name: str
    blog_topics_sheet_name: str
    master_tracker_sheet_name: str

    timezone: str
    date_output_format: str

    active_reviewers: tuple[str, ...] = ("LD", "VAF")
    inactive_reviewers: tuple[str, ...] = ("TH", "CR")
    required_reviewers: tuple[str, ...] = ("LD", "VAF")

    @classmethod
    def from_env(cls) -> "Settings":
        reviewer_map = {
            str(slack_id): str(initials).upper()
            for slack_id, initials in _json_env("REVIEWER_SLACK_MAP_JSON", {}).items()
        }

        return cls(
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", "").strip(),
            slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", "").strip(),
            spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip(),
            google_service_account=(
                os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
                or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "").strip()
            ),
            content_writers_channel_id=os.getenv("CONTENT_WRITERS_CHANNEL_ID", "").strip(),
            review_group_channel_id=os.getenv("REVIEW_GROUP_CHANNEL_ID", "").strip(),
            general_comms_channel_id=os.getenv("GENERAL_COMMS_CHANNEL_ID", "").strip(),
            coordinator_ids=_csv_env("COORDINATOR_SLACK_USER_IDS"),
            reviewer_slack_map=reviewer_map,
            status_mapping={
                str(key).lower(): str(value)
                for key, value in _json_env("STATUS_MAPPING_JSON", {}).items()
            },
            header_overrides=_json_env("HEADER_OVERRIDES_JSON", {}),
            blog_sheet_name=os.getenv("BLOG_SHEET_NAME", "Blog").strip(),
            blog_topics_sheet_name=os.getenv(
                "BLOG_TOPICS_SHEET_NAME", "Blog Topics to be Scheduled"
            ).strip(),
            master_tracker_sheet_name=os.getenv(
                "MASTER_TRACKER_SHEET_NAME", "Master Comms Tracker"
            ).strip(),
            timezone=os.getenv("DEFAULT_TIMEZONE", "Europe/London").strip(),
            date_output_format=os.getenv("DATE_OUTPUT_FORMAT", "%d/%m/%Y").strip(),
        )

    def google_credentials_dict(self) -> dict:
        raw = self.google_service_account.strip()
        if not raw:
            raise RuntimeError(
                "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON_B64 is missing."
            )

        if raw.startswith("{"):
            return json.loads(raw)

        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)
        except Exception as exc:
            raise RuntimeError(
                "Google credentials must be JSON or base64-encoded JSON."
            ) from exc


HEADER_ALIASES = {
    "task": [
        "task",
        "task title",
        "title",
        "idea",
        "content",
        "campaign",
        "post",
        "topic",
    ],
    "topic": ["topic", "blog topic", "title", "advice"],
    "advice": ["advice", "topic", "blog topic", "title"],
    "angle_context": ["angle/context", "angle", "context", "angle context"],
    "angle": ["angle", "angle/context", "context", "angle context"],
    "assigned_to": [
        "assigned to",
        "assigned",
        "owner",
        "writer",
        "assignee",
        "assignedto",
    ],
    "status": ["status", "workflow status", "stage", "progress"],
    "deadline": [
        "submission deadline",
        "deadline",
        "due date",
        "due",
        "submission due date",
    ],
    "when": ["when", "date", "scheduled date", "publish date"],
    "comments": ["comments", "comment", "notes", "note", "feedback"],
    "published_url": [
        "url here once published",
        "published url",
        "url",
        "link",
        "publication url",
    ],
}
""",

    "app/parser.py": r"""
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
        r"\b(?:angle|context|assigned to|assign to|deadline|due date|due)\b\s*[:\-]?",
        value,
        flags=re.I,
    )[0]
    return value.strip(" .:-")


def _extract_angle(text: str) -> str:
    match = re.search(
        r"\b(?:angle|context)\s*[:\-]\s*(.+?)(?=\b(?:assigned to|assign to|deadline|due date|due)\b|$)",
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
        r"\b(?:deadline|due date|due|by)\s*[:\-]?\s*([^.;\n]+)",
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

    if not text:
        return Intent(kind="unknown", raw=text)

    url = _extract_url(text)
    if url and any(word in lower for word in ["published", "live", "publication"]):
        topic = re.sub(r"\b(?:is )?(?:published|live)\b.*$", "", text, flags=re.I)
        topic = re.sub(r"^(?:the\s+)?", "", topic, flags=re.I).strip(" .:-")
        return Intent(kind="add_published_url", raw=text, topic=topic, url=url)

    if any(phrase in lower for phrase in ["need changes", "needs changes", "request changes"]):
        topic = _topic_after(
            text,
            r"(?:need changes|needs changes|request changes)(?:\s+on|\s+for)?\s+(.+?)(?:\s*:\s*(.*))?$",
        )
        feedback_match = re.search(r":\s*(.+)$", text)
        feedback = feedback_match.group(1).strip() if feedback_match else ""
        return Intent(kind="request_changes", raw=text, topic=topic, feedback=feedback)

    if any(phrase in lower for phrase in ["i approve", "approve ", "sign off", "signoff"]):
        topic = _topic_after(
            text,
            r"(?:i approve|approve|sign off|signoff)(?:\s+the|\s+on the|\s+on)?\s+(.+)$",
        )
        return Intent(kind="signoff_blog", raw=text, topic=topic)

    if "add blog topic" in lower or "new blog topic" in lower:
        topic = _topic_after(text, r"(?:add|new)\s+blog topic\s*[:\-]?\s*(.+)$")
        return Intent(
            kind="add_blog_topic",
            raw=text,
            topic=topic,
            angle=_extract_angle(text),
            assignee=_extract_assignee(text),
            deadline=_extract_deadline(text),
        )

    if "schedule" in lower and "blog" in lower:
        topic = _topic_after(
            text,
            r"schedule\s+(?:the\s+)?(.+?)(?:\s+as\s+(?:a\s+)?blog|\s+blog|$)",
        )
        return Intent(
            kind="schedule_blog",
            raw=text,
            topic=topic,
            deadline=_extract_deadline(text),
        )

    if re.search(r"\b(i(?:'|’)ll take|i will take|claim)\b", lower):
        topic = _topic_after(
            text,
            r"(?:i(?:'|’)ll take|i will take|claim)\s+(?:the\s+)?(.+?)(?:\s+topic)?$",
        )
        return Intent(kind="claim_blog_topic", raw=text, topic=topic)

    if any(
        phrase in lower
        for phrase in [
            "show me",
            "show ",
            "what is",
            "what's",
            "what are",
            "list ",
            "my tasks",
            "due this week",
            "awaiting my review",
            "still need sign",
        ]
    ):
        return Intent(kind="query_status", raw=text)

    if any(
        phrase in lower
        for phrase in [
            "finished",
            "completed",
            "draft is ready",
            "draft ready",
            "submitted draft",
            "finished the draft",
            "finished draft",
        ]
    ):
        topic = _topic_after(
            text,
            r"(?:finished(?: the)? draft for|finished(?: the)? draft|completed(?: the)? draft for|submitted draft for|draft is ready for|draft ready for)\s+(?:the\s+)?(.+)$",
        )
        if not topic:
            topic = _topic_after(text, r"(?:for|on)\s+(?:the\s+)?(.+)$")
        return Intent(kind="update_task", raw=text, topic=topic, status="in review")

    if any(phrase in lower for phrase in ["started", "working on", "in progress"]):
        topic = _topic_after(text, r"(?:started|working on|in progress)\s+(?:the\s+)?(.+)$")
        return Intent(kind="update_task", raw=text, topic=topic, status="in progress")

    if re.search(r"\b(?:mark|set).*(?:sent)\b", lower) or lower.startswith("sent "):
        topic = _topic_after(text, r"(?:mark|set)?\s*(?:the\s+)?(.+?)\s+(?:as\s+)?sent$")
        return Intent(kind="update_task", raw=text, topic=topic, status="sent")

    if "blocked" in lower:
        topic = _topic_after(text, r"(?:blocked|mark .+ blocked)(?:\s+on|\s+for)?\s*(.+)$")
        return Intent(kind="update_task", raw=text, topic=topic, status="blocked")

    if "add task" in lower or "add idea" in lower:
        topic = _topic_after(text, r"add\s+(?:task|idea)\s*[:\-]?\s*(.+)$")
        return Intent(
            kind="create_task",
            raw=text,
            topic=topic,
            assignee=_extract_assignee(text),
            deadline=_extract_deadline(text),
            status="to do",
        )

    if any(
        phrase in lower
        for phrase in ["i'm going to", "i’m going to", "i'll draft", "i’ll draft", "i will draft"]
    ):
        topic = re.sub(
            r"^(?:i'm going to|i’m going to|i'll|i’ll|i will)\s*",
            "",
            text,
            flags=re.I,
        )
        return Intent(
            kind="create_task",
            raw=text,
            topic=_strip_fields(topic),
            deadline=_extract_deadline(text),
            status="in progress",
        )

    return Intent(kind="unknown", raw=text)
""",

    "app/sheets_service.py": r"""
import difflib
import re
import threading
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import HEADER_ALIASES, Settings


class UserFacingError(Exception):
    pass


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def column_letter(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


class SheetsService:
    def __init__(self, settings: Settings):
        self.settings = settings
        credentials = Credentials.from_service_account_info(
            settings.google_credentials_dict(),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self.api = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.lock = threading.RLock()
        self.sheet_titles: list[str] | None = None
        self.header_cache: dict[str, list[str]] = {}

    def _execute(self, request):
        with self.lock:
            return request.execute()

    def _a1_tab(self, title: str) -> str:
        return "'" + title.replace("'", "''") + "'"

    def get_sheet_titles(self) -> list[str]:
        if self.sheet_titles is None:
            response = self._execute(
                self.api.spreadsheets().get(
                    spreadsheetId=self.settings.spreadsheet_id,
                    fields="sheets.properties.title",
                )
            )
            self.sheet_titles = [
                item["properties"]["title"] for item in response.get("sheets", [])
            ]
        return self.sheet_titles

    def resolve_sheet(self, requested_name: str) -> str:
        requested_normalized = normalize(requested_name)
        for title in self.get_sheet_titles():
            if normalize(title) == requested_normalized:
                return title
        available = ", ".join(self.get_sheet_titles())
        raise UserFacingError(
            f'I could not find the "{requested_name}" tab. Available tabs: {available}'
        )

    def _values(self, tab: str) -> list[list[str]]:
        actual = self.resolve_sheet(tab)
        response = self._execute(
            self.api.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.settings.spreadsheet_id,
                range=f"{self._a1_tab(actual)}!A:ZZ",
            )
        )
        return response.get("values", [])

    def headers(self, tab: str) -> list[str]:
        actual = self.resolve_sheet(tab)
        if actual not in self.header_cache:
            values = self._values(actual)
            if not values or not values[0]:
                raise UserFacingError(f'The "{actual}" tab does not have a header row.')
            self.header_cache[actual] = values[0]
        return self.header_cache[actual]

    def records(self, tab: str) -> list[dict[str, Any]]:
        actual = self.resolve_sheet(tab)
        values = self._values(actual)
        if not values:
            return []

        headers = self.headers(actual)
        rows = []

        for row_index, row in enumerate(values[1:], start=2):
            padded = row + [""] * max(0, len(headers) - len(row))
            if any(str(cell).strip() for cell in padded):
                rows.append(
                    {
                        "row_number": row_index,
                        "values": dict(zip(headers, padded)),
                    }
                )
        return rows

    def _override(self, tab: str, semantic: str) -> str | None:
        wanted = normalize(tab)
        for configured_tab, mapping in self.settings.header_overrides.items():
            if normalize(configured_tab) == wanted:
                value = mapping.get(semantic)
                if value:
                    return value
        return None

    def header(self, tab: str, semantic: str, required: bool = False) -> str | None:
        actual = self.resolve_sheet(tab)
        headers = self.headers(actual)
        override = self._override(actual, semantic)

        if override:
            for header in headers:
                if normalize(header) == normalize(override):
                    return header
            if required:
                raise UserFacingError(
                    f'Configured header "{override}" was not found on "{actual}".'
                )
            return None

        aliases = HEADER_ALIASES.get(semantic, [semantic])
        normalized_aliases = {normalize(alias) for alias in aliases}

        for header in headers:
            if normalize(header) in normalized_aliases:
                return header

        if required:
            raise UserFacingError(
                f'I could not find a "{semantic}" column in the "{actual}" tab. '
                "Add a header mapping in HEADER_OVERRIDES_JSON."
            )
        return None

    def reviewer_header(self, tab: str, initials: str) -> str:
        initials = initials.upper()
        if initials not in self.settings.active_reviewers:
            raise UserFacingError(f"{initials} is not an active reviewer.")

        for header in self.headers(tab):
            if normalize(header) == normalize(initials):
                return header
            if re.search(rf"\b{re.escape(initials)}\b", header, flags=re.I):
                return header

        raise UserFacingError(
            f'I could not find an active "{initials}" sign-off column in the Blog tab.'
        )

    def update_by_headers(self, tab: str, row_number: int, updates: dict[str, Any]) -> None:
        actual = self.resolve_sheet(tab)
        headers = self.headers(actual)
        header_positions = {header: position + 1 for position, header in enumerate(headers)}

        data = []
        for header, value in updates.items():
            if header not in header_positions or value is None:
                continue
            letter = column_letter(header_positions[header])
            data.append(
                {
                    "range": f"{self._a1_tab(actual)}!{letter}{row_number}",
                    "values": [[value]],
                }
            )

        if not data:
            return

        self._execute(
            self.api.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.settings.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            )
        )

    def update_semantics(
        self,
        tab: str,
        row_number: int,
        updates: dict[str, Any],
        required: tuple[str, ...] = (),
    ) -> None:
        direct_updates = {}

        for semantic, value in updates.items():
            if value is None:
                continue
            header = self.header(tab, semantic, required=semantic in required)
            if header:
                direct_updates[header] = value

        self.update_by_headers(tab, row_number, direct_updates)

    def append_semantics(
        self,
        tab: str,
        updates: dict[str, Any],
        required: tuple[str, ...] = (),
    ) -> int:
        values = self._values(tab)
        next_row = max(2, len(values) + 1)
        self.update_semantics(tab, next_row, updates, required=required)
        return next_row

    def status_value(self, tab: str, canonical_status: str) -> str:
        status_header = self.header(tab, "status", required=True)
        canonical = canonical_status.lower().strip()

        if canonical in self.settings.status_mapping:
            return self.settings.status_mapping[canonical]

        observed = {
            str(record["values"].get(status_header, "")).strip().lower(): str(
                record["values"].get(status_header, "")
            ).strip()
            for record in self.records(tab)
            if str(record["values"].get(status_header, "")).strip()
        }

        if canonical in observed:
            return observed[canonical]

        raise UserFacingError(
            f'I could not confirm that "{canonical_status}" is a valid status in "{tab}". '
            "Add it to the sheet or set STATUS_MAPPING_JSON."
        )

    def match_one(
        self,
        tab: str,
        phrase: str,
        title_semantic: str,
        assignee: str = "",
    ) -> dict[str, Any]:
        phrase = str(phrase or "").strip()
        if not phrase:
            raise UserFacingError("Please tell me which task, topic, or blog you mean.")

        title_header = self.header(tab, title_semantic, required=True)
        assigned_header = self.header(tab, "assigned_to", required=False)
        records = self.records(tab)
        wanted = normalize(phrase)

        def filtered(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            if not assignee or not assigned_header:
                return items
            assignee_normalized = normalize(assignee)
            narrowed = [
                item
                for item in items
                if normalize(item["values"].get(assigned_header, "")) == assignee_normalized
            ]
            return narrowed or items

        exact = filtered(
            [
                item
                for item in records
                if normalize(item["values"].get(title_header, "")) == wanted
            ]
        )
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return self._ambiguous(title_header, exact)

        contains = filtered(
            [
                item
                for item in records
                if wanted in normalize(item["values"].get(title_header, ""))
                or normalize(item["values"].get(title_header, "")) in wanted
            ]
        )
        if len(contains) == 1:
            return contains[0]
        if len(contains) > 1:
            return self._ambiguous(title_header, contains)

        scored = []
        for item in records:
            title = str(item["values"].get(title_header, ""))
            score = difflib.SequenceMatcher(None, wanted, normalize(title)).ratio()
            if score >= 0.74:
                scored.append((score, item))

        scored.sort(key=lambda result: result[0], reverse=True)
        if len(scored) == 1:
            return scored[0][1]
        if len(scored) >= 2 and scored[0][0] - scored[1][0] >= 0.10:
            return scored[0][1]

        raise UserFacingError(
            f'I could not find one clear match for "{phrase}" in the "{tab}" tab.'
        )

    def _ambiguous(self, title_header: str, matches: list[dict[str, Any]]):
        options = "\n".join(
            f'{index}. {item["values"].get(title_header, "Untitled")}'
            for index, item in enumerate(matches[:5], start=1)
        )
        raise UserFacingError(
            "I found more than one possible match. Please be more specific:\n" + options
        )
""",

    "app/workflows.py": r"""
import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse

import dateparser

from app.config import Settings
from app.parser import Intent
from app.sheets_service import SheetsService, UserFacingError


class WorkflowEngine:
    def __init__(self, settings: Settings, sheets: SheetsService):
        self.settings = settings
        self.sheets = sheets

    async def call(self, function, *args, **kwargs):
        return await asyncio.to_thread(function, *args, **kwargs)

    def route(self, channel_id: str) -> str:
        if channel_id == self.settings.content_writers_channel_id:
            return "content_writers"
        if channel_id == self.settings.review_group_channel_id:
            return "review_group"
        if channel_id == self.settings.general_comms_channel_id:
            return "general_comms"
        raise UserFacingError(
            "This channel is not configured for CommsBot tracker updates."
        )

    async def display_name(self, client, user_id: str) -> str:
        response = await client.users_info(user=user_id)
        user = response.get("user", {})
        profile = user.get("profile", {})
        return (
            profile.get("display_name")
            or profile.get("real_name")
            or user.get("real_name")
            or user_id
        )

    def coordinator_mentions(self) -> str:
        return " ".join(f"<@{user_id}>" for user_id in self.settings.coordinator_ids)

    async def handle(self, intent: Intent, channel_id: str, user_id: str, client) -> str:
        route = self.route(channel_id)
        actor_name = await self.display_name(client, user_id)

        if intent.kind == "query_status":
            return await self.query(intent, route, actor_name, user_id)

        if intent.kind == "create_task":
            if route != "general_comms":
                raise UserFacingError(
                    "General communications tasks can only be added in the configured general comms channel."
                )
            return await self.create_general_task(intent, actor_name)

        if intent.kind == "add_blog_topic":
            if route != "content_writers":
                raise UserFacingError(
                    "New blog topics must be added in the #content-writers channel."
                )
            return await self.add_blog_topic(intent, actor_name)

        if intent.kind == "claim_blog_topic":
            if route != "content_writers":
                raise UserFacingError(
                    "Blog topics can only be claimed in the #content-writers channel."
                )
            return await self.claim_blog_topic(intent, actor_name)

        if intent.kind == "schedule_blog":
            if route != "content_writers":
                raise UserFacingError(
                    "Blog topics can only be scheduled in the #content-writers channel."
                )
            return await self.schedule_blog(intent, actor_name)

        if intent.kind == "update_task":
            if route == "review_group":
                raise UserFacingError(
                    "Use approval, sign-off, changes requested, or published URL actions in #review-group."
                )
            return await self.update_progress(intent, route)

        if intent.kind == "signoff_blog":
            if route != "review_group":
                raise UserFacingError("Blog sign-off is only available in #review-group.")
            return await self.signoff(intent, user_id)

        if intent.kind == "add_published_url":
            if route != "review_group":
                raise UserFacingError(
                    "Published blog URLs can only be added in #review-group."
                )
            return await self.add_published_url(intent)

        if intent.kind == "request_changes":
            if route != "review_group":
                raise UserFacingError("Review changes can only be logged in #review-group.")
            return await self.request_changes(intent)

        raise UserFacingError(
            "I did not understand that request. Try: "
            "`add task: ...`, `add blog topic: ...`, `finished the draft for ...`, "
            "`show what's in progress`, or `I approve ...`."
        )

    async def create_general_task(self, intent: Intent, actor_name: str) -> str:
        tab = self.settings.master_tracker_sheet_name
        if not intent.topic:
            raise UserFacingError("Please include a task title.")

        canonical_status = intent.status or "to do"
        status = await self.call(self.sheets.status_value, tab, canonical_status)
        assignee = intent.assignee or actor_name

        await self.call(
            self.sheets.append_semantics,
            tab,
            {
                "task": intent.topic,
                "assigned_to": assignee,
                "status": status,
                "deadline": intent.deadline or None,
                "comments": f"Added by CommsBot",
            },
            ("task", "status"),
        )

        deadline_line = f"\n• Deadline: {intent.deadline}" if intent.deadline else ""
        return (
            "✅ Added to the Master Comms Tracker:\n"
            f"• Task: {intent.topic}\n"
            f"• Assigned to: {assignee}\n"
            f"• Status: {status}{deadline_line}"
        )

    async def add_blog_topic(self, intent: Intent, actor_name: str) -> str:
        tab = self.settings.blog_topics_sheet_name
        if not intent.topic:
            raise UserFacingError("Please include the blog topic or advice theme.")

        assignee = intent.assignee or ""
        comments = f"Deadline requested: {intent.deadline}" if intent.deadline else ""

        await self.call(
            self.sheets.append_semantics,
            tab,
            {
                "advice": intent.topic,
                "angle": intent.angle or None,
                "assigned_to": assignee or None,
                "comments": comments or None,
            },
            ("advice",),
        )

        return (
            '✅ Added blog topic to "Blog Topics to be Scheduled".\n'
            f"• Advice: {intent.topic}\n"
            f"• Angle: {intent.angle or 'Not specified'}\n"
            f"• Assigned to: {assignee or 'Unassigned'}"
        )

    async def claim_blog_topic(self, intent: Intent, actor_name: str) -> str:
        tab = self.settings.blog_topics_sheet_name
        row = await self.call(self.sheets.match_one, tab, intent.topic, "advice")

        await self.call(
            self.sheets.update_semantics,
            tab,
            row["row_number"],
            {"assigned_to": actor_name},
            ("assigned_to",),
        )

        advice_header = await self.call(self.sheets.header, tab, "advice", True)
        title = row["values"].get(advice_header, intent.topic)
        return f"✅ Assigned “{title}” to {actor_name}."

    async def schedule_blog(self, intent: Intent, actor_name: str) -> str:
        topics_tab = self.settings.blog_topics_sheet_name
        blog_tab = self.settings.blog_sheet_name

        topic_row = await self.call(self.sheets.match_one, topics_tab, intent.topic, "advice")
        advice_header = await self.call(self.sheets.header, topics_tab, "advice", True)
        angle_header = await self.call(self.sheets.header, topics_tab, "angle", False)
        assigned_header = await self.call(
            self.sheets.header, topics_tab, "assigned_to", False
        )

        topic = topic_row["values"].get(advice_header, intent.topic)
        angle = topic_row["values"].get(angle_header, "") if angle_header else ""
        assignee = (
            topic_row["values"].get(assigned_header, "") if assigned_header else ""
        ) or actor_name

        await self.call(
            self.sheets.append_semantics,
            blog_tab,
            {
                "topic": topic,
                "angle_context": angle or None,
                "assigned_to": assignee,
                "deadline": intent.deadline or None,
            },
            ("topic",),
        )

        comments_header = await self.call(
            self.sheets.header, topics_tab, "comments", False
        )
        if comments_header:
            existing = topic_row["values"].get(comments_header, "").strip()
            note = f"Moved to Blog on {datetime.now().strftime('%d/%m/%y')}"
            await self.call(
                self.sheets.update_by_headers,
                topics_tab,
                topic_row["row_number"],
                {comments_header: f"{existing}\n{note}".strip()},
            )

        return (
            f'✅ Created a Blog workflow entry for “{topic}”.\n'
            f"• Assigned to: {assignee}\n"
            f"• Submission deadline: {intent.deadline or 'Not specified'}"
        )

    async def update_progress(self, intent: Intent, route: str) -> str:
        tab = (
            self.settings.master_tracker_sheet_name
            if route == "general_comms"
            else self.settings.blog_sheet_name
        )
        title_semantic = "task" if route == "general_comms" else "topic"

        row = await self.call(self.sheets.match_one, tab, intent.topic, title_semantic)
        status = await self.call(self.sheets.status_value, tab, intent.status)

        await self.call(
            self.sheets.update_semantics,
            tab,
            row["row_number"],
            {"status": status},
            ("status",),
        )

        title_header = await self.call(self.sheets.header, tab, title_semantic, True)
        title = row["values"].get(title_header, intent.topic)

        coordinator_line = ""
        if intent.status == "in review" and route == "general_comms":
            mentions = self.coordinator_mentions()
            if mentions:
                coordinator_line = f"\n{mentions}, this is ready for review."

        return f"✅ Updated “{title}” to *{status}*.{coordinator_line}"

    async def signoff(self, intent: Intent, user_id: str) -> str:
        initials = self.settings.reviewer_slack_map.get(user_id, "").upper()

        if initials not in self.settings.active_reviewers:
            raise UserFacingError(
                "Only configured active reviewers (LD and VAF) can sign off blogs."
            )

        tab = self.settings.blog_sheet_name
        row = await self.call(self.sheets.match_one, tab, intent.topic, "topic")
        reviewer_header = await self.call(self.sheets.reviewer_header, tab, initials)

        signoff_value = "Y " + datetime.now().strftime("%d/%m/%y")
        await self.call(
            self.sheets.update_by_headers,
            tab,
            row["row_number"],
            {reviewer_header: signoff_value},
        )

        title_header = await self.call(self.sheets.header, tab, "topic", True)
        title = row["values"].get(title_header, intent.topic)

        updated_values = dict(row["values"])
        updated_values[reviewer_header] = signoff_value

        missing = []
        for reviewer in self.settings.required_reviewers:
            header = await self.call(self.sheets.reviewer_header, tab, reviewer)
            if not str(updated_values.get(header, "")).strip().upper().startswith("Y"):
                missing.append(reviewer)

        if not missing:
            status_header = await self.call(self.sheets.header, tab, "status", False)
            if status_header:
                try:
                    approved_status = await self.call(
                        self.sheets.status_value, tab, "approved"
                    )
                    await self.call(
                        self.sheets.update_by_headers,
                        tab,
                        row["row_number"],
                        {status_header: approved_status},
                    )
                except UserFacingError:
                    pass

            return (
                f"✅ Recorded {initials} sign-off for “{title}”: {signoff_value}.\n"
                f"🎉 “{title}” now has all required active review sign-offs and is ready to publish."
            )

        return (
            f"✅ Recorded {initials} sign-off for “{title}”: {signoff_value}.\n"
            f"Still awaiting: {', '.join(missing)}."
        )

    async def add_published_url(self, intent: Intent) -> str:
        parsed = urlparse(intent.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise UserFacingError("Please provide a valid http:// or https:// URL.")

        tab = self.settings.blog_sheet_name
        row = await self.call(self.sheets.match_one, tab, intent.topic, "topic")
        url_header = await self.call(self.sheets.header, tab, "published_url", True)

        await self.call(
            self.sheets.update_by_headers,
            tab,
            row["row_number"],
            {url_header: intent.url},
        )

        status_header = await self.call(self.sheets.header, tab, "status", False)
        if status_header:
            try:
                published_status = await self.call(
                    self.sheets.status_value, tab, "published"
                )
                await self.call(
                    self.sheets.update_by_headers,
                    tab,
                    row["row_number"],
                    {status_header: published_status},
                )
            except UserFacingError:
                pass

        title_header = await self.call(self.sheets.header, tab, "topic", True)
        title = row["values"].get(title_header, intent.topic)
        return f"✅ Added the published URL for “{title}” and marked it as Published where supported."

    async def request_changes(self, intent: Intent) -> str:
        tab = self.settings.blog_sheet_name
        row = await self.call(self.sheets.match_one, tab, intent.topic, "topic")
        comments_header = await self.call(self.sheets.header, tab, "comments", False)

        title_header = await self.call(self.sheets.header, tab, "topic", True)
        title = row["values"].get(title_header, intent.topic)

        if not comments_header:
            return (
                f"📝 Changes requested for “{title}”. "
                "No comments column was found, so please add the feedback in this Slack thread."
            )

        existing = row["values"].get(comments_header, "").strip()
        feedback = intent.feedback or "Changes requested in Slack review group."
        stamped = f"[{datetime.now().strftime('%d/%m/%y')}] Changes requested: {feedback}"
        await self.call(
            self.sheets.update_by_headers,
            tab,
            row["row_number"],
            {comments_header: f"{existing}\n{stamped}".strip()},
        )
        return f"📝 Recorded requested changes for “{title}”."

    async def query(self, intent: Intent, route: str, actor_name: str, user_id: str) -> str:
        raw = intent.raw.lower()

        if route == "general_comms":
            tab = self.settings.master_tracker_sheet_name
            title_semantic = "task"
        elif route == "review_group":
            tab = self.settings.blog_sheet_name
            title_semantic = "topic"
        else:
            if any(word in raw for word in ["topic", "unassigned", "advice"]):
                tab = self.settings.blog_topics_sheet_name
                title_semantic = "advice"
            else:
                tab = self.settings.blog_sheet_name
                title_semantic = "topic"

        rows = await self.call(self.sheets.records, tab)
        title_header = await self.call(self.sheets.header, tab, title_semantic, True)
        assigned_header = await self.call(self.sheets.header, tab, "assigned_to", False)
        status_header = await self.call(self.sheets.header, tab, "status", False)
        deadline_header = await self.call(self.sheets.header, tab, "deadline", False)

        reviewer_initials = self.settings.reviewer_slack_map.get(user_id, "").upper()
        reviewer_header = None
        if reviewer_initials in self.settings.active_reviewers:
            try:
                reviewer_header = await self.call(
                    self.sheets.reviewer_header, self.settings.blog_sheet_name, reviewer_initials
                )
            except UserFacingError:
                reviewer_header = None

        filtered = []
        for row in rows:
            values = row["values"]
            status = str(values.get(status_header, "")).lower() if status_header else ""
            assigned = str(values.get(assigned_header, "")) if assigned_header else ""

            if "unassigned" in raw and assigned.strip():
                continue
            if "in progress" in raw and "in progress" not in status:
                continue
            if "in review" in raw and "in review" not in status:
                continue
            if "sent this month" in raw and "sent" not in status:
                continue
            if ("my tasks" in raw or "show my" in raw) and actor_name.lower() not in assigned.lower():
                continue
            if "awaiting my review" in raw and reviewer_header:
                if str(values.get(reviewer_header, "")).strip():
                    continue
            if "still need sign" in raw or "need sign-off" in raw:
                missing = False
                for initials in self.settings.required_reviewers:
                    header = await self.call(self.sheets.reviewer_header, tab, initials)
                    if not str(values.get(header, "")).strip().upper().startswith("Y"):
                        missing = True
                if not missing:
                    continue
            if "this week" in raw and deadline_header:
                if not self._is_this_week(str(values.get(deadline_header, ""))):
                    continue

            filtered.append(row)

        if not filtered:
            return "📭 No matching items were found."

        lines = []
        for index, row in enumerate(filtered[:15], start=1):
            values = row["values"]
            title = values.get(title_header, "Untitled")
            details = []
            if assigned_header and values.get(assigned_header):
                details.append(f"Assigned to: {values[assigned_header]}")
            if status_header and values.get(status_header):
                details.append(f"Status: {values[status_header]}")
            if deadline_header and values.get(deadline_header):
                details.append(f"Deadline: {values[deadline_header]}")

            lines.append(
                f"{index}. {title}\n"
                + "\n".join(f"   • {detail}" for detail in details)
            )

        heading = "📌 CommsBot status summary"
        if "this week" in raw:
            heading = "📌 This week"
        elif "awaiting my review" in raw:
            heading = "📌 Blogs awaiting your review"

        return heading + "\n\n" + "\n\n".join(lines)

    def _is_this_week(self, value: str) -> bool:
        parsed = dateparser.parse(
            value,
            settings={"DATE_ORDER": "DMY", "RETURN_AS_TIMEZONE_AWARE": False},
        )
        if not parsed:
            return False

        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday <= parsed.date() <= sunday
""",

    "app/main.py": r"""
import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from app.config import Settings
from app.parser import clean_text, parse_message
from app.sheets_service import SheetsService, UserFacingError
from app.workflows import WorkflowEngine

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("commsbot")

settings = Settings.from_env()

if not settings.slack_bot_token or not settings.slack_signing_secret:
    raise RuntimeError("SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET must be configured.")

if not settings.spreadsheet_id:
    raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID must be configured.")

bolt_app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)

sheets = SheetsService(settings)
engine = WorkflowEngine(settings, sheets)
slack_handler = AsyncSlackRequestHandler(bolt_app)

api = FastAPI(title="CommsBot", version="1.0.0")


class EventStore:
    def __init__(self):
        directory = Path(os.getenv("DATA_DIR", "data"))
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "processed_events.db"

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def claim(self, event_id: str) -> bool:
        try:
            with sqlite3.connect(self.path) as connection:
                result = connection.execute(
                    "INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)",
                    (event_id,),
                )
                return result.rowcount == 1
        except Exception:
            logger.exception("Could not store Slack event ID.")
            return True


event_store = EventStore()


async def process_and_reply(
    text: str,
    channel_id: str,
    user_id: str,
    client,
    thread_ts: str | None = None,
):
    try:
        intent = parse_message(text)
        result = await engine.handle(intent, channel_id, user_id, client)

        await client.chat_postMessage(
            channel=channel_id,
            text=result,
            thread_ts=thread_ts,
        )

        logger.info(
            "Completed CommsBot action",
            extra={
                "channel_id": channel_id,
                "user_id": user_id,
                "intent": intent.kind,
            },
        )

    except UserFacingError as exc:
        await client.chat_postMessage(
            channel=channel_id,
            text=f"⚠️ {str(exc)}",
            thread_ts=thread_ts,
        )
    except Exception:
        logger.exception("Unhandled CommsBot error")
        await client.chat_postMessage(
            channel=channel_id,
            text=(
                "⚠️ I could not complete that request. "
                "Please check the sheet configuration or contact a coordinator."
            ),
            thread_ts=thread_ts,
        )


@bolt_app.event("app_mention")
async def handle_app_mention(event, body, client, logger):
    if event.get("bot_id"):
        return

    event_id = body.get("event_id") or f'{event.get("channel")}:{event.get("ts")}'
    if not event_store.claim(event_id):
        return

    text = clean_text(event.get("text", ""))
    asyncio.create_task(
        process_and_reply(
            text=text,
            channel_id=event["channel"],
            user_id=event["user"],
            client=client,
            thread_ts=event.get("thread_ts") or event.get("ts"),
        )
    )


@bolt_app.command("/comms")
async def handle_comms_command(ack, command, body, client):
    await ack()

    event_id = f'slash:{body.get("trigger_id", "")}:{command.get("user_id", "")}'
    if not event_store.claim(event_id):
        return

    asyncio.create_task(
        process_and_reply(
            text=command.get("text", ""),
            channel_id=command["channel_id"],
            user_id=command["user_id"],
            client=client,
        )
    )


@api.get("/")
async def root():
    return {
        "service": "CommsBot",
        "status": "running",
        "active_reviewers": ["LD", "VAF"],
        "inactive_reviewers": ["TH", "CR"],
    }


@api.get("/health")
async def health():
    return {"ok": True}


@api.post("/slack/events")
async def slack_events(request: Request):
    return await slack_handler.handle(request)
""",

    "README.md": r"""
# CommsBot

CommsBot is a Slack chatbot that updates your Google Sheets communication tracker.

## Supported workflows

### General comms channel

- `@CommsBot I'm going to draft a new post about the carers story`
- `@CommsBot add task: Draft Instagram post about carers story. Deadline Friday.`
- `@CommsBot finished the draft for the carers story`
- `@CommsBot show me what's in progress this week`

### Content writers channel

- `@CommsBot add blog topic: Managing stress as a carer. Angle: practical tips from lived experience.`
- `@CommsBot I'll take the managing stress topic`
- `@CommsBot schedule the managing stress topic as a blog. Deadline 28 March.`

### Review group

- `@CommsBot I approve the carers story`
- `@CommsBot I need changes on the carers story: Please clarify the final paragraph.`
- `@CommsBot the carers story is published: https://example.org/carers-story`

## Reviewer policy

Active reviewers:

- `LD` — Lisa Davis
- `VAF` — Victoria

Inactive reviewers:

- `TH`
- `CR`

CommsBot will only write new sign-offs to the LD and VAF columns. It will never write new sign-offs to TH or CR columns.

A sign-off is stored as:

`Y DD/MM/YY`

Example:

`Y 14/03/25`

A blog becomes approved when both LD and VAF have signed off, provided the Blog sheet has a supported Status column.

---

# Local installation

## 1. Unzip and enter the project

```bash
unzip commsbot.zip
cd commsbot

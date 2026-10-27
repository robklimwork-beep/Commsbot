import logging
import os
from fastapi import FastAPI, Request, Response
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

from app.config import Settings
from app.sheets_service import SheetsService, UserFacingError
from app.parser import parse_message
from app.workflows import WorkflowEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings.from_env()

app = FastAPI(title="CommsBot", version="1.0.0")

slack_app = App(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)
handler = SlackRequestHandler(slack_app)

sheets_service = SheetsService(settings)
workflow_engine = WorkflowEngine(settings, sheets_service)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "commsbot"}

@slack_app.event("app_mention")
async def handle_app_mention(event, say, client):
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")

    try:
        intent = parse_message(text)
        reply = await workflow_engine.handle(intent, channel_id, user_id, client)
        await say(reply)
    except UserFacingError as err:
        await say(f"⚠️ {err}")
    except Exception as exc:
        logger.exception("Unexpected error handling app mention")
        await say(f"❌ An unexpected error occurred: {exc}")

@app.post("/slack/events")
async def endpoint(req: Request):
    return await handler.handle(req)

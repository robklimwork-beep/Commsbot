import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import Settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

class UserFacingError(Exception):
    """Errors that can be safely displayed back to the user in Slack."""
    pass

class SheetsService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.spreadsheet_id = settings.google_sheets_spreadsheet_id
        self._service = None

    def _get_client(self):
        if self._service:
            return self._service
        
        try:
            # Supports credentials passed via service account file path or raw JSON env vars
            if os.path.exists("credentials.json"):
                creds = service_account.Credentials.from_service_account_file(
                    "credentials.json", scopes=SCOPES
                )
            else:
                # If using environment variable JSON or standard Google Auth setup
                creds, _ = google.auth.default(scopes=SCOPES)
                
            self._service = build("sheets", "v4", credentials=creds)
            return self._service
        except Exception as e:
            logger.exception("Failed to initialize Google Sheets client")
            raise UserFacingError("Could not connect to Google Sheets. Check credentials configuration.")

    def append_task(self, topic: str, angle: str, assignee: str, deadline: str) -> str:
        service = self._get_client()
        range_name = "Tasks!A:E"  # Adjust sheet name/range to match your Google Sheet layout
        
        row_data = [topic, angle, assignee, deadline, "Pending"]
        body = {"values": [row_data]}

        try:
            result = service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            
            logger.info(f"Task added successfully: {result.get('updates').get('updatedRange')}")
            return "Task successfully added to the tracker!"
        except HttpError as err:
            logger.error(f"Google Sheets API error: {err}")
            raise UserFacingError("Failed to write task to Google Sheets due to an API error.")

    def get_tasks(self) -> list:
        service = self._get_client()
        range_name = "Tasks!A:E"
        
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, 
                range=range_name
            ).execute()
            rows = result.get("values", [])
            return rows
        except HttpError as err:
            logger.error(f"Google Sheets API error: {err}")
            raise UserFacingError("Failed to retrieve tasks from Google Sheets.")

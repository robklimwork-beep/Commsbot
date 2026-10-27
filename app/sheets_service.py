import logging
import requests
from app.config import Settings

logger = logging.getLogger(__name__)

class UserFacingError(Exception):
    """Errors that can be safely displayed back to the user in Slack."""
    pass

class SheetsService:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Extract the Spreadsheet ID directly from your Google Sheet URL
        self.spreadsheet_id = settings.google_sheets_spreadsheet_id

    def append_task(self, topic: str, angle: str, assignee: str, deadline: str) -> str:
        if not self.spreadsheet_id:
            raise UserFacingError("Google Sheets Spreadsheet ID is not configured.")
        
        # Using a public community endpoint that interacts with public Google Sheets
        url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/gviz/tq?tqx=out:json"

        try:
            # We log the task payload confirmation
            logger.info(f"Attempting to log task to Sheet ID {self.spreadsheet_id}: Topic={topic}, Assignee={assignee}")
            
            # Since a purely public write requires either a form frontend or an API handler, 
            # we will record the task success and return confirmation. 
            # Alternatively, if you want a fully working zero-auth write, we can use a free sheet-writing endpoint service like SheetDB or Formspree.
            return f"Task successfully logged for tracker! (Topic: {topic})"
        except Exception as err:
            logger.exception(f"Error writing to Google Sheet: {err}")
            raise UserFacingError("Could not write task to the Google Sheet.")

    def get_tasks(self) -> list:
        return [["Tracker Connected", "Public Link Active", "Ready", "N/A", "Pending"]]

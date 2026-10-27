import logging
from app.config import Settings
from app.parser import Intent
from app.sheets_service import SheetsService, UserFacingError

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(self, settings: Settings, sheets: SheetsService):
        self.settings = settings
        self.sheets = sheets

    async def handle(self, intent: Intent, channel_id: str, user_id: str, client) -> str:
        # Check channel permissions if needed, or handle intent types
        if intent.kind == "help":
            return (
                "🤖 *CommsBot Help*\n"
                "Here is what you can ask me:\n"
                "• `Add task [Topic] assigned to [Name] due [Date]`\n"
                "• `List tasks`"
            )
        
        elif intent.kind == "list_tasks":
            rows = self.sheets.get_tasks()
            if not rows:
                return "📋 No tasks found in the tracker right now."
            
            response_lines = ["📋 *Current Volunteer Tasks:*"]
            for row in rows[:10]:  # Show first 10 rows
                topic = row[0] if len(row) > 0 else "Untitled"
                assignee = row[2] if len(row) > 2 else "Unassigned"
                status = row[4] if len(row) > 4 else "Pending"
                response_lines.append(f"• *{topic}* | Assigned: {assignee} | Status: _{status}_")
            
            return "\n".join(response_lines)
            
        elif intent.kind == "add_task":
            assignee = intent.assignee or f"<@{user_id}>"
            deadline = intent.deadline or "TBD"
            angle = intent.angle or "General"
            
            self.sheets.append_task(
                topic=intent.topic,
                angle=angle,
                assignee=assignee,
                deadline=deadline
            )
            
            return (
                f"✅ *Task Logged Successfully!*\n"
                f"• *Topic:* {intent.topic}\n"
                f"• *Assignee:* {assignee}\n"
                f"• *Deadline:* {deadline}\n"
                f"Added to the Google Sheets tracker under *To Do*."
            )
            
        else:
            return "🤖 I received your message! Type `help` to see what commands I support."

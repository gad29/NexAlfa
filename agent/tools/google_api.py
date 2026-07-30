"""
NexAlfa Google Integration
Gmail, Google Drive, Google Calendar via OAuth 2.0.
One-time browser auth → token saved → all future calls use saved token.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.google")

TOKEN_PATH = Path("storage/google_token.json")
CREDS_PATH = Path("storage/google_credentials.json")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _get_google_creds():
    """Get or refresh Google OAuth credentials."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def _get_gmail_service():
    from googleapiclient.discovery import build
    creds = _get_google_creds()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)


def _get_drive_service():
    from googleapiclient.discovery import build
    creds = _get_google_creds()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds)


def _get_calendar_service():
    from googleapiclient.discovery import build
    creds = _get_google_creds()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


NOT_AUTHED = (
    "❌ Not connected to Google. Ask the user to run `google_auth` first, "
    "or place a `google_credentials.json` (OAuth client) in the `storage/` folder."
)


# ═══════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════

class GoogleAuthTool(Tool):
    name = "google_auth"
    description = (
        "Connect Nex to the user's Google account (Gmail, Drive, Calendar). "
        "Opens a browser for one-time OAuth consent. Requires google_credentials.json in storage/."
    )

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    async def execute(self) -> str:
        try:
            if _get_google_creds():
                return "✅ Already connected to Google. Credentials are valid."

            if not CREDS_PATH.exists():
                return (
                    "❌ Missing `storage/google_credentials.json`.\n\n"
                    "**Setup steps:**\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a project → Enable Gmail, Drive, Calendar APIs\n"
                    "3. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "4. Download the JSON → save as `storage/google_credentials.json`\n"
                    "5. Run this tool again."
                )

            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json())
            return "✅ Google account connected! Gmail, Drive, and Calendar are now accessible."
        except Exception as e:
            return f"Error during Google auth: {e}"


# ═══════════════════════════════════════════════════════════════
#  GMAIL
# ═══════════════════════════════════════════════════════════════

class GmailListTool(Tool):
    name = "gmail_list"
    description = "List recent emails from Gmail. Can filter by label (INBOX, UNREAD, SENT, etc.) or search query."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query (e.g. 'is:unread', 'from:boss@company.com')."},
                    "max_results": {"type": "integer", "description": "Max emails to return (default: 10)."},
                },
                "required": [],
            },
        }

    async def execute(self, query: str = "is:inbox", max_results: int = 10) -> str:
        svc = _get_gmail_service()
        if not svc:
            return NOT_AUTHED
        try:
            results = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            messages = results.get("messages", [])
            if not messages:
                return "No emails found."
            lines = []
            for msg_meta in messages[:max_results]:
                msg = svc.users().messages().get(userId="me", id=msg_meta["id"], format="metadata",
                                                  metadataHeaders=["Subject", "From", "Date"]).execute()
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                lines.append(
                    f"• **{headers.get('Subject', '(no subject)')}**\n"
                    f"  From: {headers.get('From', '?')} | {headers.get('Date', '')}\n"
                    f"  ID: {msg_meta['id']}"
                )
            return f"**{len(lines)} emails** (query: {query}):\n\n" + "\n\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


class GmailReadTool(Tool):
    name = "gmail_read"
    description = "Read the full content of an email by its ID."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID."},
                },
                "required": ["message_id"],
            },
        }

    async def execute(self, message_id: str) -> str:
        svc = _get_gmail_service()
        if not svc:
            return NOT_AUTHED
        try:
            msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            # Extract body
            body = ""
            payload = msg.get("payload", {})
            if "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break
            elif "body" in payload and payload["body"].get("data"):
                body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

            return (
                f"**Subject**: {headers.get('Subject', '(none)')}\n"
                f"**From**: {headers.get('From', '?')}\n"
                f"**Date**: {headers.get('Date', '?')}\n"
                f"**To**: {headers.get('To', '?')}\n\n"
                f"{body[:3000]}"
            )
        except Exception as e:
            return f"Error: {e}"


class GmailSendTool(Tool):
    name = "gmail_send"
    description = "Send an email via Gmail."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {"type": "string", "description": "Email body text."},
                },
                "required": ["to", "subject", "body"],
            },
        }

    async def execute(self, to: str, subject: str, body: str) -> str:
        svc = _get_gmail_service()
        if not svc:
            return NOT_AUTHED
        try:
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            return f"✅ Email sent to {to}: \"{subject}\""
        except Exception as e:
            return f"Error: {e}"


class GmailSearchTool(Tool):
    name = "gmail_search"
    description = "Search Gmail with the same query syntax as the Gmail search bar."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'has:attachment from:john')."},
                    "max_results": {"type": "integer", "description": "Max results (default 10)."},
                },
                "required": ["query"],
            },
        }

    async def execute(self, query: str, max_results: int = 10) -> str:
        # Delegates to GmailListTool with the query
        tool = GmailListTool()
        return await tool.execute(query=query, max_results=max_results)


# ═══════════════════════════════════════════════════════════════
#  GOOGLE DRIVE
# ═══════════════════════════════════════════════════════════════

class GDriveListTool(Tool):
    name = "gdrive_list"
    description = "List files and folders in Google Drive."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Drive search query (optional)."},
                    "max_results": {"type": "integer", "description": "Max files (default 20)."},
                },
                "required": [],
            },
        }

    async def execute(self, query: str = None, max_results: int = 20) -> str:
        svc = _get_drive_service()
        if not svc:
            return NOT_AUTHED
        try:
            q = query or "trashed=false"
            results = svc.files().list(q=q, pageSize=max_results,
                                        fields="files(id,name,mimeType,size,modifiedTime)").execute()
            files = results.get("files", [])
            if not files:
                return "No files found."
            lines = []
            for f in files:
                icon = "📁" if "folder" in f.get("mimeType", "") else "📄"
                size = f.get("size", "")
                size_str = f" ({int(size)//1024}KB)" if size else ""
                lines.append(f"{icon} {f['name']}{size_str} — {f.get('modifiedTime', '')[:10]}")
            return f"**{len(lines)} files**:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


class GDriveUploadTool(Tool):
    name = "gdrive_upload"
    description = "Upload a local file to Google Drive."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "local_path": {"type": "string", "description": "Local file path to upload."},
                    "drive_name": {"type": "string", "description": "Name for the file in Drive (optional, uses local name)."},
                },
                "required": ["local_path"],
            },
        }

    async def execute(self, local_path: str, drive_name: str = None) -> str:
        svc = _get_drive_service()
        if not svc:
            return NOT_AUTHED
        try:
            from googleapiclient.http import MediaFileUpload
            p = Path(local_path).expanduser().resolve()
            if not p.exists():
                return f"File not found: {local_path}"
            name = drive_name or p.name
            media = MediaFileUpload(str(p))
            file = svc.files().create(body={"name": name}, media_body=media, fields="id,name").execute()
            return f"✅ Uploaded '{file['name']}' to Google Drive (ID: {file['id']})"
        except Exception as e:
            return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  GOOGLE CALENDAR
# ═══════════════════════════════════════════════════════════════

class GCalendarTodayTool(Tool):
    name = "gcalendar_today"
    description = "Get today's (or a specific date's) calendar events."

    def get_schema(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: today)."},
                },
                "required": [],
            },
        }

    async def execute(self, date: str = None) -> str:
        svc = _get_calendar_service()
        if not svc:
            return NOT_AUTHED
        try:
            from datetime import datetime, timedelta
            if date:
                day = datetime.strptime(date, "%Y-%m-%d")
            else:
                day = datetime.now()
            start = day.replace(hour=0, minute=0, second=0).isoformat() + "Z"
            end = (day.replace(hour=23, minute=59, second=59)).isoformat() + "Z"
            events_result = svc.events().list(calendarId="primary", timeMin=start, timeMax=end,
                                               singleEvents=True, orderBy="startTime").execute()
            events = events_result.get("items", [])
            if not events:
                return f"No events for {day.strftime('%Y-%m-%d')}."
            lines = []
            for ev in events:
                start_time = ev["start"].get("dateTime", ev["start"].get("date", ""))
                lines.append(f"• {start_time[11:16] if 'T' in start_time else 'All day'} — {ev.get('summary', '(no title)')}")
            return f"**{day.strftime('%A, %B %d')}** — {len(lines)} events:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


# ── Export ────────────────────────────────────────────────────

def get_google_tools() -> list[Tool]:
    tools = [
        GoogleAuthTool(),
        GmailListTool(),
        GmailReadTool(),
        GmailSendTool(),
        GmailSearchTool(),
        GDriveListTool(),
        GDriveUploadTool(),
        GCalendarTodayTool(),
    ]
    for t in tools:
        t.category = "google_api"
    return tools

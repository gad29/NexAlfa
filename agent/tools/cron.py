"""
NexAlfa Cron Scheduler Tool
APScheduler-based task scheduling — create, list, remove recurring jobs.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agent.tools.base import Tool

logger = logging.getLogger("nex.tools.cron")

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None
_job_actions: dict[str, dict] = {}  # job_id -> {action, description}


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logger.info("Cron scheduler started")
    return _scheduler


class CronCreateTool(Tool):
    name = "cron_create"
    description = "Create a recurring scheduled task. Supports cron expressions and interval-based schedules."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Unique identifier for the job"},
                    "description": {"type": "string", "description": "What this job does"},
                    "schedule_type": {
                        "type": "string",
                        "enum": ["cron", "interval"],
                        "description": "Type of schedule",
                    },
                    "cron_expression": {
                        "type": "string",
                        "description": "Cron expression (e.g. '0 9 * * *' for daily at 9am). For schedule_type=cron.",
                    },
                    "interval_seconds": {
                        "type": "integer",
                        "description": "Interval in seconds. For schedule_type=interval.",
                    },
                    "action": {
                        "type": "string",
                        "description": "Shell command or message to execute/send when triggered.",
                    },
                },
                "required": ["job_id", "description", "schedule_type", "action"],
            },
        }

    async def execute(
        self,
        job_id: str,
        description: str,
        schedule_type: str,
        action: str,
        cron_expression: str = None,
        interval_seconds: int = None,
    ) -> str:
        scheduler = get_scheduler()

        async def job_func():
            logger.info(f"Cron job fired: {job_id} — {action}")

        try:
            if schedule_type == "cron" and cron_expression:
                parts = cron_expression.split()
                trigger = CronTrigger(
                    minute=parts[0] if len(parts) > 0 else "*",
                    hour=parts[1] if len(parts) > 1 else "*",
                    day=parts[2] if len(parts) > 2 else "*",
                    month=parts[3] if len(parts) > 3 else "*",
                    day_of_week=parts[4] if len(parts) > 4 else "*",
                )
            elif schedule_type == "interval" and interval_seconds:
                trigger = IntervalTrigger(seconds=interval_seconds)
            else:
                return "Error: Provide cron_expression for cron type or interval_seconds for interval type."

            scheduler.add_job(job_func, trigger, id=job_id, replace_existing=True)
            _job_actions[job_id] = {"action": action, "description": description}

            return f"✅ Cron job created: **{job_id}** — {description}\nSchedule: {schedule_type} ({cron_expression or f'{interval_seconds}s'})"
        except Exception as e:
            return f"Error creating cron job: {e}"


class CronListTool(Tool):
    name = "cron_list"
    description = "List all scheduled cron jobs."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self) -> str:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        if not jobs:
            return "No cron jobs scheduled."

        lines = ["**Scheduled Jobs:**"]
        for job in jobs:
            info = _job_actions.get(job.id, {})
            lines.append(
                f"- **{job.id}**: {info.get('description', 'N/A')} "
                f"(next: {job.next_run_time})"
            )
        return "\n".join(lines)


class CronRemoveTool(Tool):
    name = "cron_remove"
    description = "Remove a scheduled cron job by its ID."

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID of the job to remove"},
                },
                "required": ["job_id"],
            },
        }

    async def execute(self, job_id: str) -> str:
        scheduler = get_scheduler()
        try:
            scheduler.remove_job(job_id)
            _job_actions.pop(job_id, None)
            return f"✅ Job **{job_id}** removed."
        except Exception as e:
            return f"Error: {e}"


def get_cron_tools() -> list[Tool]:
    return [CronCreateTool(), CronListTool(), CronRemoveTool()]

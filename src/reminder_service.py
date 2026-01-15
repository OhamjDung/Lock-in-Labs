"""Reminder service for sending scheduled email reminders to users."""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
import logging

from src.email_service import EmailService
from src.storage import load_profile
from src.models import CharacterSheet, SkillTree, DailyTaskStatus
from src.reporting.scheduler import get_todays_tasks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReminderService:
    """Service for managing and sending email reminders."""
    
    def __init__(self, email_service: Optional[EmailService] = None):
        """Initialize reminder service with email service."""
        self.email_service = email_service or EmailService()
        # Track last sent time per user to avoid duplicates
        self.last_sent: Dict[str, Dict[str, str]] = {}  # {user_id: {"morning": "2024-01-01", "evening": "2024-01-01"}}
    
    def get_user_tasks(self, user_id: str, target_date: Optional[str] = None) -> List[dict]:
        """
        Retrieve today's tasks for a user.
        
        Args:
            user_id: User ID
            target_date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            List of task dictionaries
        """
        try:
            profile_data = load_profile(user_id)
            if not profile_data:
                return []
            
            sheet_data = profile_data.get("character_sheet", {})
            tree_data = profile_data.get("skill_tree", {})
            
            if not sheet_data or not tree_data:
                return []
            
            sheet = CharacterSheet(**sheet_data)
            tree = SkillTree(**tree_data)
            
            if target_date is None:
                target_date = date.today().isoformat()
            
            tasks = get_todays_tasks(sheet, tree, current_date=target_date)
            
            # Convert to dict format for email
            return [{
                "name": task.name,
                "pillar": task.pillar,
                "node_id": task.node_id,
            } for task in tasks]
            
        except Exception as e:
            logger.error(f"Error getting tasks for user {user_id}: {e}")
            return []
    
    def get_user_schedule(self, user_id: str, target_date: Optional[str] = None) -> List[dict]:
        """
        Retrieve today's schedule for a user.
        
        Args:
            user_id: User ID
            target_date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            List of schedule item dictionaries
        """
        try:
            profile_data = load_profile(user_id)
            if not profile_data:
                return []
            
            sheet_data = profile_data.get("character_sheet", {})
            if not sheet_data:
                return []
            
            sheet = CharacterSheet(**sheet_data)
            
            if target_date is None:
                target_date = date.today().isoformat()
            
            schedule = sheet.daily_schedule.get(target_date, [])
            
            # Convert to dict format
            return [{
                "time": item.time,
                "label": item.label,
                "name": item.label,
                "node_id": item.node_id,
            } for item in schedule]
            
        except Exception as e:
            logger.error(f"Error getting schedule for user {user_id}: {e}")
            return []
    
    def get_user_progress(self, user_id: str, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve today's progress for a user.
        
        Args:
            user_id: User ID
            target_date: Optional date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Dictionary with completed_tasks, total_tasks, xp_gained
        """
        try:
            profile_data = load_profile(user_id)
            if not profile_data:
                return {"completed_tasks": 0, "total_tasks": 0, "xp_gained": 0}
            
            sheet_data = profile_data.get("character_sheet", {})
            if not sheet_data:
                return {"completed_tasks": 0, "total_tasks": 0, "xp_gained": 0}
            
            sheet = CharacterSheet(**sheet_data)
            
            if target_date is None:
                target_date = date.today().isoformat()
            
            # Find today's report
            today_report = None
            for report in sheet.daily_reports:
                if report.date == target_date:
                    today_report = report
                    break
            
            if not today_report:
                # No report yet, check tasks
                tasks = self.get_user_tasks(user_id, target_date)
                return {
                    "completed_tasks": 0,
                    "total_tasks": len(tasks),
                    "xp_gained": 0
                }
            
            # Count completed tasks
            completed = sum(
                1 for task in today_report.tasks
                if task.status in [DailyTaskStatus.DONE, DailyTaskStatus.PARTIAL]
            )
            total = len(today_report.tasks)
            xp_gained = today_report.stats_delta.xp_total if today_report.stats_delta else 0
            
            return {
                "completed_tasks": completed,
                "total_tasks": total,
                "xp_gained": xp_gained
            }
            
        except Exception as e:
            logger.error(f"Error getting progress for user {user_id}: {e}")
            return {"completed_tasks": 0, "total_tasks": 0, "xp_gained": 0}
    
    def get_reminder_time(self, user_id: str, reminder_type: str, day_name: str) -> Optional[str]:
        """
        Get reminder time for a user for a specific day and reminder type.
        
        Args:
            user_id: User ID
            reminder_type: 'morning' or 'evening'
            day_name: Day of week (lowercase: 'monday', 'tuesday', etc.)
            
        Returns:
            Time string (HH:MM) or None if not set
        """
        try:
            profile_data = load_profile(user_id)
            if not profile_data:
                return None
            
            sheet_data = profile_data.get("character_sheet", {})
            if not sheet_data:
                return None
            
            sheet = CharacterSheet(**sheet_data)
            
            if not sheet.reminder_preferences:
                # Default times
                return "08:00" if reminder_type == "morning" else "20:00"
            
            prefs = sheet.reminder_preferences
            if reminder_type not in prefs:
                return "08:00" if reminder_type == "morning" else "20:00"
            
            day_prefs = prefs[reminder_type]
            return day_prefs.get(day_name.lower(), None)
            
        except Exception as e:
            logger.error(f"Error getting reminder time for user {user_id}: {e}")
            return None
    
    def should_send_reminder(self, user_id: str, reminder_type: str, current_time: datetime) -> bool:
        """
        Check if reminder should be sent for user at current time.
        
        Args:
            user_id: User ID
            reminder_type: 'morning' or 'evening'
            current_time: Current datetime
            
        Returns:
            True if reminder should be sent
        """
        try:
            # Get day name
            day_name = current_time.strftime("%A").lower()
            
            # Get reminder time
            reminder_time_str = self.get_reminder_time(user_id, reminder_type, day_name)
            if not reminder_time_str:
                return False
            
            # Parse reminder time
            hour, minute = map(int, reminder_time_str.split(":"))
            
            # Check if current time matches (within 5 minute tolerance)
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            # Check if we already sent today
            today_str = current_time.strftime("%Y-%m-%d")
            last_sent_date = self.last_sent.get(user_id, {}).get(reminder_type)
            if last_sent_date == today_str:
                return False
            
            # Check if time matches (within 5 minute window)
            time_diff = abs((current_hour * 60 + current_minute) - (hour * 60 + minute))
            if time_diff <= 5:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if reminder should be sent for user {user_id}: {e}")
            return False
    
    def send_morning_reminders(self, current_time: Optional[datetime] = None) -> int:
        """
        Send morning reminders to all users who should receive them.
        
        Args:
            current_time: Optional datetime to use (defaults to now)
            
        Returns:
            Number of reminders sent
        """
        if current_time is None:
            current_time = datetime.now()
        
        users = self.email_service.get_all_user_emails()
        sent_count = 0
        
        for user in users:
            user_id = user["user_id"]
            email = user["email"]
            username = user.get("username")
            
            try:
                # Check if should send
                if not self.should_send_reminder(user_id, "morning", current_time):
                    continue
                
                # Get user's tasks and schedule
                tasks = self.get_user_tasks(user_id)
                schedule = self.get_user_schedule(user_id)
                
                # Send email
                success = self.email_service.send_morning_reminder(
                    to_email=email,
                    username=username,
                    tasks=tasks,
                    schedule=schedule
                )
                
                if success:
                    # Track that we sent
                    if user_id not in self.last_sent:
                        self.last_sent[user_id] = {}
                    self.last_sent[user_id]["morning"] = current_time.strftime("%Y-%m-%d")
                    sent_count += 1
                    logger.info(f"Sent morning reminder to {email} (user {user_id})")
                else:
                    logger.warning(f"Failed to send morning reminder to {email} (user {user_id})")
                    
            except Exception as e:
                logger.error(f"Error sending morning reminder to user {user_id}: {e}")
                continue
        
        return sent_count
    
    def send_evening_reminders(self, current_time: Optional[datetime] = None) -> int:
        """
        Send evening reminders to all users who should receive them.
        
        Args:
            current_time: Optional datetime to use (defaults to now)
            
        Returns:
            Number of reminders sent
        """
        if current_time is None:
            current_time = datetime.now()
        
        users = self.email_service.get_all_user_emails()
        sent_count = 0
        
        for user in users:
            user_id = user["user_id"]
            email = user["email"]
            username = user.get("username")
            
            try:
                # Check if should send
                if not self.should_send_reminder(user_id, "evening", current_time):
                    continue
                
                # Get user's progress
                progress = self.get_user_progress(user_id)
                
                # Send email
                success = self.email_service.send_progress_report(
                    to_email=email,
                    username=username,
                    completed_tasks=progress["completed_tasks"],
                    total_tasks=progress["total_tasks"],
                    xp_gained=progress["xp_gained"]
                )
                
                if success:
                    # Track that we sent
                    if user_id not in self.last_sent:
                        self.last_sent[user_id] = {}
                    self.last_sent[user_id]["evening"] = current_time.strftime("%Y-%m-%d")
                    sent_count += 1
                    logger.info(f"Sent evening reminder to {email} (user {user_id})")
                else:
                    logger.warning(f"Failed to send evening reminder to {email} (user {user_id})")
                    
            except Exception as e:
                logger.error(f"Error sending evening reminder to user {user_id}: {e}")
                continue
        
        return sent_count
"""Scheduler for email reminders using APScheduler."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
import atexit

from src.reminder_service import ReminderService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Manages scheduled email reminders."""
    
    def __init__(self, reminder_service: ReminderService):
        """Initialize scheduler with reminder service."""
        self.reminder_service = reminder_service
        self.scheduler = BackgroundScheduler()
        self.is_running = False
    
    def start(self):
        """Start the scheduler and add reminder jobs."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            # Add job to check for morning reminders every hour
            self.scheduler.add_job(
                func=self._check_morning_reminders,
                trigger=CronTrigger(minute=0),  # Run at the top of every hour
                id='morning_reminders',
                name='Check and send morning reminders',
                replace_existing=True
            )
            
            # Add job to check for evening reminders every hour
            self.scheduler.add_job(
                func=self._check_evening_reminders,
                trigger=CronTrigger(minute=0),  # Run at the top of every hour
                id='evening_reminders',
                name='Check and send evening reminders',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Reminder scheduler started")
            
            # Register shutdown handler
            atexit.register(self.shutdown)
            
        except Exception as e:
            logger.error(f"Failed to start reminder scheduler: {e}")
            raise
    
    def _check_morning_reminders(self):
        """Check and send morning reminders."""
        try:
            current_time = datetime.now()
            count = self.reminder_service.send_morning_reminders(current_time)
            if count > 0:
                logger.info(f"Sent {count} morning reminder(s)")
        except Exception as e:
            logger.error(f"Error in morning reminder job: {e}")
    
    def _check_evening_reminders(self):
        """Check and send evening reminders."""
        try:
            current_time = datetime.now()
            count = self.reminder_service.send_evening_reminders(current_time)
            if count > 0:
                logger.info(f"Sent {count} evening reminder(s)")
        except Exception as e:
            logger.error(f"Error in evening reminder job: {e}")
    
    def shutdown(self):
        """Shutdown the scheduler gracefully."""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Reminder scheduler shut down")
        except Exception as e:
            logger.error(f"Error shutting down reminder scheduler: {e}")
    
    def get_jobs(self):
        """Get list of scheduled jobs."""
        return self.scheduler.get_jobs()
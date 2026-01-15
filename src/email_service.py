"""Email service for sending reminders and reports to users.

Uses SMTP to send emails with morning reminders and evening progress reports.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

from src.firebase_client import get_firestore_client

# Load environment variables
load_dotenv()


class EmailService:
    """Service for sending emails to users."""
    
    def __init__(self):
        """Initialize email service with SMTP configuration from environment."""
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.from_email = self.smtp_user
        
        if not self.smtp_user or not self.smtp_password:
            raise ValueError(
                "SMTP_USER and SMTP_PASSWORD must be set in environment variables"
            )
    
    def _send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> bool:
        """
        Send an email to a recipient.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_text: Plain text email body
            body_html: Optional HTML email body
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            
            # Add text and HTML parts
            text_part = MIMEText(body_text, "plain")
            msg.attach(text_part)
            
            if body_html:
                html_part = MIMEText(body_html, "html")
                msg.attach(html_part)
            
            # Connect to SMTP server and send
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            print(f"✓ Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to send email to {to_email}: {e}")
            return False
    
    def send_morning_reminder(
        self,
        to_email: str,
        username: Optional[str] = None,
        tasks: Optional[List[dict]] = None,
        schedule: Optional[List[dict]] = None
    ) -> bool:
        """
        Send a morning reminder email to check tasks.
        
        Args:
            to_email: Recipient email address
            username: Optional username to personalize the email
            tasks: Optional list of today's tasks (dict with 'name', 'pillar', etc.)
            schedule: Optional list of schedule items (dict with 'time', 'label', etc.)
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        display_name = username or to_email.split("@")[0]
        current_date = datetime.now().strftime("%B %d, %Y")
        
        subject = f"🌅 Good Morning! Time to Check Your Tasks - {current_date}"
        
        # Build tasks section
        tasks_section = ""
        if tasks and len(tasks) > 0:
            tasks_section = "\n\nToday's Tasks:\n"
            for task in tasks[:10]:  # Limit to 10 tasks
                task_name = task.get('name', 'Task')
                pillar = task.get('pillar', {}).get('value', '') if isinstance(task.get('pillar'), dict) else str(task.get('pillar', ''))
                tasks_section += f"  • {task_name}"
                if pillar:
                    tasks_section += f" ({pillar})"
                tasks_section += "\n"
            if len(tasks) > 10:
                tasks_section += f"  ... and {len(tasks) - 10} more tasks\n"
        else:
            tasks_section = "\n\nYou have no tasks scheduled for today. Check your app to see your schedule!"
        
        # Build schedule section
        schedule_section = ""
        if schedule and len(schedule) > 0:
            schedule_section = "\n\nToday's Schedule:\n"
            for item in schedule[:8]:  # Limit to 8 schedule items
                time_str = item.get('time', '')
                label = item.get('label', item.get('name', 'Task'))
                if time_str:
                    schedule_section += f"  {time_str} - {label}\n"
                else:
                    schedule_section += f"  • {label}\n"
            if len(schedule) > 8:
                schedule_section += f"  ... and {len(schedule) - 8} more items\n"
        
        body_text = f"""Good morning, {display_name}!

It's a new day ({current_date}), and it's time to check in with your tasks and goals.{tasks_section}{schedule_section}

Take a moment to review what you have planned for today and get started on your journey to level up your life!

Stay focused, stay motivated, and make today count!

Best regards,
Lock In Labs Team
"""
        
        # Build HTML version
        tasks_html = ""
        if tasks and len(tasks) > 0:
            tasks_html = "<h3 style='color: #4a5568; margin-top: 20px;'>Today's Tasks:</h3><ul style='list-style-type: none; padding-left: 0;'>"
            for task in tasks[:10]:
                task_name = task.get('name', 'Task')
                pillar = task.get('pillar', {}).get('value', '') if isinstance(task.get('pillar'), dict) else str(task.get('pillar', ''))
                tasks_html += f"<li style='margin: 8px 0;'>• {task_name}"
                if pillar:
                    tasks_html += f" <span style='color: #718096; font-size: 0.9em;'>({pillar})</span>"
                tasks_html += "</li>"
            if len(tasks) > 10:
                tasks_html += f"<li style='color: #718096; font-size: 0.9em;'>... and {len(tasks) - 10} more tasks</li>"
            tasks_html += "</ul>"
        else:
            tasks_html = "<p style='color: #718096;'>You have no tasks scheduled for today. Check your app to see your schedule!</p>"
        
        schedule_html = ""
        if schedule and len(schedule) > 0:
            schedule_html = "<h3 style='color: #4a5568; margin-top: 20px;'>Today's Schedule:</h3><ul style='list-style-type: none; padding-left: 0;'>"
            for item in schedule[:8]:
                time_str = item.get('time', '')
                label = item.get('label', item.get('name', 'Task'))
                if time_str:
                    schedule_html += f"<li style='margin: 8px 0;'><strong>{time_str}</strong> - {label}</li>"
                else:
                    schedule_html += f"<li style='margin: 8px 0;'>• {label}</li>"
            if len(schedule) > 8:
                schedule_html += f"<li style='color: #718096; font-size: 0.9em;'>... and {len(schedule) - 8} more items</li>"
            schedule_html += "</ul>"
        
        body_html = f"""<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h2 style="color: #4a5568;">🌅 Good Morning, {display_name}!</h2>
      <p>It's a new day ({current_date}), and it's time to check in with your tasks and goals.</p>
      {tasks_html}
      {schedule_html}
      <p style="font-weight: bold; color: #2d3748; margin-top: 20px;">Stay focused, stay motivated, and make today count!</p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
      <p style="color: #718096; font-size: 12px;">Best regards,<br>Lock In Labs Team</p>
    </div>
  </body>
</html>"""
        
        return self._send_email(to_email, subject, body_text, body_html)
    
    def send_progress_report(
        self,
        to_email: str,
        username: Optional[str] = None,
        completed_tasks: int = 0,
        total_tasks: int = 0,
        xp_gained: int = 0,
        progress_summary: Optional[str] = None
    ) -> bool:
        """
        Send an end-of-day progress report email.
        
        Args:
            to_email: Recipient email address
            username: Optional username to personalize the email
            completed_tasks: Number of tasks completed today
            total_tasks: Total number of tasks for today
            xp_gained: XP gained today
            progress_summary: Optional text summary of progress
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        display_name = username or to_email.split("@")[0]
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Calculate completion percentage
        completion_pct = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        subject = f"📊 Your Daily Progress Report - {current_date}"
        
        body_text = f"""Hello {display_name},

Here's your end-of-day progress report for {current_date}:

Tasks Completed: {completed_tasks} out of {total_tasks} ({completion_pct}%)
XP Gained: {xp_gained}
"""
        
        if progress_summary:
            body_text += f"\n{progress_summary}\n"
        
        body_text += """
Great work today! Don't forget to complete your daily report to track your progress.

See you tomorrow for another productive day!

Best regards,
Lock In Labs Team
"""
        
        body_html = f"""<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h2 style="color: #4a5568;">📊 Your Daily Progress Report</h2>
      <p>Hello {display_name},</p>
      <p>Here's your end-of-day progress report for <strong>{current_date}</strong>:</p>
      
      <div style="background-color: #f7fafc; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p style="margin: 5px 0;"><strong>Tasks Completed:</strong> {completed_tasks} out of {total_tasks} ({completion_pct}%)</p>
        <p style="margin: 5px 0;"><strong>XP Gained:</strong> {xp_gained}</p>
      </div>
"""
        
        if progress_summary:
            body_html += f'<p style="margin: 20px 0;">{progress_summary}</p>'
        
        body_html += """      <p style="font-weight: bold; color: #2d3748;">Great work today! Don't forget to complete your daily report to track your progress.</p>
      <p>See you tomorrow for another productive day!</p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
      <p style="color: #718096; font-size: 12px;">Best regards,<br>Lock In Labs Team</p>
    </div>
  </body>
</html>"""
        
        return self._send_email(to_email, subject, body_text, body_html)
    
    def get_user_email(self, user_id: str) -> Optional[str]:
        """
        Retrieve user email from Firestore.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            User email address if found, None otherwise
        """
        try:
            db = get_firestore_client()
            user_doc = db.collection("users").document(user_id).get()
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                return user_data.get("email")
            else:
                print(f"User {user_id} not found in Firestore")
                return None
                
        except Exception as e:
            print(f"Error retrieving user email: {e}")
            return None
    
    def get_all_user_emails(self) -> List[dict]:
        """
        Retrieve all user emails from Firestore.
        
        Returns:
            List of dictionaries with 'user_id' and 'email' keys
        """
        try:
            db = get_firestore_client()
            users_ref = db.collection("users")
            users = users_ref.stream()
            
            user_list = []
            for user_doc in users:
                user_data = user_doc.to_dict()
                email = user_data.get("email")
                if email:
                    user_list.append({
                        "user_id": user_doc.id,
                        "email": email,
                        "username": user_data.get("username", email.split("@")[0])
                    })
            
            return user_list
            
        except Exception as e:
            print(f"Error retrieving user emails: {e}")
            return []
"""Test script for email functionality.

This script tests sending emails to users for:
- Morning reminders to check their tasks
- End-of-day progress reports

Usage:
    python test_email.py

Environment variables needed:
    SMTP_HOST: SMTP server hostname (e.g., smtp.gmail.com)
    SMTP_PORT: SMTP server port (e.g., 587 for TLS, 465 for SSL)
    SMTP_USER: Email address to send from
    SMTP_PASSWORD: Password or app password for the email account
    SMTP_USE_TLS: Set to 'true' to use TLS (default: true)
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    
    def send_morning_reminder(self, to_email: str, username: Optional[str] = None) -> bool:
        """
        Send a morning reminder email to check tasks.
        
        Args:
            to_email: Recipient email address
            username: Optional username to personalize the email
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        display_name = username or to_email.split("@")[0]
        current_date = datetime.now().strftime("%B %d, %Y")
        
        subject = f"🌅 Good Morning! Time to Check Your Tasks - {current_date}"
        
        body_text = f"""Good morning, {display_name}!

It's a new day, and it's time to check in with your tasks and goals.

Take a moment to review what you have planned for today and get started on your journey to level up your life!

Stay focused, stay motivated, and make today count!

Best regards,
Lock In Labs Team
"""
        
        body_html = f"""<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
      <h2 style="color: #4a5568;">🌅 Good Morning, {display_name}!</h2>
      <p>It's a new day ({current_date}), and it's time to check in with your tasks and goals.</p>
      <p>Take a moment to review what you have planned for today and get started on your journey to level up your life!</p>
      <p style="font-weight: bold; color: #2d3748;">Stay focused, stay motivated, and make today count!</p>
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
        progress_summary: Optional[str] = None
    ) -> bool:
        """
        Send an end-of-day progress report email.
        
        Args:
            to_email: Recipient email address
            username: Optional username to personalize the email
            completed_tasks: Number of tasks completed today
            total_tasks: Total number of tasks for today
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
"""
        
        if progress_summary:
            body_text += f"\n{progress_summary}\n"
        
        body_text += """
Great work today! Keep up the momentum and continue working towards your goals.

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
      </div>
"""
        
        if progress_summary:
            body_html += f'<p style="margin: 20px 0;">{progress_summary}</p>'
        
        body_html += """      <p style="font-weight: bold; color: #2d3748;">Great work today! Keep up the momentum and continue working towards your goals.</p>
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


def test_email_sending():
    """Test function to send a test email."""
    print("=" * 70)
    print("EMAIL FUNCTIONALITY TEST")
    print("=" * 70)
    print()
    
    # Check if SMTP credentials are configured
    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASSWORD"):
        print("⚠️  SMTP credentials not configured!")
        print("Please set the following environment variables:")
        print("  - SMTP_HOST (default: smtp.gmail.com)")
        print("  - SMTP_PORT (default: 587)")
        print("  - SMTP_USER (your email address)")
        print("  - SMTP_PASSWORD (your email password or app password)")
        print("  - SMTP_USE_TLS (default: true)")
        print()
        print("You can create a .env file in the project root with these values.")
        return
    
    try:
        email_service = EmailService()
        print(f"✓ Email service initialized")
        print(f"  SMTP Host: {email_service.smtp_host}")
        print(f"  SMTP Port: {email_service.smtp_port}")
        print(f"  From: {email_service.from_email}")
        print()
        
        # Test: Send to a test email address
        test_email = input("Enter a test email address to send to: ").strip()
        
        if not test_email:
            print("No email address provided. Exiting.")
            return
        
        print()
        print("Choose test type:")
        print("1. Morning reminder")
        print("2. End-of-day progress report")
        print("3. Both")
        
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == "1" or choice == "3":
            print("\nSending morning reminder...")
            email_service.send_morning_reminder(test_email, "TestUser")
        
        if choice == "2" or choice == "3":
            print("\nSending progress report...")
            email_service.send_progress_report(
                test_email,
                "TestUser",
                completed_tasks=5,
                total_tasks=8,
                progress_summary="You completed 5 out of 8 tasks today. Great job staying focused!"
            )
        
        print()
        print("=" * 70)
        print("Test complete!")
        print("=" * 70)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_get_user_emails():
    """Test function to retrieve user emails from Firestore."""
    print("=" * 70)
    print("TEST: RETRIEVE USER EMAILS FROM FIRESTORE")
    print("=" * 70)
    print()
    
    try:
        email_service = EmailService()
        users = email_service.get_all_user_emails()
        
        if not users:
            print("No users found in Firestore.")
            return
        
        print(f"Found {len(users)} user(s) with email addresses:")
        print()
        for user in users:
            print(f"  User ID: {user['user_id']}")
            print(f"  Email: {user['email']}")
            print(f"  Username: {user.get('username', 'N/A')}")
            print()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        # List all users
        test_get_user_emails()
    else:
        # Test email sending
        test_email_sending()

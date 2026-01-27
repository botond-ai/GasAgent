"""
Infrastructure layer - SMTP email client implementation for Gmail.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SMTPEmailClient:
    """Client for sending emails via SMTP (Gmail)."""
    
    def __init__(self, username: str, app_password: str, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        """
        Initialize SMTP email client.
        
        Args:
            username: Gmail email address
            app_password: Gmail app password (not regular password)
            smtp_server: SMTP server address
            smtp_port: SMTP server port (587 for TLS)
        """
        self.username = username
        self.app_password = app_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        logger.info(f"SMTPEmailClient initialized for {username}")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        from_email: str = None,
        html_body: str = None
    ) -> Dict[str, Any]:
        """
        Send an email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            from_email: Sender email address (defaults to username)
            html_body: Optional HTML email body
        
        Returns:
            Dict with success status and message details
        """
        try:
            # Use username as from_email if not provided
            if not from_email:
                from_email = self.username
            
            # Create message container
            if html_body:
                message = MIMEMultipart('alternative')
                part1 = MIMEText(text_body, 'plain', 'utf-8')
                part2 = MIMEText(html_body, 'html', 'utf-8')
                message.attach(part1)
                message.attach(part2)
            else:
                message = MIMEText(text_body, 'plain', 'utf-8')
            
            # Set email headers
            message['From'] = from_email
            message['To'] = to_email
            message['Subject'] = subject
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Enable TLS encryption
                server.login(self.username, self.app_password)
                server.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}")
            
            return {
                "success": True,
                "message_id": f"smtp_{to_email}_{subject[:20]}",
                "message": "Email sent successfully via SMTP"
            }
        
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "status_code": 535
            }
        
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }

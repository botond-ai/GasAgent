"""
Infrastructure layer - Gmail API client implementation.
"""
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailClient:
    """Client for sending emails via Gmail API."""
    
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        """
        Initialize Gmail client.
        
        Args:
            client_id: Google OAuth2 client ID
            client_secret: Google OAuth2 client secret
            refresh_token: OAuth2 refresh token for Gmail API access
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        
        # Create credentials
        self.credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )
        
        # Build Gmail service
        try:
            self.service = build('gmail', 'v1', credentials=self.credentials)
            logger.info("GmailClient initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            raise
    
    def _create_message(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        from_email: str,
        html_body: str = None
    ) -> Dict[str, str]:
        """
        Create a message for an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            from_email: Sender email address
            html_body: Optional HTML email body
        
        Returns:
            Dict containing the base64url encoded email message
        """
        # Create message container
        if html_body:
            message = MIMEMultipart('alternative')
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            message.attach(part1)
            message.attach(part2)
        else:
            message = MIMEText(text_body, 'plain')
        
        message['to'] = to_email
        message['from'] = from_email
        message['subject'] = subject
        
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        return {'raw': raw_message}
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        from_email: str,
        html_body: str = None
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            from_email: Sender email address
            html_body: Optional HTML email body
        
        Returns:
            Dict with success status and message details
        """
        try:
            # Create message
            message = self._create_message(
                to_email=to_email,
                subject=subject,
                text_body=text_body,
                from_email=from_email,
                html_body=html_body
            )
            
            # Send message
            sent_message = self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            message_id = sent_message.get('id')
            logger.info(f"Email sent successfully to {to_email}: {message_id}")
            
            return {
                "success": True,
                "message_id": message_id,
                "message": "Email sent successfully"
            }
        
        except HttpError as error:
            error_msg = f"Gmail API error: {error.status_code} - {error.reason}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "status_code": error.status_code
            }
        
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }

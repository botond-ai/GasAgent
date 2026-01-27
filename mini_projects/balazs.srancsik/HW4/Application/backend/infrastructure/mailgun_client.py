"""
Infrastructure layer - Mailgun email client implementation.
"""
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class MailgunClient:
    """Client for sending emails via Mailgun API."""
    
    def __init__(self, api_key: str, domain: str, base_url: str = "https://api.mailgun.net"):
        """
        Initialize Mailgun client.
        
        Args:
            api_key: Mailgun API key
            domain: Mailgun domain (e.g., sandbox...mailgun.org)
            base_url: Mailgun API base URL
        """
        self.api_key = api_key
        self.domain = domain
        self.base_url = base_url
        self.api_endpoint = f"{base_url}/v3/{domain}/messages"
        logger.info(f"MailgunClient initialized with domain: {domain}")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        from_email: str = None,
        html_body: str = None
    ) -> Dict[str, Any]:
        """
        Send an email via Mailgun.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text email body
            from_email: Sender email address (defaults to noreply@domain)
            html_body: Optional HTML email body
        
        Returns:
            Dict with success status and message details
        """
        try:
            # Default from email if not provided
            if not from_email:
                from_email = f"noreply@{self.domain}"
            
            # Prepare email data
            data = {
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "text": text_body
            }
            
            # Add HTML body if provided
            if html_body:
                data["html"] = html_body
            
            # Send request to Mailgun API
            response = requests.post(
                self.api_endpoint,
                auth=("api", self.api_key),
                data=data,
                timeout=10
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Email sent successfully to {to_email}: {result.get('id')}")
                return {
                    "success": True,
                    "message_id": result.get("id"),
                    "message": result.get("message", "Email sent successfully")
                }
            else:
                error_msg = f"Failed to send email: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
        
        except requests.exceptions.Timeout:
            error_msg = "Email send timeout - Mailgun API did not respond"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Email send failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            error_msg = f"Unexpected error sending email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }

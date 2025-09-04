"""
Email Service Infrastructure Implementation - SES and SMTP Email Services.

This module provides concrete implementations of the email service interface
for different email backends (AWS SES, SMTP).
"""

import logging
import asyncio
import smtplib
from typing import List, Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import boto3
from botocore.exceptions import ClientError

from ..interfaces.infrastructure import IEmailService
from ..interfaces.base import ServiceResult
from ...core.config import get_settings

logger = logging.getLogger(__name__)


class SESEmailService(IEmailService):
    """AWS SES email service implementation."""
    
    def __init__(self, aws_config: Optional[Dict[str, Any]] = None):
        """Initialize SES email service with AWS configuration."""
        self.settings = get_settings()
        self.aws_config = aws_config or {}
        
        # Initialize SES client
        session = boto3.Session(
            aws_access_key_id=self.aws_config.get('access_key_id'),
            aws_secret_access_key=self.aws_config.get('secret_access_key'),
            region_name=self.aws_config.get('region', 'us-east-1')
        )
        self.ses_client = session.client('ses')
        
        self.default_sender = self.aws_config.get('default_sender', 'noreply@example.com')
        
    @property
    def service_name(self) -> str:
        return "SESEmailService"
    
    async def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_address: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> ServiceResult[str]:
        """Send email using AWS SES."""
        try:
            sender = from_address or self.default_sender
            
            # Prepare destination
            destination = {'ToAddresses': to_addresses}
            if cc_addresses:
                destination['CcAddresses'] = cc_addresses
            if bcc_addresses:
                destination['BccAddresses'] = bcc_addresses
            
            # Prepare message
            message = {
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {'Text': {'Data': body_text, 'Charset': 'UTF-8'}}
            }
            
            if body_html:
                message['Body']['Html'] = {'Data': body_html, 'Charset': 'UTF-8'}
            
            # Send email
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ses_client.send_email(
                    Source=sender,
                    Destination=destination,
                    Message=message
                )
            )
            
            message_id = response['MessageId']
            
            logger.info(f"Email sent successfully via SES: {message_id}")
            return ServiceResult.success(message_id)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES client error sending email: {error_code} - {error_message}")
            return ServiceResult.error(
                error=f"SES error: {error_message}",
                error_code=f"SES_{error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error sending email via SES: {e}")
            return ServiceResult.error(
                error=f"Email sending error: {str(e)}",
                error_code="EMAIL_SEND_ERROR"
            )
    
    async def send_template_email(
        self,
        to_addresses: List[str],
        template_name: str,
        template_data: Dict[str, Any],
        from_address: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> ServiceResult[str]:
        """Send templated email using AWS SES."""
        try:
            sender = from_address or self.default_sender
            
            # Prepare destination
            destination = {'ToAddresses': to_addresses}
            if cc_addresses:
                destination['CcAddresses'] = cc_addresses
            if bcc_addresses:
                destination['BccAddresses'] = bcc_addresses
            
            # Send templated email
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ses_client.send_templated_email(
                    Source=sender,
                    Destination=destination,
                    Template=template_name,
                    TemplateData=str(template_data)  # SES expects JSON string
                )
            )
            
            message_id = response['MessageId']
            
            logger.info(f"Template email sent successfully via SES: {message_id}")
            return ServiceResult.success(message_id)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES client error sending template email: {error_code} - {error_message}")
            return ServiceResult.error(
                error=f"SES template error: {error_message}",
                error_code=f"SES_TEMPLATE_{error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error sending template email via SES: {e}")
            return ServiceResult.error(
                error=f"Template email error: {str(e)}",
                error_code="TEMPLATE_EMAIL_ERROR"
            )
    
    async def verify_email_address(
        self,
        email_address: str
    ) -> ServiceResult[bool]:
        """Verify email address with SES."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.ses_client.verify_email_identity(EmailAddress=email_address)
            )
            
            logger.info(f"Email verification sent to: {email_address}")
            return ServiceResult.success(True)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES client error verifying email: {error_code} - {error_message}")
            return ServiceResult.error(
                error=f"SES verification error: {error_message}",
                error_code=f"SES_VERIFY_{error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error verifying email: {e}")
            return ServiceResult.error(
                error=f"Email verification error: {str(e)}",
                error_code="EMAIL_VERIFY_ERROR"
            )


class SMTPEmailService(IEmailService):
    """SMTP email service implementation."""
    
    def __init__(self, smtp_config: Dict[str, Any]):
        """Initialize SMTP email service with configuration."""
        self.smtp_config = smtp_config
        self.host = smtp_config.get('host', 'localhost')
        self.port = smtp_config.get('port', 587)
        self.username = smtp_config.get('username')
        self.password = smtp_config.get('password')
        self.use_tls = smtp_config.get('use_tls', True)
        self.default_sender = smtp_config.get('default_sender', 'noreply@example.com')
        
    @property
    def service_name(self) -> str:
        return "SMTPEmailService"
    
    async def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_address: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> ServiceResult[str]:
        """Send email using SMTP."""
        try:
            sender = from_address or self.default_sender
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = ', '.join(to_addresses)
            
            if cc_addresses:
                msg['Cc'] = ', '.join(cc_addresses)
            
            # Add text part
            text_part = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Prepare recipients
            all_recipients = to_addresses.copy()
            if cc_addresses:
                all_recipients.extend(cc_addresses)
            if bcc_addresses:
                all_recipients.extend(bcc_addresses)
            
            # Send email
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp_email, msg, sender, all_recipients)
            
            message_id = msg.get('Message-ID', 'unknown')
            
            logger.info(f"Email sent successfully via SMTP to {len(all_recipients)} recipients")
            return ServiceResult.success(message_id)
            
        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}")
            return ServiceResult.error(
                error=f"SMTP email error: {str(e)}",
                error_code="SMTP_SEND_ERROR"
            )
    
    def _send_smtp_email(self, msg: MIMEMultipart, sender: str, recipients: List[str]) -> None:
        """Send email via SMTP (synchronous helper)."""
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            
            if self.username and self.password:
                server.login(self.username, self.password)
            
            server.send_message(msg, sender, recipients)
    
    async def send_template_email(
        self,
        to_addresses: List[str],
        template_name: str,
        template_data: Dict[str, Any],
        from_address: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> ServiceResult[str]:
        """Send templated email using SMTP (basic template substitution)."""
        try:
            # For SMTP, we'll implement basic template substitution
            # In a real implementation, you'd use a template engine like Jinja2
            
            # This is a simplified implementation
            template_text = self._get_email_template(template_name, 'text')
            template_html = self._get_email_template(template_name, 'html')
            
            # Simple variable substitution
            body_text = template_text
            body_html = template_html
            subject = template_data.get('subject', 'Notification')
            
            for key, value in template_data.items():
                placeholder = f"{{{{{key}}}}}"
                if body_text:
                    body_text = body_text.replace(placeholder, str(value))
                if body_html:
                    body_html = body_html.replace(placeholder, str(value))
            
            return await self.send_email(
                to_addresses=to_addresses,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_address=from_address,
                cc_addresses=cc_addresses,
                bcc_addresses=bcc_addresses
            )
            
        except Exception as e:
            logger.error(f"Error sending template email via SMTP: {e}")
            return ServiceResult.error(
                error=f"SMTP template email error: {str(e)}",
                error_code="SMTP_TEMPLATE_ERROR"
            )
    
    def _get_email_template(self, template_name: str, format_type: str) -> Optional[str]:
        """Get email template content (placeholder implementation)."""
        # In a real implementation, this would load templates from files or database
        templates = {
            'welcome': {
                'text': 'Welcome {{name}}! Thank you for joining us.',
                'html': '<h1>Welcome {{name}}!</h1><p>Thank you for joining us.</p>'
            },
            'job_completion': {
                'text': 'Your job {{job_id}} has completed successfully.',
                'html': '<h2>Job Completed</h2><p>Your job <strong>{{job_id}}</strong> has completed successfully.</p>'
            },
            'job_failure': {
                'text': 'Your job {{job_id}} has failed. Error: {{error}}',
                'html': '<h2>Job Failed</h2><p>Your job <strong>{{job_id}}</strong> has failed.</p><p>Error: {{error}}</p>'
            }
        }
        
        return templates.get(template_name, {}).get(format_type)
    
    async def verify_email_address(
        self,
        email_address: str
    ) -> ServiceResult[bool]:
        """Verify email address (not supported by basic SMTP)."""
        logger.warning("Email verification not supported by SMTP service")
        return ServiceResult.error(
            error="Email verification not supported by SMTP",
            error_code="SMTP_VERIFY_NOT_SUPPORTED"
        )


class ConsoleEmailService(IEmailService):
    """Console email service for development and testing."""
    
    @property
    def service_name(self) -> str:
        return "ConsoleEmailService"
    
    async def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_address: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> ServiceResult[str]:
        """Print email to console instead of sending."""
        message_id = f"console_{asyncio.get_event_loop().time()}"
        
        print("=" * 60)
        print("📧 EMAIL (Console Mode)")
        print("=" * 60)
        print(f"From: {from_address or 'noreply@example.com'}")
        print(f"To: {', '.join(to_addresses)}")
        if cc_addresses:
            print(f"Cc: {', '.join(cc_addresses)}")
        if bcc_addresses:
            print(f"Bcc: {', '.join(bcc_addresses)}")
        print(f"Subject: {subject}")
        print("-" * 60)
        print("TEXT BODY:")
        print(body_text)
        if body_html:
            print("-" * 60)
            print("HTML BODY:")
            print(body_html)
        print("=" * 60)
        
        return ServiceResult.success(message_id)
    
    async def send_template_email(
        self,
        to_addresses: List[str],
        template_name: str,
        template_data: Dict[str, Any],
        from_address: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        bcc_addresses: Optional[List[str]] = None
    ) -> ServiceResult[str]:
        """Print template email to console."""
        message_id = f"console_template_{asyncio.get_event_loop().time()}"
        
        print("=" * 60)
        print("📧 TEMPLATE EMAIL (Console Mode)")
        print("=" * 60)
        print(f"Template: {template_name}")
        print(f"From: {from_address or 'noreply@example.com'}")
        print(f"To: {', '.join(to_addresses)}")
        if cc_addresses:
            print(f"Cc: {', '.join(cc_addresses)}")
        if bcc_addresses:
            print(f"Bcc: {', '.join(bcc_addresses)}")
        print("-" * 60)
        print("TEMPLATE DATA:")
        for key, value in template_data.items():
            print(f"  {key}: {value}")
        print("=" * 60)
        
        return ServiceResult.success(message_id)
    
    async def verify_email_address(
        self,
        email_address: str
    ) -> ServiceResult[bool]:
        """Print verification request to console."""
        print("=" * 60)
        print("📧 EMAIL VERIFICATION (Console Mode)")
        print("=" * 60)
        print(f"Verification requested for: {email_address}")
        print("=" * 60)
        
        return ServiceResult.success(True)

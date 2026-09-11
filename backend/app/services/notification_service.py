import os
from ..logger import get_logger

# To use real WhatsApp, you would run: `pip install twilio`
# from twilio.rest import Client 

logger = get_logger(__name__)

class NotificationService:
    """
    Acts as the 'Notification Engine'. 
    Current Status: SIMULATION MODE (Prints to console).
    
    To enable Real WhatsApp:
    1. Sign up for Twilio (twilio.com)
    2. Get Account SID, Auth Token, and a Sender Number.
    3. Set environment variables: TWILIO_SID, TWILIO_TOKEN
    """
    
    def __init__(self):
        # self.client = Client(os.environ.get("TWILIO_SID"), os.environ.get("TWILIO_TOKEN"))
        self.sender_number = "whatsapp:+14155238886" # This is Twilio's Sandbox Number
        pass

    def send_whatsapp_alert(self, to_number: str, message: str):
        """
        In production, the 'Sender' is a paid business number you rent from Twilio.
        For testing, it is the Twilio Sandbox Number.
        """
        try:
            # --- REAL WORLD CODE (Commented Out) ---
            # message = self.client.messages.create(
            #     from_=self.sender_number,
            #     body=message,
            #     to=f"whatsapp:{to_number}"
            # )
            # return message.sid
            
            # --- SIMULATION CODE ---
            logger.info(f"📱 [WhatsApp SIMULATION] From: {self.sender_number} -> To: {to_number}")
            logger.info(f"   Message: {message}")
            return True
        except Exception as e:
            logger.error(f"Error sending WhatsApp: {e}")
            return False

    def send_email_alert(self, to_email: str, subject: str, message: str):
        # Placeholder for SMTP logic
        logger.info(f"📧 [Email Sent] To: {to_email} | Subject: {subject} | Body: {message}")
        return True

    def notify_admin(self, title: str, message: str, severity: str = "info"):
        """
        Routing logic: High severity -> WhatsApp, Medium -> Email
        """
        logger.info(f"🔔 [System Notification] {title}: {message} (Severity: {severity})")
        
        if severity == "high":
            # Example: Critical stockout or sudden drop
            self.send_whatsapp_alert("+123456789", f"🚨 {title}: {message}")
        elif severity == "medium":
            # Example: Low stock warning
            self.send_email_alert("admin@store.com", f"⚠️ {title}", message)

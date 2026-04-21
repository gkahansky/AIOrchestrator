from datetime import datetime, timezone, timedelta
from typing import Any
from aiplatform.database.session import db_session_context
from aiplatform.database.models import Contact, ContactMessage
from sqlalchemy import select

def log_contact_message(
    email: str,
    venture: str,
    message_type: str,
    subject: str,
    body_snippet: str | None = None,
    message_id: str | None = None,
) -> None:
    """Upserts the contact and logs the email message."""
    with db_session_context() as db:
        # Convert email to lowercase so they are unique
        clean_email = email.strip().lower()
        contact = db.execute(select(Contact).filter(Contact.email == clean_email)).scalar_first()

        if not contact:
            # Create contact if it does not exist
            contact = Contact(email=clean_email)
            db.add(contact)
            db.flush()
        
        # Track ventures approached
        if venture not in contact.ventures_approached:
            # Reassign so JSONB updates correctly
            updated_ventures = list(contact.ventures_approached)
            updated_ventures.append(venture)
            contact.ventures_approached = updated_ventures
        
        contact.last_activity_at = datetime.now(timezone.utc)

        # Create message record
        msg = ContactMessage(
            contact_id=contact.id,
            venture=venture,
            message_type=message_type,
            subject=subject,
            body_snippet=body_snippet,
            message_id=message_id,
        )
        db.add(msg)
        db.commit()

def can_send_sample(email: str, venture: str, days: int = 30) -> bool:
    """Checks if a contact was sent a sample email for this venture within the last `days` days."""
    with db_session_context() as db:
        clean_email = email.strip().lower()
        contact = db.execute(select(Contact).filter(Contact.email == clean_email)).scalar_first()
        if not contact:
            return True
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent_sample = db.execute(
            select(ContactMessage).filter(
                ContactMessage.contact_id == contact.id,
                ContactMessage.venture == venture,
                ContactMessage.message_type == "sample",
                ContactMessage.sent_at >= cutoff
            )
        ).scalar_first()
        
        if recent_sample:
            return False
            
    return True

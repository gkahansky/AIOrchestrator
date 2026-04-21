import sys

content = open('src/aiplatform/worker.py').read()

audit_find = '''        from aiplatform.skills.comms.send_email import send_email
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message
        from pathlib import Path

        if sample_email and not can_send_sample(sample_email, "marketing_audit"):'''

audit_replace = '''        from aiplatform.skills.comms.send_email import send_email
        from aiplatform.database.crm_ops import can_send_sample, log_contact_message
        from pathlib import Path

        if sample_email and not can_send_sample(sample_email, "marketing_audit"):
            return {
                "order_id": order.get("order_id"), 
                "status": "skipped_throttle", 
                "error": "Sample limit reached (30 days)"
            }'''

if audit_find not in content:
    content = content.replace(
        "from aiplatform.skills.comms.send_email import send_email\n        from aiplatform.database.crm_ops import can_send_sample, log_contact_message\n        from pathlib import Path\n\n        # Force sample-only mode",
        "from aiplatform.skills.comms.send_email import send_email\n        from aiplatform.database.crm_ops import can_send_sample, log_contact_message\n        from pathlib import Path\n\n        if sample_email and not can_send_sample(sample_email, \"marketing_audit\"):\n            return {\n                \"order_id\": order.get(\"order_id\"), \n                \"status\": \"skipped_throttle\", \n                \"error\": \"Sample limit reached (30 days)\"\n            }\n\n        # Force sample-only mode"
    )

podcast_replace1 = "from aiplatform.skills.comms.send_email import send_email\n        from aiplatform.database.crm_ops import can_send_sample, log_contact_message\n        from pathlib import Path\n\n        # Skip human review"
podcast_replace2 = "from aiplatform.skills.comms.send_email import send_email\n        from aiplatform.database.crm_ops import can_send_sample, log_contact_message\n        from pathlib import Path\n\n        if sample_email and not can_send_sample(sample_email, \"podcast_notes\"):\n            return {\n                \"order_id\": order.get(\"order_id\"), \n                \"status\": \"skipped_throttle\", \n                \"error\": \"Sample limit reached (30 days)\"\n            }\n\n        # Skip human review"

content = content.replace(podcast_replace1, podcast_replace2)

open('src/aiplatform/worker.py', 'w').write(content)
print("Updated worker.py")
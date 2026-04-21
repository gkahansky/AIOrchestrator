import sys

lines = open('src/aiplatform/worker.py', 'r', encoding='utf-8').readlines()

out = []
i = 0

while i < len(lines):
    line = lines[i]
    out.append(line)
    
    if 'raise RuntimeError(f"send_email failed: {result_send[\'error\']}")' in line:
        
        # Check if the preceding lines had "Your Free Marketing Audit" or "Your Free Podcast Sample"
        recent = "".join(lines[max(0, i-10):i])
        
        if "Your Free Marketing Audit Sample" in recent:
            out.append('''
            log_contact_message(
                email=sample_email,
                venture="marketing_audit",
                message_type="sample",
                subject=f"Your Free Marketing Audit Sample \u2014 {url}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )
''')
        elif "Your Free Podcast Sample" in recent:
            out.append('''
            log_contact_message(
                email=sample_email,
                venture="podcast_notes",
                message_type="sample",
                subject=f"Your Free Podcast Sample \u2014 {episode}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )
''')
    
    i += 1
    
open('src/aiplatform/worker.py', 'w', encoding='utf-8').writelines(out)
print("Done")
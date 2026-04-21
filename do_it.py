import sys
content = open('src/aiplatform/worker.py').read()

old_podcast = '''            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Podcast Sample â€” {episode}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):      
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            # Schedule nurture follow-ups'''

new_podcast = '''            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Podcast Sample â€” {episode}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):      
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            log_contact_message(
                email=sample_email,
                venture="podcast_notes",
                message_type="sample",
                subject=f"Your Free Podcast Sample â€” {episode}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )

            # Schedule nurture follow-ups'''
if old_podcast in content:
    content = content.replace(old_podcast, new_podcast)
    open('src/aiplatform/worker.py', 'w').write(content)
    print('replaced podcast')
else:
    print('podcast old block not found')

old_audit = '''            # Attach PDF if local file is still available; fall back to link-only
            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Marketing Audit Sample â€” {url}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):      
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            # Schedule nurture follow-ups'''

new_audit = '''            # Attach PDF if local file is still available; fall back to link-only
            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Marketing Audit Sample â€” {url}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):      
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            log_contact_message(
                email=sample_email,
                venture="marketing_audit",
                message_type="sample",
                subject=f"Your Free Marketing Audit Sample â€” {url}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )

            # Schedule nurture follow-ups'''
if old_audit in content:
    content = content.replace(old_audit, new_audit)
    open('src/aiplatform/worker.py', 'w').write(content)
    print('replaced audit')
else:
    print('audit old block not found')
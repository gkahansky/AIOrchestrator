import re

content = open('src/aiplatform/worker.py').read()

audit_pattern = r'''            attachments = \[sample_pdf\] if \(sample_pdf and Path\(sample_pdf\)\.exists\(\)\) else \[\]
            result_send = send_email\(
                to=sample_email,
                subject=f"Your Free Marketing Audit Sample .{1,10} \{url\}",
                body_html=body,
                attachments=attachments,
            \)
            if isinstance\(result_send, dict\) and result_send\.get\("error"\):
                raise RuntimeError\(f"send_email failed: \{result_send\['error'\]\}"\)

            # Schedule nurture follow-ups'''

audit_replacement = r'''            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Marketing Audit Sample \u2014 {url}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            log_contact_message(
                email=sample_email,
                venture="marketing_audit",
                message_type="sample",
                subject=f"Your Free Marketing Audit Sample \u2014 {url}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )

            # Schedule nurture follow-ups'''

content = re.sub(audit_pattern, audit_replacement, content)

podcast_pattern = r'''            attachments = \[sample_pdf\] if \(sample_pdf and Path\(sample_pdf\)\.exists\(\)\) else \[\]
            result_send = send_email\(
                to=sample_email,
                subject=f"Your Free Podcast Sample .{1,10} \{episode\}",
                body_html=body,
                attachments=attachments,
            \)
            if isinstance\(result_send, dict\) and result_send\.get\("error"\):
                raise RuntimeError\(f"send_email failed: \{result_send\['error'\]\}"\)

            # Schedule nurture follow-ups'''

podcast_replacement = r'''            attachments = [sample_pdf] if (sample_pdf and Path(sample_pdf).exists()) else []
            result_send = send_email(
                to=sample_email,
                subject=f"Your Free Podcast Sample \u2014 {episode}",
                body_html=body,
                attachments=attachments,
            )
            if isinstance(result_send, dict) and result_send.get("error"):
                raise RuntimeError(f"send_email failed: {result_send['error']}")

            log_contact_message(
                email=sample_email,
                venture="podcast_notes",
                message_type="sample",
                subject=f"Your Free Podcast Sample \u2014 {episode}",
                body_snippet=body[:200],
                message_id=result_send.get("message_id") if isinstance(result_send, dict) else None
            )

            # Schedule nurture follow-ups'''

content = re.sub(podcast_pattern, podcast_replacement, content)

open('src/aiplatform/worker.py', 'w', encoding='utf-8').write(content)
print("Regex replace Done")
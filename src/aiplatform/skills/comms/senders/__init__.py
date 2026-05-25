"""
Send handlers — one module per delivery platform.

Each handler exposes a single function:
    send(req: SendRequest, config: dict) -> SendResult

Resolve a platform to its handler via the registry:
    from aiplatform.skills.comms.senders import HANDLERS
    result = HANDLERS["email"].send(req, config)

Email delivers now (Resend). Social platforms (linkedin/instagram/facebook) use
assisted send today and have a provider slot for a future native API. Adding a
platform means adding one handler file and one entry below.
"""
from aiplatform.skills.comms.senders import email, linkedin, instagram, facebook

HANDLERS = {
    "email":     email,
    "linkedin":  linkedin,
    "instagram": instagram,
    "facebook":  facebook,
}

VALID_SEND_PLATFORMS = set(HANDLERS.keys())

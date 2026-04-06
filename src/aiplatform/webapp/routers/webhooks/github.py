from fastapi import APIRouter, Request, BackgroundTasks, Header, HTTPException
import hmac
import hashlib
import os

router = APIRouter()

def verify_github_signature(payload: bytes, signature: str) -> bool:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        return False
    mac = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None)
):
    if not x_hub_signature_256:
        raise HTTPException(status_code=400, detail="Missing signature")
        
    payload = await request.body()
    if not verify_github_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    data = await request.json()
    action = data.get("action")
    
    if "pull_request" in data and action in ["opened", "synchronize"]:
        # Run Architect Advisor
        # background_tasks.add_task(run_advisor, "architect", data["pull_request"])
        pass
        
    return {"status": "accepted"}

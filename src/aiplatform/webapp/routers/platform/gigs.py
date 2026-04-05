from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from aiplatform.webapp.auth import require_auth
from aiplatform.skills.marketplace.generate_fiverr_gig import generate_gig
from aiplatform.skills.media.generate_image import generate_image
from aiplatform.skills.storage.drive_write import drive_write
import os

# We will import the venture configs from the CLI script for now.
# In the future these should live in ventures/{name}/config.py
import sys
repo_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent)
sys.path.append(repo_root)

try:
    from scripts.run_gig_generator import VENTURE_CONFIGS
except ImportError as e:
    print(f"Warning: Could not import VENTURE_CONFIGS: {e}")
    VENTURE_CONFIGS = {}

router = APIRouter()

class GigGenerationRequest(BaseModel):
    platform: str
    venture: str

class GigPackage(BaseModel):
    name: str
    price: int
    delivery_days: int
    revisions: int
    description: str
    features: list[str]

class GigFaq(BaseModel):
    question: str
    answer: str

class GigContentResponse(BaseModel):
    gig_title: str
    gig_description: str
    packages: list[GigPackage]
    faq: list[GigFaq]
    tags: list[str]
    image_url: Optional[str] = None
    output_path: str


@router.post("/generate", response_model=GigContentResponse)
def generate_gig_endpoint(
    req: GigGenerationRequest,
    _: str = Depends(require_auth),
) -> GigContentResponse:
    if req.platform.lower() != "fiverr":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform '{req.platform}' is not supported yet."
        )

    if req.venture not in VENTURE_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown venture '{req.venture}'. Known ones are {list(VENTURE_CONFIGS.keys())}."
        )

    config = VENTURE_CONFIGS[req.venture]

    # Generate the text content
    try:
        result = generate_gig(
            service_name=config["service_name"],
            service_description=config["service_description"],
            packages=config["packages"],
            target_audience=config["target_audience"],
            key_benefits=config["key_benefits"],
            keywords=config["keywords"],
            venture_name=req.venture,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate gig copy: {str(e)}")

    image_url = None
    image_prompt = result.get("image_prompt")

    # Generate cover image and upload to Drive if prompt exists
    if image_prompt:
        try:
            image_result = generate_image(
                prompt=image_prompt,
                aspect_ratio="16:9",
                quality_tier="standard",
                output_dir=Path(result["output_path"]).parent,
                filename=f"{Path(result['output_path']).stem}-cover"
            )
            
            # Since the frontend needs to download it, we put it in Google Drive root
            # Alternatively, we could serve it directly from the backend, but prompt says:
            # "Any images required will be stored in Google drive and a link will be provided to download locally."
            
            # Assuming you have a general drive folder or we just use root for these temporary image covers
            folder_id = "root"
            # It might be cleaner to just store it in the same drive folder as the venture, 
            # but we aren't loading venture configs here to get their drive ID. Let's just use root.
            # If there's a GOOGLE_DRIVE_ROOT_ID or something similar:
            # folder_id = os.environ.get("GOOGLE_DRIVE_ROOT_ID", "root")

            drive_resp = drive_write(
                local_path=image_result["image_path"],
                folder_id=folder_id,
                share_anyone_with_link=True
            )
            
            image_url = drive_resp.get("web_view_link")
            
        except Exception as e:
            # Do not completely fail the request if image generation or drive upload fails
            print(f"Warning: Image generation or upload failed: {str(e)}")


    return GigContentResponse(
        gig_title=result["gig_title"],
        gig_description=result["gig_description"],
        packages=result["packages"],
        faq=result["faq"],
        tags=result["tags"],
        image_url=image_url,
        output_path=result["output_path"]
    )

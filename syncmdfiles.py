import os
import sys
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add src to sys.path to allow importing platform skills
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from aiplatform.skills.storage.drive_organise import create_folder
from aiplatform.skills.storage.drive_write import drive_write

def backup_md_files():
    load_dotenv()
    
    # Ensure local token is used if it exists in the root, overriding .ENV
    if Path("google_token.json").exists():
        os.environ["GOOGLE_TOKEN_PATH"] = str(Path("google_token.json").resolve())
    
    drive_root_id = os.getenv("DRIVE_MD_ROOT_ID")
    md_folders = posix_list(os.getenv("DRIVE_MD_FOLDERS", ""))
    root_files = posix_list(os.getenv("Drive_MD_ROOT_FILES", ""))
    
    if not drive_root_id:
        print("Missing DRIVE_MD_ROOT_ID in environment variables.")
        return

    base_dir = Path(__file__).resolve().parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"Creating Drive folder: {timestamp} under {drive_root_id}")
    folder_result = create_folder(name=timestamp, parent_id=drive_root_id)
    new_folder_id = folder_result["folder_id"]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # 1 & 2: Process folder paths and append folder name
        for folder_name in md_folders:
            folder_path = base_dir / folder_name
            if not folder_path.exists() or not folder_path.is_dir():
                continue
                
            for md_file in folder_path.rglob("*.md"):
                if md_file.name.lower() != "claude.md":
                    continue
                parent_name = md_file.parent.name
                new_filename = f"{md_file.stem}_{parent_name}{md_file.suffix}"
                temp_file_path = temp_dir_path / new_filename
                shutil.copy2(md_file, temp_file_path)
                
                print(f"Uploading nested file: {new_filename}")
                drive_write(local_path=str(temp_file_path), folder_id=new_folder_id)

        # 3: Process root files
        for root_file in root_files:
            file_path = base_dir / root_file
            if file_path.exists() and file_path.is_file():
                temp_file_path = temp_dir_path / file_path.name
                shutil.copy2(file_path, temp_file_path)
                
                print(f"Uploading root file: {file_path.name}")
                drive_write(local_path=str(temp_file_path), folder_id=new_folder_id)

    print("Backup completed successfully.")

def posix_list(value_str):
    if value_str:
        return [item.strip() for item in value_str.split(",") if item.strip()]
    return []

if __name__ == "__main__":
    backup_md_files()

import os
import json
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose():
    print("--- GOOGLE DRIVE DIAGNOSTIC ---")
    
    # 1. Load Credentials
    try:
        creds_json = os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON')
        if not creds_json:
            print("ERROR: GOOGLE_DRIVE_CREDENTIALS_JSON not found in env")
            return

        # Handle the case where it might be a string properly
        if creds_json.startswith('"') and creds_json.endswith('"'):
            creds_json = creds_json[1:-1]
        
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        print(f"Service Account Email: {creds.service_account_email}")
        
        service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"ERROR Loading Credentials: {e}")
        return

    # 2. Check Storage Quota
    try:
        about = service.about().get(fields="storageQuota,user").execute()
        quota = about.get('storageQuota', {})
        user = about.get('user', {})
        print(f"\n[Service Account Info]")
        print(f"Name: {user.get('displayName')}")
        print(f"Me: {user.get('me')}")
        print(f"Limit: {quota.get('limit')} bytes")
        print(f"Usage: {quota.get('usage')} bytes")
        
        if str(quota.get('limit')) == '0' or quota.get('limit') is None:
             print("WARNING: Service Account has 0 storage quota. It CANNOT own binary files.")
    except Exception as e:
        print(f"ERROR checking quota: {e}")

    # 3. Check Folder Access
    folder_id = os.getenv('GOOGLE_DRIVE_PHOTO_MEMORIES_FOLDER_ID')
    if not folder_id:
        # Try to find it by name
        try:
            results = service.files().list(
                q="name = 'Photo_Memories' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                fields="files(id, name, owners, capabilities, driveId)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = results.get('files', [])
            if files:
                folder_id = files[0]['id']
                print(f"\nFound 'Photo_Memories' by name. ID: {folder_id}")
            else:
                print("\n'Photo_Memories' folder NOT FOUND accessible to this account.")
                return
        except Exception as e:
            print(f"ERROR searching folder: {e}")
            return
    else:
         print(f"\nUsing Folder ID from env: {folder_id}")

    # 4. Check Folder Metadata
    try:
        folder = service.files().get(
            fileId=folder_id,
            fields="id, name, owners, capabilities, driveId, shared, permissionIds",
            supportsAllDrives=True
        ).execute()
        
        print(f"\n[Target Folder Info]")
        print(f"Name: {folder.get('name')}")
        print(f"ID: {folder.get('id')}")
        print(f"Shared: {folder.get('shared')}")
        print(f"Drive ID (Shared Drive?): {folder.get('driveId', 'None (My Drive)')}")
        print(f"Capabilities: CanAddChildren={folder.get('capabilities', {}).get('canAddChildren')}")
        
        if not folder.get('driveId'):
            print("NOTE: Folder is in 'My Drive' (not a Shared/Team Drive).")
            print("      Service Accounts usually CANNOT upload files here unless they have quota.")
            
    except Exception as e:
        print(f"ERROR reading folder metadata: {e}")
        return

    # 5. Try Test Upload (Tiny File)
    try:
        print("\n[Attempting Test Upload (1 byte)]")
        file_metadata = {
            'name': 'DIAGNOSTIC_TEST_FILE.txt',
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(b'x'), mimetype='text/plain', resumable=True)
        
        new_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        print(f"SUCCESS! Uploaded test file ID: {new_file.get('id')}")
        
        # Cleanup
        service.files().delete(fileId=new_file.get('id'), supportsAllDrives=True).execute()
        print("Test file cleaned up.")
        
    except Exception as e:
        print(f"FAIL: Upload failed. Reason: {e}")

if __name__ == "__main__":
    diagnose()

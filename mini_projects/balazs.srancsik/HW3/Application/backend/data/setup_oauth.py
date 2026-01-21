
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes required for the application
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    print("--- Google Drive OAuth 2.0 Setup ---")
    print("This script will generate the credentials needed for the .env file.")
    print("You need a 'client_secrets.json' file from Google Cloud Console.")
    print("1. Go to https://console.cloud.google.com/apis/credentials")
    print("2. Create Credentials -> OAuth client ID -> Desktop app")
    print("3. Download the JSON file and save it as 'client_secrets.json' in this folder")
    print("----------------------------------------")

    if not os.path.exists('client_secrets.json'):
        print("ERROR: 'client_secrets.json' not found!")
        print("Please download it from Google Cloud Console and try again.")
        return

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json', SCOPES)
        
        # Use console-based authentication which is more robust for remote/docker environments
        creds = flow.run_console()

        # Convert credentials to dictionary
        creds_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'expiry': creds.expiry.isoformat() if creds.expiry else None
        }

        # Print the JSON string
        print("\n--- SUCCESS! ---")
        print("Copy the following JSON string (everything between the lines) into your .env file:")
        print("GOOGLE_DRIVE_CREDENTIALS_JSON=" + json.dumps(creds_data))
        print("----------------")
        
        # Also save to file for convenience
        with open('user_credentials.json', 'w') as f:
            json.dump(creds_data, f)
        print("Credentials also saved to 'user_credentials.json'")

    except Exception as e:
        print(f"\nERROR: Authentication failed: {e}")

if __name__ == '__main__':
    main()

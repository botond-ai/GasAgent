"""
Helper script to generate Gmail API OAuth refresh token.

Steps to set up Gmail API:
1. Go to https://console.cloud.google.com/
2. Create a new project or select existing one
3. Enable Gmail API for your project
4. Go to "Credentials" and create OAuth 2.0 Client ID (Desktop app)
5. Download the credentials JSON file
6. Run this script to get the refresh token
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os

# Gmail API scope for sending emails
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_credentials():
    """
    Generate Gmail API credentials and refresh token.
    
    This will open a browser window for you to authorize the application.
    After authorization, it will print the refresh token that you need to
    add to your .env file.
    """
    creds = None
    
    # Check if we have saved credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # You need to download credentials.json from Google Cloud Console
            if not os.path.exists('credentials.json'):
                print("ERROR: credentials.json not found!")
                print("\nPlease follow these steps:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project and enable Gmail API")
                print("3. Create OAuth 2.0 credentials (Desktop app)")
                print("4. Download credentials.json and place it in this directory")
                return
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    print("\n" + "="*60)
    print("Gmail API Credentials Generated Successfully!")
    print("="*60)
    print("\nAdd these values to your .env file:\n")
    print(f"GMAIL_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print(f"GMAIL_FROM_EMAIL=your-email@gmail.com")
    print(f"GMAIL_TO_EMAIL=srancsik@gmail.com")
    print("\n" + "="*60)
    print("\nNote: Replace 'your-email@gmail.com' with the Gmail account")
    print("you used to authorize the application.")
    print("="*60 + "\n")

if __name__ == '__main__':
    get_gmail_credentials()

This folder contains a modified version of the AI Chat sample which I previously extended with a new radio channel related API, Document Read and Translate.  

📰 The newest feature is a photo_upload tool, which enables the user to store his/her photos in custom folders on PCloud. It uses both JSON POST and JSON GET menthods to interact with the server as follows:
- Based on the free text input from the user, it identifies the user's photo memory folder based on the event name, location and date
- Forces a naming convention for the folder: "YYYY.MM.DD - event_name - location" and creates the folder on PCloud's Photo_Memories folder
- uploads the photos to the folder
- in the response:
    - it returns the folder name and the file names of the uploaded photos
    - it also summarizes the folders available in the Photo_Memories folder

🧪 Pytest, Unit test, Pydentic API test scripts and test reports have been added into Test_Scripts_And_Logs folder

📈Entire Langraph description and details can be found in the langraph.md file

📊Further details about the used JSON Post and Get schema is below:

# Photo Upload Tool JSON Queries and Data Schema

## POST Request Schema
The POST requests handle file uploads and folder creation:

**Folder Creation:**
```json
{
  "action": "create_folder",
  "folder_name": "2024.01.15 - birthday party - Budapest",
  "metadata": {
    "date": "2024-01-15",
    "event_type": "birthday party",
    "location": "Budapest"
  }
}
```

**File Upload:**
```json
{
  "action": "upload_files",
  "folder_id": "target_folder_id",
  "files": [
    {
      "name": "photo1.jpg",
      "content": "base64_encoded_image_data",
      "content_type": "image/jpeg"
    }
  ],
  "metadata": {
    "upload_timestamp": "ISO_timestamp",
    "user_id": "user_identifier"
  }
}
```

## GET Request Schema
The photo upload tool uses GET requests to:
- **List folders**: Retrieve existing folder structure from the storage service
- **Check upload status**: Query the status of previously uploaded files
- **Get folder contents**: List files within specific photo memory folders

**Response Schema:**
```json
{
  "folders": [
    {
      "id": "folder_id",
      "name": "YYYY.MM.DD - event_name - location",
      "created_at": "timestamp",
      "file_count": "number"
    }
  ],
  "files": [
    {
      "id": "file_id",
      "name": "filename.jpg",
      "size": "bytes",
      "uploaded_at": "timestamp"
    }
  ]
}
```

## Usage Examples
1. **Query existing folders**: GET `/api/folders` returns available photo memory folders
2. **Create new memory folder**: POST with folder schema and event metadata
3. **Upload photos**: POST with files array containing base64-encoded images
4. **Retrieve folder contents**: GET `/api/folders/{folder_id}/files` for specific photo collection



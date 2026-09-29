# library/cloud_backup.py
"""
آپلود بکاپ به Google Drive
"""
import os
import pickle
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_drive_service(credentials_file='token.pickle'):
    """دریافت سرویس Google Drive"""
    creds = None

    if os.path.exists(credentials_file):
        with open(credentials_file, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(credentials_file, 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)


def upload_to_drive(file_path, folder_id=None):
    """آپلود فایل به Google Drive"""
    service = get_drive_service()
    file_name = os.path.basename(file_path)

    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(file_path, mimetype='application/json')

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink'
    ).execute()

    return file


def list_drive_backups(folder_id=None):
    """لیست بکاپ‌های موجود در Drive"""
    service = get_drive_service()

    query = "name contains 'backup_' and mimeType='application/json'"
    if folder_id:
        query += f" and '{folder_id}' in parents"

    results = service.files().list(
        q=query,
        pageSize=20,
        fields="files(id, name, createdTime, size, webViewLink)"
    ).execute()

    return results.get('files', [])


def download_from_drive(file_id, save_path):
    """دانلود فایل از Drive"""
    service = get_drive_service()

    request = service.files().get_media(fileId=file_id)

    with open(save_path, 'wb') as f:
        f.write(request.execute())

    return save_path
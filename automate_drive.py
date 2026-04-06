import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_latest_file(service, mime_type, file_ext, folder_id=None):
    query = f"mimeType='{mime_type}' and name contains '{file_ext}'"
    if folder_id:
        query += f" and '{folder_id}' in parents"
    results = service.files().list(
        q=query,
        orderBy="createdTime desc",
        pageSize=10,
        fields="files(id, name, createdTime)"
    ).execute()
    files = results.get('files', [])
    if not files:
        return None
    return files[0]  # Most recent

def download_file(service, file_id, destination):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(destination, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"Download {int(status.progress() * 100)}%.")
    print(f"Downloaded to {destination}")

if __name__ == '__main__':
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Optionally, set your folder ID here if you want to restrict search
    folder_id = None  # or 'your-folder-id'

    # Get latest .mp4 file
    latest_mp4 = get_latest_file(service, 'video/mp4', '.mp4', folder_id)
    # Get latest .gpx file (GPX files are usually application/gpx+xml or application/octet-stream)
    latest_gpx = get_latest_file(service, 'application/octet-stream', '.gpx', folder_id)
    if not latest_gpx:
        # Try with another common GPX mime type
        latest_gpx = get_latest_file(service, 'application/gpx+xml', '.gpx', folder_id)
    if not latest_gpx:
        # Try with generic XML
        latest_gpx = get_latest_file(service, 'application/xml', '.gpx', folder_id)

    output_dir_vid = 'vid'
    output_dir_gpx = 'gpx'
    os.makedirs(output_dir_vid, exist_ok=True)
    os.makedirs(output_dir_gpx, exist_ok=True)

    if latest_mp4:
        download_file(service, latest_mp4['id'], os.path.join(output_dir_vid, 'footage.mp4'))
    else:
        print("No .mp4 file found.")

    if latest_gpx:
        download_file(service, latest_gpx['id'], os.path.join(output_dir_gpx, "latest.gpx"))
    else:
        print("No .gpx file found.") 
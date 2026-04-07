from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from datetime import datetime
import json
import os
import pickle


class YouTubeShortsUploader:
    def __init__(self, client_secrets_file, api_key=None, target_channel_id=None):
        self.client_secrets_file = client_secrets_file
        self.target_channel_id = target_channel_id
        self.credentials_pickle = 'youtube_credentials.pickle'
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly"
        ]
        self.youtube = None

    def authenticate(self):
        credentials = None
        if os.path.exists(self.credentials_pickle):
            print("Loading saved credentials...")
            with open(self.credentials_pickle, 'rb') as token:
                credentials = pickle.load(token)

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                print("Refreshing expired credentials...")
                credentials.refresh(Request())
            else:
                print("Opening browser for YouTube authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes
                )
                credentials = flow.run_local_server(port=8080)
            with open(self.credentials_pickle, 'wb') as token:
                print("Credentials saved.")
                pickle.dump(credentials, token)

        self.youtube = build('youtube', 'v3', credentials=credentials)
        return self.youtube

    def get_channel_id(self):
        if not self.youtube:
            self.authenticate()
        response = self.youtube.channels().list(part="id", mine=True).execute()
        return response['items'][0]['id']

    def upload_short(self, video_path, content):
        """Upload a Short. content is a dict with topic, title, script, tags."""
        if not self.youtube:
            self.authenticate()

        if self.target_channel_id:
            current = self.get_channel_id()
            if current != self.target_channel_id:
                raise ValueError(f"Wrong channel! Authenticated as {current}, expected {self.target_channel_id}")

        title = content.get("title", f"🔥 {content.get('topic', 'Trending')} - Must Watch!")
        tags = content.get("tags", ["Shorts", "trending"])
        script = content.get("script", "")

        # Build description from script
        description = (
            f"{script[:200]}...\n\n"
            f"{'#' + ' #'.join(t.replace('#','').strip() for t in tags[:8] if t.strip())}\n"
            f"#Shorts #trending"
        )

        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:5000],
                'tags': [t.replace('#', '').strip() for t in tags] + ['Shorts', 'trending'],
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }

        try:
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
            )
            print(f"Uploading: {title}")
            response = insert_request.execute()
            video_id = response['id']
            print(f"✅ Upload successful! Video ID: {video_id}")
            self._save_log(video_id, title, description, tags)
            return video_id
        except HttpError as e:
            print(f"YouTube upload error: {e}")
            return None

    def _save_log(self, video_id, title, description, tags):
        log = {
            'video_id': video_id,
            'title': title,
            'description': description,
            'tags': tags,
            'upload_time': datetime.now().isoformat()
        }
        log_file = 'upload_history.json'
        history = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                history = json.load(f)
        history.append(log)
        with open(log_file, 'w') as f:
            json.dump(history, f, indent=2)

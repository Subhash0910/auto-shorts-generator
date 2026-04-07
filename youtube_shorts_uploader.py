from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from datetime import datetime
from groq import Groq
import json
import os
import pickle

class YouTubeShortsUploader:
    def __init__(self, client_secrets_file, api_key, target_channel_id=None):
        self.client_secrets_file = client_secrets_file
        self.target_channel_id = target_channel_id
        self.credentials_pickle = 'youtube_credentials.pickle'
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly"
        ]
        self.client = Groq(api_key=api_key)
        self.youtube = None

    def _groq_prompt(self, message, temperature=0.7):
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": message}],
                temperature=temperature
            )
            return {"status": "success", "message": response.choices[0].message.content}
        except Exception as e:
            return {"status": "error", "error": str(e)}

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
                print("Getting new credentials...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file,
                    self.scopes
                )
                credentials = flow.run_local_server(port=8080)

            with open(self.credentials_pickle, 'wb') as token:
                print("Saving credentials for future use...")
                pickle.dump(credentials, token)

        self.youtube = build('youtube', 'v3', credentials=credentials)
        return self.youtube

    def get_channel_id(self):
        if not self.youtube:
            self.authenticate()
        request = self.youtube.channels().list(part="id", mine=True)
        response = request.execute()
        return response['items'][0]['id']

    def generate_seo_content(self, riddle_content):
        prompt = f"""You are a YouTube Shorts metadata generator specializing in riddle and brain teaser content. Your task is to generate an engaging title and description for a riddle-based YouTube Short.

Content to process:
{riddle_content}

REQUIREMENTS:
1. Title MUST:
   - Include AT LEAST ONE of these keywords: "Riddle", "Brain Teaser", "Puzzle", "IQ Test", "Mind Game"
   - Include 2-3 relevant emojis
   - Stay under 40 characters
   - Use words like "Can You", "Solve If", "Only Genius", "Test Your Mind"

2. Description must:
   - Be engaging and conversational
   - Include a clear call-to-action
   - Use 3-4 relevant hashtags
   - Stay under 200 characters

YOU MUST FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
Title: [Your title here with emojis and keywords]
Description: [Your description here with hashtags]

YOUR RESPONSE MUST START WITH 'Title:' AND INCLUDE 'Description:' ON A NEW LINE.
DO NOT include any other text or explanations."""

        response = self._groq_prompt(prompt, temperature=0.7)

        if response["status"] != "success":
            return (
                "🧠 Riddle Challenge: Can You Solve? 🤔",
                "Test your brain with these mind-bending riddles! Like & Subscribe for more puzzles! #Riddles #BrainTeasers #Shorts"
            )

        content = response["message"].strip().split('\n')
        title = None
        description = None

        for line in content:
            line = line.strip()
            if line.lower().startswith('title:'):
                title = line.replace('Title:', '', 1).strip()
            elif line.lower().startswith('description:'):
                description = line.replace('Description:', '', 1).strip()

        if not title:
            title = "🧠 Genius Riddle: Can You Solve? 🤔"
        if not description:
            description = "Only the smartest can solve this! Like & Subscribe for daily brain teasers! #Riddles #BrainTeasers #IQTest #Shorts"

        if len(title) > 40:
            title = title[:37] + "..."

        required_keywords = ["riddle", "brain teaser", "puzzle", "iq test", "mind game"]
        if not any(keyword in title.lower() for keyword in required_keywords):
            title = "🧠 Riddle: " + title

        return title, description

    def generate_tags(self, riddle_content):
        prompt = f"Generate 10 relevant YouTube tags for this riddle: {riddle_content}"
        response = self._groq_prompt(prompt, temperature=0.7)

        if response["status"] == "success":
            tags = [tag.strip() for tag in response["message"].split(',')]
            tags.extend(['shorts', 'youtubeshorts', 'riddle', 'brainteaser'])
            return list(set(tags))[:15]
        else:
            return ['shorts', 'youtubeshorts', 'riddle', 'brainteaser']

    def upload_short(self, video_path, riddle_content):
        if not self.youtube:
            self.authenticate()

        if self.target_channel_id:
            current_channel = self.get_channel_id()
            if current_channel != self.target_channel_id:
                raise ValueError(f"Wrong channel! Authenticated as {current_channel}")

        title, description = self.generate_seo_content(riddle_content)
        tags = self.generate_tags(riddle_content)

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False,
            }
        }

        try:
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=MediaFileUpload(
                    video_path,
                    chunksize=-1,
                    resumable=True,
                    mimetype='video/mp4'
                )
            )

            print(f"Starting upload: {title}")
            response = insert_request.execute()
            video_id = response['id']
            print(f"Upload successful! Video ID: {video_id}")
            print(f"Title: {title}")
            print(f"Description: {description}")
            self._save_upload_details(video_id, title, description, tags)
            return video_id

        except HttpError as e:
            print(f"An HTTP error occurred: {str(e)}")
            return None

    def _save_upload_details(self, video_id, title, description, tags):
        upload_details = {
            'video_id': video_id,
            'title': title,
            'description': description,
            'tags': tags,
            'upload_time': datetime.now().isoformat()
        }

        log_file = 'upload_history.json'
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    history = json.load(f)
            else:
                history = []
            history.append(upload_details)
            with open(log_file, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"Failed to save upload details: {str(e)}")
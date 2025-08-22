import os, re, time, pickle, sys
from typing import List, Dict, Set, Optional
import time
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ================== CONFIG ==================
CHANNEL_SEARCH_NAME = "Barbell Pitch Meetings"  # we'll resolve its channelId
KEYWORD = "Pitch Meeting"                        # title must contain this
WHOLE_WORD = True                                # True=\\bPitch Meeting\\b ; False=substring
PLAYLIST_TITLE = "Barbell: Pitch Meeting videos (auto)"
PLAYLIST_DESCRIPTION = "Videos from @BarbellPitchMeetings with 'Pitch Meeting' in the title."
PLAYLIST_PRIVACY = "private"                     # "private" | "unlisted" | "public"
MAX_TO_ADD = 1000                                # safety cap
SLEEP_BETWEEN_ADDS_SEC = 0.15                    # gentle pacing
SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_FILE = "token_youtube_api.pkl"
CLIENT_SECRET = "client_secret.json"
# ============================================
def wait_until_playlist_exists(youtube, playlist_id: str, tries: int = 6, delay: float = 1.5):
    """Poll until the playlist becomes readable; raise if it never does."""
    for i in range(tries):
        try:
            youtube.playlists().list(part="id", id=playlist_id, maxResults=1).execute()
            return  # success
        except HttpError as e:
            if e.resp.status == 404:
                time.sleep(delay)
                delay *= 1.6  # backoff
            else:
                raise
    raise RuntimeError("Playlist not readable after retries (eventual consistency delay?).")
def auth_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET):
                sys.exit("Missing client_secret.json (OAuth desktop) next to this script.")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

def find_channel_id(youtube, channel_name: str) -> Optional[str]:
    """Resolve channelId by searching for the channel name and picking the best title match."""
    req = youtube.search().list(part="snippet", q=channel_name, type="channel", maxResults=5)
    resp = req.execute()
    best = None
    name_l = channel_name.strip().lower()
    for it in resp.get("items", []):
        title = it["snippet"]["channelTitle"].strip().lower()
        cid = it["snippet"]["channelId"]
        if title == name_l:
            return cid
        best = best or cid
    return best

def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    resp = youtube.channels().list(part="contentDetails", id=channel_id, maxResults=1).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError("Channel not found or missing contentDetails.")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

def iter_all_uploads(youtube, uploads_playlist_id: str):
    """Yield dicts with videoId and title for every upload (handles pagination)."""
    pt = None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=pt
        ).execute()
        for it in resp.get("items", []):
            vid = it["contentDetails"]["videoId"]
            title = it["snippet"]["title"]
            yield {"id": vid, "title": title}
        pt = resp.get("nextPageToken")
        if not pt:
            break

def title_matches(title: str, kw: str, whole_word: bool) -> bool:
    if whole_word:
        # whole-word, but allow internal spaces; case-insensitive
        pattern = r"\b" + re.escape(kw) + r"\b"
        return re.search(pattern, title, flags=re.IGNORECASE) is not None
    return kw.lower() in title.lower()

def create_playlist(youtube, title: str, description: str, privacy: str) -> str:
    body = {"snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy}}
    resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
    return resp["id"]

def get_existing_ids_in_playlist(youtube, playlist_id: str) -> set[str]:
    ids = set()
    page_token = None
    while True:
        try:
            resp = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=page_token,
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                time.sleep(1.5)
                continue
            raise
        for it in resp.get("items", []):
            ids.add(it["contentDetails"]["videoId"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def add_to_playlist(youtube, playlist_id: str, video_id: str):
    body = {"snippet": {"playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
    return youtube.playlistItems().insert(part="snippet", body=body).execute()

def main():
    youtube = auth_service()

    # 1) resolve channel
    channel_id = find_channel_id(youtube, CHANNEL_SEARCH_NAME)
    if not channel_id:
        sys.exit(f"Could not resolve channel for name: {CHANNEL_SEARCH_NAME}")

    # 2) uploads feed
    uploads_pid = get_uploads_playlist_id(youtube, channel_id)

    # 3) collect matches
    matches = []
    for item in iter_all_uploads(youtube, uploads_pid):
        if title_matches(item["title"], KEYWORD, WHOLE_WORD):
            matches.append(item)
            if len(matches) >= MAX_TO_ADD:
                break

    if not matches:
        print("No uploads matched the title filter.")
        return

    # 4) create playlist
    playlist_id = create_playlist(youtube, PLAYLIST_TITLE, PLAYLIST_DESCRIPTION, PLAYLIST_PRIVACY)
    print(f"Created playlist: https://www.youtube.com/playlist?list={playlist_id}")

    wait_until_playlist_exists(youtube, playlist_id)  # <-- add this line

    existing = get_existing_ids_in_playlist(youtube, playlist_id)


    # 5) add videos (skip dups)
    existing = get_existing_ids_in_playlist(youtube, playlist_id)
    added = 0
    for m in matches:
        if m["id"] in existing:
            continue
        try:
            add_to_playlist(youtube, playlist_id, m["id"])
            added += 1
            time.sleep(SLEEP_BETWEEN_ADDS_SEC)
        except HttpError as e:
            print(f"Failed to add {m['id']}: {e}")

    print(f"Done. Added {added} / {len(matches)} matching videos.")

if __name__ == "__main__":
    main()

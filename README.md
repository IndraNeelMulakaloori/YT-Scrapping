# YouTube Playlist Auto-Sync

Automates discovery and curation of YouTube videos from a channel’s **Uploads** feed into a **private playlist**, with whole-word title filtering, OAuth2, pagination, dedupe, backoff, and gentle rate-limiting. Ships with simple metrics so you can drop results straight into your resume.

## ✨ Features

- **Channel resolve → uploads traverse → filter → curate** (end-to-end)
- **Whole-word regex** title matching (e.g., `\bPitch Meeting\b`)
- **OAuth2 Desktop flow** with token persistence (`pickle`)
- **Pagination** across channel uploads (50/page)
- **Idempotent dedupe** (skip already-added videos)
- **Eventual consistency** handling for new playlists (poll & backoff)
- **Rate limiting** between inserts (defaults to `0.15s`)
- **Safety cap** on number of videos to add
- **Metrics printout** (scanned, matched, added, duplicates, runtime)

## 🧰 Tech

Python • Google APIs Client • YouTube Data API v3 • OAuthlib • Pandas (optional, for CSV)

## 📦 Requirements

- Python 3.9+  
- Google Cloud project with **YouTube Data API v3** enabled  
- OAuth client: **Desktop App**  
- Files in repo root:
  - `client_secret.json` (downloaded from Google Cloud Console)
  - (auto-generated) `token_youtube_api.pkl`

Install deps:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

> If you plan to export CSVs, also: `pip install pandas`

## ⚙️ Configuration

Edit the constants at the top of `barbell_scrap.py`:

```python
CHANNEL_SEARCH_NAME = "Barbell Pitch Meetings"
KEYWORD = "Pitch Meeting"
WHOLE_WORD = True
PLAYLIST_TITLE = "Barbell: Pitch Meeting videos (auto)"
PLAYLIST_DESCRIPTION = "Videos from @BarbellPitchMeetings with 'Pitch Meeting' in the title."
PLAYLIST_PRIVACY = "private"
MAX_TO_ADD = 1000
SLEEP_BETWEEN_ADDS_SEC = 0.15
SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_FILE = "token_youtube_api.pkl"
CLIENT_SECRET = "client_secret.json"
```

## ▶️ Run

First run will open a browser for Google sign-in (Desktop OAuth). After that, token is reused.

```bash
python barbell_scrap.py
```

**Sample output:**
```
Created playlist: https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
Scanned: 358 | Matches: 120 | Added: 95 | Duplicates: 25 | Errors: 0 | Runtime: 00:02:07
Done. Added 95 / 120 matching videos.
```

## 📊 Metrics (auto-printed)

- **Scanned**: total uploads traversed
- **Matches**: videos whose titles match the keyword/regex
- **Added**: newly inserted into the playlist
- **Duplicates**: matched but already present (skipped)
- **Errors**: API insert failures after retries
- **Runtime**: end-to-end wall clock

## 🧩 How it Works (High Level)

1. Resolve channel ID  
2. Fetch uploads playlist ID  
3. Iterate uploads (paginated)  
4. Filter titles by regex  
5. Create playlist and poll until readable  
6. Add videos (skip dups, retry on errors)  
7. Print metrics and exit

## 🧪 Optional: Export to CSV

```python
import pandas as pd
df = pd.DataFrame(matches)
df.to_csv("matched_videos.csv", index=False)
```

## 🛡️ Troubleshooting

- **Missing client_secret.json**: Place your Desktop OAuth client secret next to the script.
- **Quota errors**: You’ve hit API quota; try later or request higher quota.
- **404 playlist not found**: Expected eventual consistency — script polls with backoff.
- **Auth issues**: Delete `token_youtube_api.pkl` to re-run OAuth.

## 🔒 Secrets

- Keep `client_secret.json` and `token_youtube_api.pkl` private.  
- Add them to `.gitignore`.

```
token_youtube_api.pkl
client_secret.json
__pycache__/
.venv/
```


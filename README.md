# Chauny Douyin Skill

A self-contained read-mostly Douyin skill for:

- metadata
- format listing
- audio/video download
- comments
- like / favorite state inspection
- optional DashScope transcription

Primary stable route:

- real browser login session
- page `RENDER_DATA` extraction
- direct media URL download from rendered data

## Safety default

This repo is read-mostly by default.
It does not expose risky write workflows as first-class commands.

## Status first

```bash
python scripts/dy_status.py --json
```

## Install

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Optional:

```bash
ffmpeg
```

## Workflows

### Login and cookie export

```bash
python scripts/dy_login.py
```

This now performs a preparation phase before opening the login page:

1. scan usable dedicated browsers (`chrome`, `edge`, `chromium`)
2. pick a dedicated browser/profile for the skill
3. print the selected browser, executable, and profile directory
4. only then open the visible Douyin login window
5. export both `cookies.json` and `cookies.txt` after you log in

Important:

- do **not** trust a generic “prepared login window” message by itself
- trust the JSON block that says `window_ready: true`
- if you do not personally see a browser window on your desktop, stop and report that explicitly

### Metadata

```bash
python scripts/dy_info.py "<douyin_share_url>"
python scripts/dy_info.py "<douyin_share_url>" --formats
python scripts/dy_info.py "<douyin_share_url>" --browser chrome
python scripts/dy_info.py "<douyin_share_url>" --cookie-file "D:/path/to/cookies.txt"
```

### Download

```bash
python scripts/dy_download.py "<douyin_share_url>"
python scripts/dy_download.py "<douyin_share_url>" --audio-only
python scripts/dy_download.py "<douyin_share_url>" --browser chrome
python scripts/dy_download.py "<douyin_share_url>" --cookie-file "D:/path/to/cookies.txt"
```

### Comments

```bash
python scripts/dy_comments.py "<douyin_share_url>" --count 10
```

### Reaction state

```bash
python scripts/dy_reactions.py "<douyin_share_url>"
```

### Transcription

```bash
python scripts/dy_transcribe.py "D:/path/to/local.mp4"
python scripts/dy_transcribe.py "https://example.com/audio.wav"
```

Detailed operator manual:

- `references/OPERATIONS-MANUAL.md`

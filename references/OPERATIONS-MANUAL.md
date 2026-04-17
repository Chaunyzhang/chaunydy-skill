# Chauny Douyin Skill Operations Manual

This manual is for weaker models and low-context operators.

## 1. Purpose

This repo provides a self-contained read-mostly Douyin skill.

Main blocks:

1. metadata
2. format listing
3. media download
4. transcription

Current preferred runtime path:

1. log in through `dy_login.py`
2. reuse the exported browser cookies
3. parse `RENDER_DATA` from a real page session
4. extract direct media URLs from rendered page data

## 2. First command

Always run:

```bash
python scripts/dy_status.py --json
```

## 3. Install

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Optional:

```bash
ffmpeg
```

## 4. Metadata

```bash
python scripts/dy_info.py "<douyin_share_url>"
python scripts/dy_info.py "<douyin_share_url>" --formats
python scripts/dy_info.py "<douyin_share_url>" --browser chrome
```

Use metadata first when:

- a share link looks broken
- download path is unclear
- you want to inspect available formats before downloading

## 5. Download

```bash
python scripts/dy_download.py "<douyin_share_url>"
python scripts/dy_download.py "<douyin_share_url>" --audio-only
python scripts/dy_download.py "<douyin_share_url>" --browser chrome
```

## 5. Fresh cookie requirement

Douyin currently often requires fresh browser cookies even for read-only metadata and download paths.

If you see an error like:

```text
Fresh cookies (not necessarily logged in) are needed
```

preferred fix:

```bash
python scripts/dy_login.py
```

What this does:

1. opens a persistent browser
2. lets the user log in manually
3. exports cookies into:
   - `~/.local/share/chaunydy-skill/cookies.json`
   - `~/.local/share/chaunydy-skill/cookies.txt`

If that path still needs manual override, then do this:

1. open Douyin in a real browser
2. refresh the page normally
3. rerun the command with a browser hint:

```bash
python scripts/dy_info.py "<douyin_share_url>" --browser chrome
python scripts/dy_download.py "<douyin_share_url>" --browser chrome
```

If Chrome is not your active browser, try `edge`.

If browser-cookie loading fails on Windows because of DPAPI decryption, use a manual cookie file instead:

```bash
python scripts/dy_info.py "<douyin_share_url>" --cookie-file "D:/path/to/cookies.txt"
python scripts/dy_download.py "<douyin_share_url>" --cookie-file "D:/path/to/cookies.txt"
```

Success means:

- `success: true`
- `file_path` is non-empty
- `file_size_bytes > 0`

## 6. Transcription

Requires:

```bash
DASHSCOPE_API_KEY
```

Examples:

```bash
python scripts/dy_transcribe.py "D:/path/to/video.mp4"
python scripts/dy_transcribe.py "https://example.com/audio.wav"
```

## 7. Safety default

Do not add publish/comment/like flows as default commands in this repo.

## 8. Practical rule

If a link cannot be parsed cleanly, stop and report it rather than inventing a fake success state.

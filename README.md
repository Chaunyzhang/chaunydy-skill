# Chauny Douyin Skill

A self-contained read-mostly Douyin skill for:

- metadata
- format listing
- audio/video download
- optional DashScope transcription

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
```

Optional:

```bash
ffmpeg
```

## Workflows

### Metadata

```bash
python scripts/dy_info.py "<douyin_share_url>"
python scripts/dy_info.py "<douyin_share_url>" --formats
python scripts/dy_info.py "<douyin_share_url>" --browser chrome
```

### Download

```bash
python scripts/dy_download.py "<douyin_share_url>"
python scripts/dy_download.py "<douyin_share_url>" --audio-only
python scripts/dy_download.py "<douyin_share_url>" --browser chrome
```

### Transcription

```bash
python scripts/dy_transcribe.py "D:/path/to/local.mp4"
python scripts/dy_transcribe.py "https://example.com/audio.wav"
```

Detailed operator manual:

- `references/OPERATIONS-MANUAL.md`

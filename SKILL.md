---
name: chaunydy-skill
description: Chauny's Douyin collection skill. Prefer audio-first when a trustworthy standalone audio source is exposed, otherwise fall back to downloading the video from a share link using the proven share-page source parsing route, then verify the file really exists. Use when the user wants to collect 抖音 media first, especially before any transcription or copywriting step. Do not use this skill for ASR or text generation.
---

Read `references/workflow.md` before changing the workflow.

## Command

```bash
python scripts/download_douyin_video.py "<douyin_share_url>"
```

## Hard rules

- Only do download and verification.
- Prefer audio-first if a standalone audio source is truly available.
- Current stable route falls back to video download.
- Success requires verified file metadata.
- Do not mix in transcription.
- This route is share-link parsing, not browser/F12 capture.
- If verification fails, treat the run as failed.

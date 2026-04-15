# Chauny Douyin Download Workflow

## Goal

Prefer audio-first if a trustworthy standalone audio source is available; otherwise download the Douyin video to local disk and stop.
Do not mix in transcription, ASR, or copywriting.

## Working path

1. Use the share link directly
2. Let `scripts/douyin.js` parse the share page source data
3. Try audio-first only if the page exposes a trustworthy standalone audio source
4. Otherwise extract candidate video URLs from page JSON
5. Prefer the strongest candidate and download the MP4 as fallback
6. Verify success using `file_exists` and `file_size_bytes`

## Known working link

- `https://v.douyin.com/FSfWiKriBuY/`

## Pitfalls

- Do not trust printed success alone
- Prefer in-process `file_exists` and `file_size_bytes` over later cross-process path checks on Windows
- Emoji/encoding print errors are display problems, not download failures
- TLS handshake errors are request-level failures, not proof the whole machine is offline
- This working path came from share-page source parsing, not browser/F12 capture

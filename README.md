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

On a new machine, run the doctor first:

```bash
python scripts/dy_doctor.py --json
```

This is the self-check stage. It verifies:

- dedicated browser candidates
- dedicated profile directories
- cookie health
- Playwright launchability
- whether login is still needed
- exact next actions for weak models

Then run:

```bash
python scripts/dy_status.py --json
```

Then run the actual preparation / readiness stage:

```bash
python scripts/dy_prepare.py
```

`dy_prepare.py` is now the real foundation step. It:

- selects the dedicated browser/profile
- confirms whether the dedicated browser login state is actually usable
- opens login when needed
- exports cookies
- probes metadata readiness
- probes comments readiness
- probes reaction readiness
- probes search readiness
- writes a persistent prepare-state file so later agents can resume from known state

When search returns `verify_check`, `dy_prepare.py` now opens the dedicated browser search page and waits for the human to complete verification before rechecking search readiness.

Important:

- cookie presence alone does not automatically skip login anymore
- the prepare flow first tries to confirm that the dedicated browser profile can actually access a logged-in page
- if that confirmation fails, it will force the visible login stage before continuing
- search verification is now split out into a separate explicit step:

```bash
python scripts/dy_search_verify.py
python scripts/dy_prepare.py
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

Important:

- `dy_info.py` now expects `dy_prepare.py` to have succeeded first
- if the prepare-state is missing or stale, it will stop and tell you to rerun preparation

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

Current transcription vendor support:

- `DashScope` only

API-key rule:

- every agent / terminal session must configure its **own** transcription API key
- do not assume one agent inherits another agent's environment
- do not write real keys into the repo, sample configs, or committed files
- do not reuse or expose any team-owned secret key in skill output

Current environment variable:

```powershell
$env:DASHSCOPE_API_KEY="your_own_key"
```

Weak-model operator guidance:

1. tell the user that this skill currently supports **DashScope** for transcription
2. tell the user to open their **own** DashScope / 阿里云百炼 account and create their **own** API key
3. ask the user to set the key only in the **current agent session**
4. if the key is missing, stop and report that honestly
5. never paste any existing secret from our side into chat, code, config, or logs

Detailed operator manual:

- `references/OPERATIONS-MANUAL.md`

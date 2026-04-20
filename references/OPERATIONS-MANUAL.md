# Chauny Douyin Skill Operations Manual

This manual is written for weak models and low-context operators.
Do not improvise. Follow the exact order.

## 1. What this skill is for

This repo is a read-mostly Douyin skill.

Use it for:

1. metadata
2. format inspection
3. media download
4. comment reading
5. like/favorite state reading
6. transcription

Do not treat it as a writing or publishing tool.

## 2. Default safety rule

Allowed by default:

- metadata
- format listing
- download
- comments read
- reaction state read
- transcription

Not enabled as default workflow actions:

- like action
- favorite action
- comment posting
- any other write action

Reason:

- Douyin risk controls are aggressive
- read-only paths are much safer and already useful

## 3. First command always

Always run this first on a new machine:

```bash
python scripts/dy_doctor.py --json
```

This is the self-check stage.
Use it to confirm:

- browser candidates
- dedicated profile directories
- cookie health
- whether login is still needed
- whether Playwright can launch the selected browser path

Then run:

```bash
python scripts/dy_status.py --json
```

Then run:

```bash
python scripts/dy_prepare.py
```

If `all_ready` is true, continue.

If `all_ready` is false, stop and inspect the missing parts.

## 4. Required install

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Optional but important:

```bash
ffmpeg
```

Needed for:

- local video transcription

## 5. The only supported login path

Do not guess.
Do not use random browser profiles.
Do not assume Edge or Chrome is automatically reusable.

Use this only:

```bash
python scripts/dy_login.py
```

What this does:

1. scans dedicated browser candidates first
2. selects a dedicated browser + profile for the skill
3. prints the selected browser environment
4. opens a dedicated browser session
5. waits for the user to log in
6. exports:
   - `~/.local/share/chaunydy-skill/cookies.json`
   - `~/.local/share/chaunydy-skill/cookies.txt`

Important:

- If user interaction is needed, stop and wait
- Do not continue until the user confirms login is complete
- Do not assume the login window is visible just because the script says it is preparing one
- Treat `window_ready: true` plus human confirmation as the real signal
- Do not switch to another browser path on your own

## 5.5 Real preparation stage

The real readiness gate is:

```bash
python scripts/dy_prepare.py
```

This is different from `dy_doctor.py`.

- `dy_doctor.py` = self-check
- `dy_prepare.py` = browser selection + login + capability verification + persistent prepare-state

`dy_prepare.py` verifies:

1. metadata
2. comments
3. reactions
4. search

The output is written into a persistent prepare-state file so later agents can recover after interruptions instead of guessing.

Important:

- normal probes should stay headless and quiet
- only true human-action stages should open a visible browser window
- if search hits `verify_check`, `dy_prepare.py` should open the dedicated search page and wait for the human to finish verification before retrying the search probe
- the verification window must not close merely because the page title or URL no longer looks like a captcha page; it should close only after a real search-readiness probe succeeds

## 6. Preferred runtime path

The current preferred path is:

1. dedicated login session
2. browser cookies exported
3. real page load
4. parse `#RENDER_DATA`
5. extract media URLs from rendered page data

This is more stable than:

- anonymous scraping
- `yt-dlp` as the first path
- browser-cookie auto-decryption

## 7. Workflow map

### A. Metadata

Command:

```bash
python scripts/dy_info.py "<douyin_share_url>"
```

Use this when:

- the user wants title / author / counts
- you need to validate a share link before download
- you need the safest first read

Expected success signs:

- `success: true`
- `info.title`
- `info.uploader`
- `info.webpage_url`

### B. Format inspection

Command:

```bash
python scripts/dy_info.py "<douyin_share_url>" --formats
```

Use this when:

- you want to inspect possible output formats
- you need debugging before download

### C. Download

Audio first:

```bash
python scripts/dy_download.py "<douyin_share_url>" --audio-only --output-dir "./out"
```

Video:

```bash
python scripts/dy_download.py "<douyin_share_url>" --output-dir "./out"
```

Expected success signs:

- `success: true`
- `file_path` exists
- `file_size_bytes > 0`

### D. Comments

Command:

```bash
python scripts/dy_comments.py "<douyin_share_url>" --count 10
```

Expected success signs:

- `success: true`
- `comments` array exists
- comment items contain:
  - `text`
  - `digg_count`
  - `user`

### E. Reaction state

Command:

```bash
python scripts/dy_reactions.py "<douyin_share_url>"
```

Expected success signs:

- `success: true`
- `like_count`
- `collect_count`
- `comment_count`
- `user_digged`
- `user_collected`

Important:

- This is state reading only
- Do not treat it as permission to click like or favorite

### F. Transcription

Requires:

```bash
DASHSCOPE_API_KEY
```

Current supported vendor:

- `DashScope` only

Secret-handling rule:

1. every agent / terminal session must configure its own key separately
2. never assume another agent already configured it
3. never print or commit a real key
4. never expose any team-owned key to the user

Correct setup pattern:

```powershell
$env:DASHSCOPE_API_KEY="your_own_key"
```

How weak models should guide the user:

1. say that transcription currently supports **DashScope**
2. ask the user to create their **own** DashScope / 阿里云百炼 API key
3. tell the user to set it only in the current session
4. if the key is missing, stop and report the missing configuration honestly
5. do not invent fallback credentials

Commands:

```bash
python scripts/dy_transcribe.py "D:/path/to/local.mp4"
python scripts/dy_transcribe.py "D:/path/to/local.mp3"
python scripts/dy_transcribe.py "https://example.com/audio.wav"
```

Expected success signs:

- `success: true`
- `provider: dashscope`
- `result.sentences` or `result.results`

## 8. Strict execution order for weak models

If you are a weak model, follow this exact order:

1. `python scripts/dy_doctor.py --json`
2. `python scripts/dy_status.py --json`
3. `python scripts/dy_prepare.py`
4. If prepare says login is needed, stop and wait for the human to complete the visible login window
5. After prepare succeeds, run `python scripts/dy_info.py "<url>"` first
6. Only after metadata succeeds, run download or comments or reactions
7. Only after download succeeds, run transcription

Do not reorder these steps.

## 9. Failure meanings

### Case: `Fresh cookies (not necessarily logged in) are needed`

Meaning:

- the current path still does not have a usable fresh session

Action:

1. stop
2. run `python scripts/dy_login.py`
3. wait for user login
4. rerun `dy_info.py`

### Case: `success: false` in metadata

Meaning:

- the share link is not usable yet
- or the login session is not trusted enough

Action:

1. do not guess
2. rerun login
3. retry metadata

### Case: metadata succeeds but download fails

Meaning:

- rendered data was available but the extracted media URL was not usable

Action:

1. retry once
2. if still failing, report failure honestly
3. do not invent a fake success

### Case: comments succeed but reactions are missing

Meaning:

- the page was partially readable
- some state fields may not be present for that aweme

Action:

1. keep comment result
2. report missing state fields honestly

## 10. What the user must do

The user only needs to do one interactive task:

- log in when you explicitly ask them to

When you need user help, say it plainly:

- “Please log in in the opened Douyin window.”
- “Reply ‘已登录’ when done.”

Do not keep switching browsers.
Do not assume the user knows which session you are using.

## 11. Minimal summary

Remember only this:

1. `dy_status.py --json`
2. if needed, `dy_login.py`
3. `dy_info.py`
4. `dy_download.py`
5. `dy_comments.py`
6. `dy_reactions.py`
7. `dy_transcribe.py`

And never invent success when the data is not really there.

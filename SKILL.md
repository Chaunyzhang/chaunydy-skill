---
name: chaunydy-skill
description: 一个聚合版抖音技能，包含元数据、格式查看、下载、可选 DashScope 转写等只读能力。默认禁用写操作。适合弱模型按步骤执行：先检查状态，再选择元数据、下载或转写工作流。
---

# Chauny Douyin Skill

Detailed operator manual:

- `references/OPERATIONS-MANUAL.md`

## First rule

Always run the self-check stage first on a new machine:

```bash
python scripts/dy_doctor.py --json
```

Then check status:

```bash
python scripts/dy_status.py --json
```

If Douyin requires fresh cookies, run:

```bash
python scripts/dy_login.py
```

`dy_login.py` now has an explicit preparation stage before login:

1. scan dedicated browser candidates
2. choose a browser/profile
3. print the chosen environment
4. open the visible Douyin login window

Only continue after the user says they **personally saw the window**.
Do not treat “browser prepared” as proof that a visible window actually appeared.

## Workflow A: metadata

```bash
python scripts/dy_info.py "<douyin_share_url>"
python scripts/dy_info.py "<douyin_share_url>" --formats
```

## Workflow B: download

```bash
python scripts/dy_download.py "<douyin_share_url>"
python scripts/dy_download.py "<douyin_share_url>" --audio-only
```

## Workflow C: comments

```bash
python scripts/dy_comments.py "<douyin_share_url>" --count 10
```

## Workflow D: reaction state

```bash
python scripts/dy_reactions.py "<douyin_share_url>"
```

## Workflow E: transcription

```bash
python scripts/dy_transcribe.py "<local_or_remote_media_source>"
```

## Weak-model rules

1. Do not skip `dy_status.py`
2. Prefer read-only operations
3. Prefer metadata before download when debugging a broken link
4. Prefer local media for transcription when possible

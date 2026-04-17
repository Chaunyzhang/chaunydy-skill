# Douyin Workflow

## Goal

Use a stable read-only path for Douyin share links:

1. inspect metadata
2. inspect available formats if needed
3. download media
4. optionally transcribe local media

## Important rule

Treat download success as real only when the file exists and has non-zero size.

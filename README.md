# Clip Automator 🎬

Fully automated finance clip finder. Pulls latest videos from top finance creators, scores them for virality, downloads the best ones, and sends you a daily email digest.

## What it does
- Checks 5 finance YouTube channels daily
- Scores each video title for viral potential (0-10)
- Downloads anything scoring 5+
- Emails you a digest of what's queued
- You review → everything else posts automatically

## Environment Variables (set in Railway)
| Variable | Value |
|---|---|
| EMAIL_SENDER | your Gmail address |
| EMAIL_PASSWORD | Gmail app password (not your real password) |
| EMAIL_RECEIVER | where you want the daily digest sent |

## Creators monitored
1. Codie Sanchez
2. Graham Stephan
3. George Kamel
4. Andrei Jikh
5. Mark Tilbury

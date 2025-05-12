# STATOME Telegram Bot (Render Deployment)

This is a video-report forwarding Telegram bot for internal use.

## Features

- Accepts video or video-files from employees
- Forwards them to a private channel
- Responds in Russian or Spanish

## Deployment on Render

1. Push this repo to GitHub
2. Go to https://dashboard.render.com
3. Click "New Web Service" → Connect your repo
4. Render reads render.yaml and deploys automatically
5. Done! Your bot is live 24/7

## Environment Variables (already included)

- `BOT_TOKEN` – Your BotFather token
- `CHANNEL_ID` – Your private channel ID (starts with -100...)

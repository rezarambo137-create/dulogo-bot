# DU Şafak Nail Beauty — Logo Bot

This bot has your logo baked in. Send it a photo in Telegram and it replies with
**3 versions** of that photo, each with the logo placed in a different spot it
judged to be a good, uncluttered fit (it avoids faces and busy areas automatically).

You control the standard logo size yourself with a chat command — no code edits needed.

---

## Part 1 — Create your bot with BotFather (5 minutes)

1. Open Telegram, search for **@BotFather**, start a chat with it.
2. Send `/newbot`.
3. Give it a name (e.g. "DU Şafak Logo Bot") and a username ending in `bot` (e.g. `dusafak_logo_bot`).
4. BotFather will reply with a **token** — a long string like `123456789:AAF...`.
   Save this somewhere safe. You'll paste it into Railway in Part 2.

---

## Part 2 — Deploy for free on Railway (10-15 minutes)

Railway keeps the bot running 24/7 without you needing a computer left on.

1. Go to **https://railway.app** and sign up (GitHub login is easiest).
2. Put this project on GitHub:
   - Go to **https://github.com/new**, create a repository (e.g. `logo-bot`), keep it Private if you like.
   - Upload all the files from this folder (`bot.py`, `requirements.txt`, `Procfile`, `logo.png`, `README.md`)
     using GitHub's "Add file → Upload files" button in the browser — no command line needed.
3. Back in Railway: click **New Project → Deploy from GitHub repo**, pick the repo you just created.
4. Railway will start building automatically. While it builds, go to the **Variables** tab of your Railway service and add:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: *(paste the token from BotFather)*
5. Go to the **Settings** tab → **Deploy** section → set **Custom Start Command** to:
   ```
   python bot.py
   ```
   (This makes sure Railway runs the bot itself rather than guessing.)
6. Redeploy if needed (Railway usually does this automatically after you save settings/variables).
7. Check the **Deployments → View Logs** tab — you should see the bot start up with no errors.

That's it. Open Telegram, find your bot by its username, and send `/start`.

---

## Using it day-to-day

- **Set your standard logo size** (once, or whenever you want to change it):
  ```
  /setsize 20
  ```
  This means the logo will always be 20% of each photo's width. Pick any number from 5-60.
  Your choice is remembered for your chat.

- **Get logo placements**: just send any photo to the bot. You'll get 3 photos back,
  each captioned with where the logo was placed (e.g. "bottom-right", "top-left").
  Pick whichever looks best and post that one.

---

## Notes

- The bot avoids placing the logo over detected faces, and prefers plainer areas of
  the photo over busy/detailed ones — it's a good heuristic, not perfect judgment,
  so occasionally you may want to nudge/replace a placement using the browser-based
  **Mark.** studio tool for full manual control.
- Free Railway usage has monthly hour limits — fine for personal/small business use,
  but if you post a very high volume of photos, keep an eye on your Railway usage dashboard.
- To change the logo later, just replace `logo.png` in the GitHub repo with a new
  transparent PNG and Railway will redeploy automatically.

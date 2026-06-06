# Deploying Digital Adjudicator to Render

This guide walks you through deploying the app to Render's free tier. All steps are point-and-click — no terminal work after the initial code push.

## What you'll get

- **A web app** at `https://digital-adjudicator-XXXX.onrender.com` (Render assigns the subdomain)
- **A free PostgreSQL database** that persists for **90 days** (more than your 7-day window)
- **Free HTTPS** with auto-renewing SSL
- **Three test users** seeded automatically: `admin`, `judge`, `zahra` (same passwords as local)

## One-time setup (15 minutes total)

### 1. Push the code to GitHub

The app is in `SE_Zahra/DigitalAdjudicator_App/`. Push **that folder** as the root of a GitHub repo.

```bash
# From inside DigitalAdjudicator_App/
git init
git add .
git commit -m "Initial commit"
git branch -M main

# Then on github.com, create a new repo named 'digital-adjudicator', and:
git remote add origin https://github.com/YOUR_USERNAME/digital-adjudicator.git
git push -u origin main
```

If you're not comfortable with command-line git, use [GitHub Desktop](https://desktop.github.com/) — point it at the `DigitalAdjudicator_App` folder, fill in repo name, click Publish.

### 2. Create a Render account

Go to [render.com](https://render.com) and sign up with GitHub. The free tier needs no credit card.

### 3. Connect your repo

In the Render dashboard:

1. Click **New +** in the top bar → **Blueprint**
2. Pick your GitHub account, find **digital-adjudicator**, click **Connect**
3. Render reads `render.yaml` from the repo and shows you what it'll create:
   - A web service: `digital-adjudicator`
   - A free PostgreSQL: `digital-adjudicator-db`
4. Click **Apply**

That's it. Render builds the app, provisions the database, and links them. First deploy takes about **4–7 minutes** (because Postgres is being created and Python dependencies are installed).

### 4. Get your URL

Once the build status turns green, your URL appears at the top of the service page:

```
https://digital-adjudicator-abcd.onrender.com
```

Open it. You should see the public homepage with "The Stage Awaits."

### 5. Sign in

The build process automatically ran `seed_test_users.py`, so these accounts exist on the live site:

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin12345` |
| Judge | `judge` | `judge12345` |
| Participant | `zahra` | `zahra12345` |

**Change these passwords before sharing the URL.** Either:
- Sign in as `admin`, go to a competition, create judges with strong passwords, and never share `admin12345`
- Or edit `seed_test_users.py` before pushing to set stronger passwords

## What's different in production

Compared to local development, the deployed app has:

- **HTTPS forced** for cookies (`SESSION_COOKIE_SECURE = True`)
- **PostgreSQL** instead of SQLite (the schema is identical; SQLAlchemy handles it)
- **Gunicorn** as the WSGI server with 2 workers × 4 threads
- **DEBUG = False** so error traces don't leak
- **Health check** at `/auth/login` so Render can tell if the app is alive

## Render free tier — important quirks

### Sleep after 15 minutes

The web service goes to sleep after 15 minutes of no traffic. **First request after sleep takes ~30 seconds** as Render wakes the container.

Workaround: keep it awake during your tournament with [UptimeRobot](https://uptimerobot.com) (free):
1. Sign up at uptimerobot.com (no credit card)
2. Add a new monitor → HTTP(s) → your Render URL
3. Set check interval to 5 minutes
4. The pings keep the app warm

### Ephemeral filesystem

Uploaded profile photos are saved to `app/static/uploads/photos/`. **These are lost when the container restarts** (e.g., after sleep or on redeploy). For a 7-day tournament this is usually fine because:
- Participants upload during registration, photos are used during the tournament, then everything resets afterwards
- The database (Postgres) persists, only the file uploads are ephemeral

If you need photo persistence past restarts: upgrade to Render's $7/month plan and attach a persistent disk, or switch photo storage to S3/Cloudinary.

### Database lifetime

Render's free Postgres expires after 90 days. For your 7-day window you're well within. After 90 days the database is automatically deleted — set a calendar reminder if you want to back it up.

## Updating the live app

After the initial setup, every push to your GitHub repo's `main` branch automatically triggers a Render rebuild. Workflow:

```bash
# Make edits locally, test with python run.py
git add .
git commit -m "describe what changed"
git push
```

Then watch the **Deploys** tab in Render. Builds take 2–4 minutes after the first one. Old version stays running until the new one is healthy.

## Common issues

### "Application failed to start" on first deploy

Check the **Logs** tab. Most common causes:
- Missing dependency in `requirements.txt` — add it and push again
- Postgres not finished provisioning — wait 60 seconds and click **Manual Deploy → Deploy latest commit**

### Photos disappear after a while

That's the ephemeral filesystem. See "Ephemeral filesystem" above. For a single-tournament 7-day demo this rarely matters.

### "404 Not Found" on a URL that worked locally

You're hitting the auth gate. Sign in first.

### Slow first-load after a quiet hour

That's the 15-minute sleep. Use UptimeRobot to fix.

## Tearing it down

When you're done with the deployment:

1. Render dashboard → your service → **Settings → Delete Service**
2. Render dashboard → your database → **Settings → Delete Database**

Or just let the database expire automatically after 90 days. The free tier doesn't charge you anything either way.

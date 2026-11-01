# Deployment: Aiven (MySQL) + Render (backend) + Vercel (frontend)

All three have free plans, and none needs a credit card to start.

| Part | Host | Free plan (check current terms) | Configured by |
|---|---|---|---|
| MySQL 8 database | **Aiven for MySQL** | 1 CPU, 1 GB RAM, 1 GB disk, backups, no time limit | Aiven console |
| FastAPI backend | **Render** web service | Sleeps after ~15 idle minutes | [`render.yaml`](../render.yaml) |
| React frontend | **Vercel** | Static hosting | [`frontend/vercel.json`](../frontend/vercel.json) |

```
Browser ──HTTPS──▶ Vercel (static React app)
   │
   └──HTTPS + Bearer token──▶ Render (FastAPI, Docker) ──TLS──▶ Aiven MySQL 8
```

Render and Vercel redeploy automatically when you push to `main`. Allow about 45 minutes the
first time.

---

## 0. Before you start

- Push the code to GitHub, and create a `main` branch if you don't have one yet:

  ```bash
  git checkout develop && git pull
  git checkout -b main && git push -u origin main
  ```

- Make free accounts on [aiven.io](https://aiven.io), [render.com](https://render.com) and
  [vercel.com](https://vercel.com). Sign in to Render and Vercel with GitHub so they can see
  the repository.
- Choose the first admin's email and a **strong password**. The site is public, so don't use
  `admin12345`.

---

## 1. Database on Aiven

1. In the Aiven console, choose **Create service → MySQL**, then the **Free** plan.
2. Pick a cloud region **close to the Render region** you'll use in step 2. Every query
   crosses between the two, so a nearby pair makes the app noticeably faster. For users in
   India, pick Asia (e.g. Singapore) on both if they're offered.
3. Name it (e.g. `uio-mysql`) and click **Create**. It takes a few minutes to show
   **Running**.
4. On the service's **Overview** page, copy:
   - **Service URI**: `mysql://avnadmin:<password>@<host>.aivencloud.com:<port>/defaultdb?ssl-mode=REQUIRED`
   - **CA certificate** (click **Show**, then copy the whole `-----BEGIN CERTIFICATE-----…` block). This is optional but recommended.

The tables are created automatically by the backend on its first start; you don't need to
run any SQL.

**About the free plan:**
- **Idle shutdown.** Aiven can power off a free service that has no activity, after sending
  you an email. Power it back on from the console. Open the app every few days, or enable the
  nightly pipeline (step 5), which counts as activity.
- **1 GB disk.** The demo data takes about 35 MB. Each pipeline run stores about 7 MB of
  forecasts, but only the newest 5 runs keep theirs (older runs keep their targets and
  summary), so storage levels off at well under 100 MB. "Reset to fresh demo data" clears old
  runs entirely.
- **Connections.** The free plan allows 76 connections; the backend uses at most 10.

---

## 2. Backend on Render

1. In the Render dashboard, choose **New → Blueprint** and select this repository. Render reads
   `render.yaml` and proposes the web service **uio-backend**. Choose the region nearest your
   Aiven database.
2. Fill in the variables it asks for:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Aiven's **Service URI**, pasted exactly (the `?ssl-mode=REQUIRED` part turns on encryption) |
   | `DATABASE_SSL_CA` | Aiven's **CA certificate**, pasted whole (optional; makes the backend also verify it's really talking to your database) |
   | `CORS_ORIGINS` | For now `https://example.com`; you'll set the real Vercel URL in step 4 |
   | `ADMIN_EMAIL` | The first admin's email |
   | `ADMIN_PASSWORD` | The first admin's password (8+ characters) |

   `JWT_SECRET` and `API_KEY` are generated automatically; leave them alone.
3. Click **Apply**. The first build takes 5–10 minutes (OR-Tools is large).
4. When the service shows **Live**, open `https://<your-service>.onrender.com/health/ready`.
   It should show `{"status":"ready"}`, which means the backend reached the database. Note
   this URL: it's your **backend URL**.

On every start, the container applies database migrations (`alembic upgrade head`). It
creates the first admin only while the `users` table is empty.

---

## 3. Frontend on Vercel

1. In Vercel, choose **Add New → Project** and import the repository.
2. Set **Root Directory** to `frontend`. Vercel detects Vite; `vercel.json` sets the build.
3. Under **Environment Variables**, add `VITE_API_URL` = your backend URL, e.g.
   `https://uio-backend.onrender.com` (no trailing slash).
4. Click **Deploy** and note the URL, e.g. `https://unified-inventory-optimizer.vercel.app`.
5. In **Settings → Git**, set the **Production Branch** to `main`.

---

## 4. Connect them

In Render, open **uio-backend → Environment** and set `CORS_ORIGINS` to your exact Vercel URL
(no trailing slash; separate several with commas). Save, and Render redeploys in a minute or
two.

---

## 5. First sign-in

1. Open your Vercel URL and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
2. The dashboard shows **Welcome! Let's get some data in**. Click **Load demo data**. This
   loads the demo network and runs the pipeline, taking about a minute on free plans. Or go
   to **Data Import** and upload your own Excel file.
3. Open **Users** and create accounts: **Viewer** (read-only, good for examiners),
   **Planner** (runs the pipeline, edits policies, imports data) and **Admin**.

**Nightly pipeline (optional).** In GitHub → **Settings → Secrets and variables → Actions**,
add `PROD_API_URL` (your backend URL) and `PIPELINE_SECRET` (the `API_KEY` value from Render's
Environment tab). `.github/workflows/nightly-pipeline.yml` then re-runs forecasts and targets
at 02:00 UTC every night, which also keeps the free Aiven database active.

---

## 6. Before a presentation

- **Check the database is on.** In the Aiven console, make sure the service is **Running**,
  not powered off.
- **Wake the backend.** Open the site 3–5 minutes before you present. While Render's free
  backend wakes up (up to a minute), the app shows *"The server is waking up…"* and retries
  on its own.
- **Refresh the demo data.** Demo sales history ends on the day it was loaded. A day or two
  before, sign in as admin, then go to **Data Import → Demo data → Reset to fresh demo data**.
  It keeps users and the activity log.
- **Take a backup** (optional). Aiven's free plan includes automatic backups. You can also
  take your own with the values from the Aiven Overview page:

  ```bash
  mysqldump --ssl-mode=REQUIRED -h <host> -P <port> -u avnadmin -p defaultdb > uio-backup.sql
  ```

- **Have a fallback.** Keep the local Docker version working (`docker compose up -d && make demo`),
  plus a short screen recording.

---

## 7. Updating the live site

```bash
git checkout main && git merge develop && git push
```

Render rebuilds the backend and applies any new migrations to Aiven. Vercel rebuilds the
frontend.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `/health` works but `/health/ready` shows `unhealthy` | The backend can't reach MySQL. Check `DATABASE_URL` matches Aiven's Service URI exactly, and that the Aiven service is **Running** (not powered off). Render's **Logs** show the exact error |
| Logs show `Access denied for user 'avnadmin'` | The password in `DATABASE_URL` is wrong or was reset in Aiven. Copy the Service URI again |
| Logs show a certificate / SSL error | `DATABASE_SSL_CA` was pasted incompletely. Paste the whole block including the BEGIN/END lines, or clear the variable to connect encrypted without verification |
| Login shows "Can't reach the server" right away, and the browser console mentions CORS | `CORS_ORIGINS` on Render doesn't exactly match the Vercel URL (scheme, no trailing slash) |
| Login takes up to a minute | The free backend was asleep; expected |
| Render deploy fails with `JWT_SECRET (32+ characters) must be set` | Set it to a long random string: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| Nobody can sign in on a fresh deploy | `ADMIN_EMAIL` / `ADMIN_PASSWORD` weren't set before the first start. Set them and redeploy |
| Forgot the admin password | Another admin can reset it on **Users**. If there's none: make a hash with `python3 -c "import bcrypt; print(bcrypt.hashpw(b'NewPassword123', bcrypt.gensalt()).decode())"`, connect with `mysql --ssl-mode=REQUIRED -h <host> -P <port> -u avnadmin -p defaultdb`, and run `UPDATE users SET password_hash='<hash>' WHERE email='<admin email>';` |
| Refreshing a page on Vercel gives 404 | The project's Root Directory isn't `frontend`, so `vercel.json` wasn't picked up |
| Dashboard empty after deploy | No data yet: **Load demo data** on the dashboard, or **Data Import** |

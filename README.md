# Azure Storage Migration Query Monitor

Automatically monitors Reddit, Stack Overflow, and Microsoft forums for questions about **storage migrations to Azure** (online/offline, from on-prem/AWS/GCP).

**What you get:** A notification on your phone/email with:
1. The question someone asked
2. A **suggested response** (with Microsoft Learn doc links) you can copy-paste as a reply
3. A direct link to the post so you can reply immediately

**Cost: $0/month** — everything used is free.

---

## What You'll Receive (Real Example)

This is an actual match the monitor found from Reddit r/sysadmin this week:

```
SOURCE: Reddit r/sysadmin
LINK:   https://reddit.com/r/sysadmin/comments/.../vmware_to_azure_migration...

--- QUESTION ---
Title: VMware to Azure migration scenarios post Broadcom acquisition?
Body:  Mid sized team here. Our vmware renewal post broadcom acquisition
       looks like a totally different cost scenario so I'm looking at avs
       with hcx to get out of the renewal cycle...

--- SUGGESTED RESPONSE (copy-paste this as your reply) ---
Here are Azure tools that can help with your migration:

**Azure Migrate** - Discover, assess, and migrate servers and VMs.
Docs: https://learn.microsoft.com/azure/migrate/

**AzCopy** - Versatile CLI tool for Azure Storage data movement.
Docs: https://learn.microsoft.com/azure/storage/common/storage-use-azcopy-v10

Full migration guide:
https://learn.microsoft.com/azure/storage/common/storage-migration-overview
```

---

## 3 Notification Options (All Free)

Pick whichever you prefer:

| Option | What it is | Difficulty | Best for |
|--------|-----------|------------|----------|
| **Microsoft Teams** | Messages in a Teams channel | Easy | Enterprise / work teams |
| **Email (Gmail)** | Get alerts in your inbox | Easy | Most people |
| **ntfy.sh** | Phone push notifications | Easy | Instant mobile alerts |
| **Discord** | Messages in a Discord channel | Easy | If you use Discord |

---

## Step-by-Step Setup

### STEP 1: Get the code onto GitHub

You need a GitHub account (free). This is where the automation runs.

**1a.** Go to https://github.com and sign in (or create a free account)

**1b.** Click the **+** button (top right) → **New repository**

**1c.** Name it `azure-migration-monitor`, set it to **Public** (free unlimited runs), click **Create**

**1d.** Open PowerShell on your computer and run these commands one by one:

```powershell
cd c:\Users\lakshyajalan\azure-migration-monitor
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/azure-migration-monitor.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

---

### STEP 2: Choose your notification method

#### OPTION A: Microsoft Teams (Recommended for enterprise)

**What you need:** Access to a Teams channel where you can add a webhook.

**2a.** Open **Microsoft Teams** → go to the channel where you want alerts

**2b.** Click the **•••** (three dots) next to the channel name → **Manage channel**

**2c.** Scroll to **Connectors** (or **Apps** → **Incoming Webhook**) and click **Edit**

**2d.** Search for **Incoming Webhook** → click **Add** → click **Add** again

**2e.** Give it a name like `Azure Migration Monitor` → click **Create**

**2f.** Copy the webhook URL it gives you (starts with `https://...webhook.office.com/...`)

**2g.** Go to your GitHub repo → **Settings** tab → left sidebar: **Secrets and variables** → **Actions**

**2h.** Click **New repository secret**:

| Secret name | Value |
|------------|-------|
| `TEAMS_WEBHOOK_URL` | The webhook URL you copied in step 2f |

**2i.** Click the **Variables** tab → **New repository variable**:

| Variable name | Value |
|--------------|-------|
| `NOTIFY_METHOD` | `teams` |

Done! You’ll get rich **Adaptive Cards** in your Teams channel like this:

```
┌────────────────────────────────────────────┐
│  Azure Migration Query Detected           │
│                                            │
│  Source: Reddit r/sysadmin                 │
│  Title:  VMware to Azure migration...      │
│                                            │
│  Question:                                 │
│  Mid sized team here. Our vmware renewal   │
│  post broadcom acquisition looks like...    │
│                                            │
│  Suggested Response:                       │
│  **Azure Migrate** - Discover, assess...   │
│  Docs: https://learn.microsoft.com/...     │
│                                            │
│  [ Open Post ]                             │
└────────────────────────────────────────────┘
```

The card has a clickable **"Open Post"** button that takes you directly to the forum post.

> **Note for new Teams (Workflows app):** If your org has migrated to the new Teams
> and Incoming Webhook connector is retired, use **Workflows** instead:
> 1. In Teams, go to the channel → **•••** → **Workflows**
> 2. Search for **"Post to a channel when a webhook request is received"**
> 3. Set it up and copy the workflow URL — use that as `TEAMS_WEBHOOK_URL`

---

#### OPTION B: Email (Gmail) — Get alerts in your inbox

**What you need:** A Gmail account with 2-Factor Authentication enabled.

**2a.** Go to https://myaccount.google.com/apppasswords
   - If you don't see this page, first enable 2FA at https://myaccount.google.com/signinoptions/two-step-verification

**2b.** Create a new app password:
   - App name: `azure-monitor`
   - Click **Create**
   - Copy the 16-character password it shows you (e.g., `abcd efgh ijkl mnop`)

**2c.** Go to your GitHub repo → **Settings** tab → left sidebar: **Secrets and variables** → **Actions**

**2d.** Click **New repository secret** and add these one by one:

| Secret name | Value |
|------------|-------|
| `EMAIL_FROM` | Your Gmail address, e.g. `lakshya@gmail.com` |
| `EMAIL_TO` | Where to receive alerts (can be same Gmail or any other email) |
| `EMAIL_PASSWORD` | The 16-char app password from step 2b |

**2e.** Still on the same page, click the **Variables** tab → **New repository variable**:

| Variable name | Value |
|--------------|-------|
| `NOTIFY_METHOD` | `email` |

Done! You'll get emails like this when a match is found:
```
Subject: Azure Migration Query: VMware to Azure migration scenarios...
Body: [Question + Suggested Response + Link to post]
```

---

#### OPTION C: ntfy.sh — Phone push notifications (no account needed)

**2a.** Install the **ntfy** app:
   - Android: Search "ntfy" in Play Store
   - iPhone: Search "ntfy" in App Store

**2b.** Open the app → tap **+** → type a unique topic name, e.g. `lakshya-azure-monitor-2026`
   - Pick something unique! Anyone who knows the topic name can see messages

**2c.** Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**

**2d.** Add a **Secret**: `NTFY_TOPIC` = `lakshya-azure-monitor-2026` (same name from step 2b)

**2e.** Add a **Variable**: `NOTIFY_METHOD` = `ntfy`

Done! You'll get push notifications on your phone.

---

#### OPTION D: Discord webhook

**2a.** In your Discord server → right-click a channel → **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**

**2b.** Copy the webhook URL

**2c.** Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**

**2d.** Add a **Secret**: `DISCORD_WEBHOOK_URL` = the URL you copied

**2e.** Add a **Variable**: `NOTIFY_METHOD` = `discord`

---

### STEP 3: (Optional) Enable smarter AI responses — Free

Without this, you still get suggested responses — they're template-based with relevant Azure tools and Microsoft Learn links (like the example above).

With this, you get **context-aware AI responses** from Google Gemini that understand the specific question and write a tailored reply.

**3a.** Go to https://aistudio.google.com/apikey

**3b.** Sign in with your Google account → click **Create API Key** → copy it

**3c.** In GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
   - Name: `GEMINI_API_KEY`
   - Value: the API key you copied

Free tier: 1500 requests/day (more than enough).

---

### STEP 4: Start the monitor

**4a.** Go to your repo on GitHub → click the **Actions** tab

**4b.** You'll see "Azure Migration Monitor" on the left → click it

**4c.** Click the **"Run workflow"** dropdown → click the green **"Run workflow"** button

**4d.** Wait ~30 seconds, then click into the run to see the logs

**4e.** If everything worked, you'll see output like:
```
Fetching: https://www.reddit.com/r/azure/new/.rss
  Got 25 posts
  MATCH: VMware to Azure migration scenarios post Broadcom acquisition?
...
Relevant matches: 4
Processing: VMware to Azure migration...
  Sent email notification
Done.
```

**4f.** The workflow now runs automatically every 15 minutes, 24/7. No further action needed.

---

## About the Suggested Responses

Every notification includes a **suggested response** you can use to reply to the forum post. The response:

- Recommends the right **Azure tools** based on the question context:
  - **Azure Data Box** — for large offline migrations (ship a physical device)
  - **Azure File Sync** — for file server sync to Azure Files
  - **AzCopy** — CLI tool for blob/file transfers, S3-to-Azure copy
  - **Azure Storage Mover** — managed agent-based migration
  - **Azure Migrate** — VM/server discovery and migration
- Includes **Microsoft Learn documentation links** for each tool
- Links to the full migration overview guide

If you add a Gemini API key (Step 3), responses are AI-generated and tailored to the specific question.

---

## Where Does It Look?

The monitor checks these sources every 15 minutes:

| Source | What it checks |
|--------|---------------|
| Reddit r/azure | All new posts + search for "storage migration" |
| Reddit r/sysadmin | Search for "azure storage migration" |
| Reddit r/cloudcomputing | Search for "azure migration" |
| Reddit r/dataengineering | Search for "azure storage migration" |
| Stack Overflow | Posts tagged `azure-storage` and `azure-migrate` |

---

## Customization

### Change how often it checks
Edit `.github/workflows/monitor.yml`:
```yaml
- cron: "*/15 * * * *"   # every 15 min (default)
- cron: "*/30 * * * *"   # every 30 min
- cron: "0 * * * *"      # every hour
```

### Add more subreddits or tags
Edit the `RSS_FEEDS` list in `monitor.py`.

### Adjust keyword sensitivity
Edit `MIGRATION_KEYWORDS`, `STORAGE_KEYWORDS`, `AZURE_KEYWORDS` in `monitor.py` to catch broader or narrower topics.

---

## Cost Breakdown

| Component | Cost |
|-----------|------|
| GitHub Actions | Free (unlimited on public repos) |
| RSS Feeds (Reddit/SO) | Free (no API keys needed) |
| Email (Gmail SMTP) | Free |
| ntfy.sh push notifications | Free (no account) |
| Discord Webhook | Free |
| Google Gemini AI (optional) | Free tier (1500 req/day) |
| **Total** | **$0/month** |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No notifications | Go to Actions tab → click the latest run → check logs for errors |
| Too many notifications | Tighten keywords in `monitor.py` or remove noisy feeds |
| Too few notifications | Loosen keywords or add more Reddit subreddits |
| Email not arriving | Check spam folder. Verify app password is correct (not your Gmail password) |
| "NTFY_TOPIC not set" | Make sure you added the secret in GitHub Settings, not just as a variable |
| Workflow not running | Go to Actions tab → enable the workflow if it says "disabled" |

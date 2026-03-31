# samuelstocks

DJIA insider trading dashboard for daily stock research.
Live site: `https://YOUR-USERNAME.github.io/samuelstocks`

---

## One-time setup (takes ~15 minutes)

### Step 1 — Create the GitHub repo

1. Go to [github.com/new](https://github.com/new)
2. Name it exactly: `samuelstocks`
3. Set it to **Public** (required for free GitHub Pages)
4. Click **Create repository**
5. Upload all these files (drag and drop or use GitHub Desktop)

### Step 2 — Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Under "Source", select **Deploy from a branch**
3. Branch: `main`, Folder: `/ (root)`
4. Click **Save**
5. Your site will be live at: `https://YOUR-USERNAME.github.io/samuelstocks`

### Step 3 — Set up Gmail App Password (for sending emails)

Gmail requires an "App Password" — a special password just for this script.

1. Go to your Google Account → **Security**
2. Make sure **2-Step Verification** is ON
3. Search for "App passwords" in your Google Account settings
4. Create a new app password: name it "samuelstocks"
5. Copy the 16-character password shown (you only see it once)

### Step 4 — Add GitHub Secrets

These are encrypted — GitHub never shows them again after you save.

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:

| Secret name | Value |
|---|---|
| `SENDER_GMAIL` | Your Gmail address (e.g. `you@gmail.com`) |
| `SENDER_GMAIL_APP_PASS` | The 16-char app password from Step 3 |
| `RECIPIENT_EMAIL` | Dad's Outlook/Live address |
| `SITE_URL` | `https://YOUR-USERNAME.github.io/samuelstocks` |

### Step 5 — Test it manually

1. Go to your repo → **Actions** tab
2. Click **Nightly Insider Trading Fetch** in the left sidebar
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch it run — takes about 2-3 minutes
5. Check that `data/insider.json` appeared in your repo
6. Check that an email arrived in dad's inbox

---

## How it works

```
Every night at midnight PST
        ↓
GitHub Actions wakes up
        ↓
fetch_insider.py runs
  → Loads all 30 DJIA tickers
  → Fetches CIK numbers from SEC
  → Pulls Form 4 filings from last 7 days
  → Parses buys, sells, roles, shares
  → Saves to data/insider.json
        ↓
Git commits data/insider.json to repo
        ↓
send_email.py runs
  → Reads data/insider.json
  → Builds HTML email with tables
  → CEO/CFO buys highlighted at top
  → Sends via your Gmail to dad's Outlook
        ↓
GitHub Pages serves index.html
  → Loads data/insider.json automatically
  → Dad opens site any time next morning
```

## File structure

```
samuelstocks/
├── index.html                        ← The website (GitHub Pages serves this)
├── data/
│   └── insider.json                  ← Auto-generated nightly (do not edit)
├── scripts/
│   ├── fetch_insider.py              ← Fetches SEC EDGAR data
│   └── send_email.py                 ← Sends nightly email digest
├── .github/
│   └── workflows/
│       └── nightly.yml               ← GitHub Actions schedule
└── README.md
```

## Troubleshooting

**Email not arriving?**
- Check spam/junk folder
- Verify the Gmail App Password is correct (not your regular password)
- Make sure 2FA is enabled on your Gmail

**Data not updating?**
- Go to Actions tab → check if the workflow ran and if there were errors
- SEC EDGAR sometimes rate-limits — the script has delays built in

**Site not loading?**
- GitHub Pages can take 5-10 minutes after first setup
- Make sure repo is Public, not Private

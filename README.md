# 🏅 XAUUSD Gold Price Alert Bot

A Telegram bot that tracks live **XAUUSD (Gold/USD)** prices and sends you instant alerts when the price hits your target.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📊 Live Price | `/price` gives you the current spot price instantly |
| 🔔 Price Alerts | Set unlimited above/below alerts |
| 📝 Alert Notes | Tag alerts ("buy zone", "stop loss", etc.) |
| 🔁 Auto-check | Checks price every 60 seconds in background |
| 💾 Persistent | Alerts survive bot restarts (SQLite DB) |
| 👥 Multi-user | Each Telegram user has their own alerts |

---

## 🚀 Quick Setup (5 minutes)

### Step 1 — Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. "My Gold Alert Bot")
4. Choose a username ending in `bot` (e.g. `mygoldalert_bot`)
5. Copy the **API token** → looks like `1234567890:ABCdef_...`

### Step 2 — Install Dependencies

```bash
# Python 3.10+ required
python --version

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install packages
pip install -r requirements.txt
```

### Step 3 — Configure & Run

```bash
# Set your token
export BOT_TOKEN="1234567890:ABCdef_your_token_here"

# (Windows)
set BOT_TOKEN=1234567890:ABCdef_your_token_here

# Start the bot
python bot.py
```

You should see:
```
2024-01-01 12:00:00  INFO      Bot started  |  Interval: 60s  |  DB: alerts.db
```

### Step 4 — Use It

Find your bot on Telegram by its `@username` and send `/start`!

---

## 📋 Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + command list |
| `/price` | Current XAUUSD price |
| `/alert 2500` | Alert when gold hits $2,500 |
| `/alert 2100 support` | Alert with a note |
| `/alerts` | List all your active alerts |
| `/cancel 3` | Remove alert #3 |
| `/cancelall` | Remove all your alerts |
| `/help` | Help message |

### Example Session

```
You:  /price
Bot:  📊 XAUUSD Spot Price
      💰 $2,341.50  per troy oz
      🕐 2024-06-15 09:30:00 UTC

You:  /alert 2400
Bot:  ✅ Alert Created — ID #1
      🎯 Target:   $2,400.00
      📊 Current:  $2,341.50
      ↔️  Gap:      $58.50
      📈 Fires when price goes above $2,400.00

[... later when gold hits $2,400 ...]

Bot:  🚨 PRICE ALERT FIRED!
      📈 XAUUSD moved above your target!
      💰 Current:  $2,401.20
      🎯 Target:   $2,400.00
```

---

## ⚙️ Configuration

Set these as environment variables:

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | **required** | Your bot token from @BotFather |
| `CHECK_INTERVAL` | `60` | Seconds between price checks |
| `DB_PATH` | `alerts.db` | SQLite database file path |

---

## 📡 Price Data

| Source | Ticker | Notes |
|---|---|---|
| Yahoo Finance | `XAUUSD=X` | Spot gold — primary source |
| Yahoo Finance | `GC=F` | Gold Futures — fallback |

> ⚠️ **Free tier data may have a ~15 min delay.**
> Gold markets are open 23 hours/day, 5 days/week (Mon–Fri).
> Prices are unavailable on weekends.

### Upgrade to Real-Time Data (Optional)

Use [Twelve Data](https://twelvedata.com/) — free tier gives 800 requests/day with near real-time XAUUSD prices.

Replace the `get_price()` function in `bot.py`:

```python
import requests

TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_KEY", "")

def get_price() -> Optional[float]:
    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": "XAU/USD", "apikey": TWELVE_DATA_KEY}
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        price = float(data.get("price", 0))
        return price if price > 500 else None
    except Exception as exc:
        logger.error("Twelve Data error: %s", exc)
        return None
```

Then: `export TWELVE_DATA_KEY="your_key_here"`

---

## 🌐 Deployment (Run 24/7)

For real-time alerts the bot needs to run continuously.

### Option A — Railway.app (Easiest, Free)

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → GitHub repo
3. Add environment variable: `BOT_TOKEN = your_token`
4. Deploy → Done!

### Option B — VPS (DigitalOcean / Linode / AWS)

```bash
# SSH into your server, then:
sudo apt update && sudo apt install python3-pip screen -y

# Clone/upload your bot files
cd xauusd-bot
pip3 install -r requirements.txt

# Run in a screen session so it keeps running after you disconnect
screen -S goldbot
export BOT_TOKEN="your_token"
python3 bot.py

# Press Ctrl+A, then D to detach (bot keeps running)
# To reattach: screen -r goldbot
```

### Option C — Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
```

```bash
docker build -t xauusd-bot .
docker run -d -e BOT_TOKEN="your_token" --name goldbot xauusd-bot
```

### Option D — systemd Service (Linux)

```ini
# /etc/systemd/system/goldbot.service
[Unit]
Description=XAUUSD Gold Alert Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/xauusd-bot/bot.py
Restart=always
Environment=BOT_TOKEN=your_token_here

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable goldbot
sudo systemctl start goldbot
```

---

## 🗂 Project Structure

```
xauusd-bot/
├── bot.py            # Main bot (all-in-one file)
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variable template
├── README.md         # This file
└── alerts.db         # SQLite database (auto-created on first run)
```

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| `BOT_TOKEN is not set` | Run `export BOT_TOKEN="..."` before `python bot.py` |
| Price shows as unavailable | Markets closed (weekend) or Yahoo Finance is slow — wait and retry |
| Bot not responding | Check the terminal for errors; restart with `python bot.py` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |

---

## 📄 License

MIT — free to use, modify, and deploy.

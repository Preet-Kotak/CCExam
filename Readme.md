# CCExam — Clash of Clans CC Exam Bot

A Discord bot for managing **Clan Capital (CC) Exam** seasons in Clash of Clans. Examiners can start seasons, record base links, submit and edit player scores per district, and track a live leaderboard that updates automatically after every score submission.

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Commands](#commands)
- [Grading System](#grading-system)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Database Schema](#database-schema)
- [Deployment](#deployment)

---

## Features

- **Season management** — Start and end CC Exam seasons with a chosen month and 5 districts
- **Base tracking** — Store and display CoC layout share links + screenshots per district
- **Score submission** — Submit per-district scores (stars + percentage) via a Discord modal
- **Score editing & deletion** — Correct or remove scores at any time during an active season
- **Live leaderboard** — A pinned embed in your leaderboard channel that auto-updates whenever a score is submitted or changed
- **Historical scores** — Any server member can look up a player's full score history across all seasons with pagination
- **District leaderboard** — View ranking for a specific district within any season
- **Role-gated commands** — Examiner-only commands are protected by a configurable Discord role
- **Keep-alive server** — Built-in HTTP server + self-ping loop for persistent hosting on Render

---

## How It Works

1. A **CC Examiner** starts a season with `/start`, picks the month/year, and selects exactly **5 districts** from a dropdown.
2. The bot creates a live leaderboard embed in the configured leaderboard channel.
3. The examiner adds each district's base layout link via `/add_link` (the bot auto-detects which district the link belongs to from the CoC share URL).
4. As players complete the exam, the examiner runs `/submit_score`, fills in a per-district score modal (format: `stars.percent`, e.g. `3.100` or `2.50`), and the bot:
   - Saves the score to the database
   - Posts a score result embed in the results channel and mentions the player
   - Automatically updates the live leaderboard
5. Scores can be corrected with `/edit_score` or removed with `/delete_score`.
6. At the end of the month, `/end_exam` closes the season and posts a summary of all bases to the end-season channel.

---

## Commands

### CC Examiner Only

| Command | Description |
|---|---|
| `/start <month> <year>` | Start a new exam season and select 5 districts |
| `/add_link <link> <screenshot>` | Add or replace a base layout link + screenshot for a district |
| `/submit_score <player>` | Submit a score for a player via a modal |
| `/edit_score <player>` | Edit an existing player score via a pre-filled modal |
| `/delete_score <player>` | Delete a player's score from the current season |
| `/show_bases` | Show all current base links and screenshots |
| `/end_exam` | Close the current season and post a base summary |
| `/delete_exam <name>` | Permanently delete a season and all its data |

### Everyone

| Command | Description |
|---|---|
| `/show_score <player>` | View all recorded scores for a player (paginated) |
| `/leaderboard <season>` | View the full leaderboard for any season |
| `/district_leaderboard <season> <district>` | View the ranking for a specific district in a season |
| `/help` | Show available commands (examiner commands shown only to examiners) |

---

## Grading System

Grades are based purely on the number of **3-star districts** out of the 5 examined:

| 3-Star Count | Grade |
|:---:|:---:|
| 5 | A+ |
| 4 | A |
| 3 | B+ |
| 2 | B |
| 1 | C |
| 0 | D |

Scores within a grade are ranked by **3-star count → total stars → total percentage → earliest submission time**.

### Score Format

Scores are entered as `stars.percent`:
- `2.099` → 2 stars, 99%
- `2.50` → 2 stars, 50%
- `1.00` → 1 star, 0%

Valid star values: `0`–`3`. Valid percent values: `00`–`100` (2 or 3 digits).

---

## Tech Stack

| | |
|---|---|
| Language | Python 3.11+ |
| Discord library | discord.py 2.3+ |
| Database | PostgreSQL (Supabase) via `asyncpg` |
| HTTP client | aiohttp |
| Config | python-dotenv |
| Hosting | Render (keep-alive included) |

---

## Project Structure

```
CCExam/
├── main.py               # Bot entry point, loads cogs, syncs slash commands
├── config.py             # Env vars, district list, grade map
├── database.py           # asyncpg connection pool + all DB queries
├── link_checker.py       # Validates CoC layout share links + detects district from URL
├── keep_alive.py         # Lightweight HTTP server + self-ping loop for Render
├── requirements.txt      # Python dependencies
│
├── cogs/
│   ├── examiner.py       # All examiner-only slash commands + modals/views
│   ├── general.py        # Public commands: show_score, leaderboard, district_leaderboard, help
│   └── leaderboard.py    # Auto-updates the pinned live leaderboard embed
│
└── utils/
    ├── formatting.py     # Discord embed builders (score, leaderboard, show_score)
    └── validators.py     # Score parsing (x.xxx format) and grade/total calculation
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- A PostgreSQL database (e.g. [Supabase](https://supabase.com) free tier)
- A Discord bot application with the following intents enabled:
  - `Server Members Intent`
  - `Message Content Intent`

### 1. Clone the repo

```bash
git clone https://github.com/Preet-Kotak/CCExam.git
cd CCExam
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root (see [Environment Variables](#environment-variables) below).

### 4. Run the bot

```bash
python main.py
```

The bot will automatically create the required database tables on first run and sync slash commands to your guild.

---

## Environment Variables

Create a `.env` file with the following values:

```env
# Discord bot token (from Discord Developer Portal)
DISCORD_TOKEN=your_bot_token_here

# PostgreSQL connection string (e.g. from Supabase)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Your Discord server (guild) ID
GUILD_ID=123456789012345678

# Channel IDs
SCORE_RESULTS_CHANNEL_ID=123456789012345678   # Where score result embeds are posted
LEADERBOARD_CHANNEL_ID=123456789012345678     # Where the live leaderboard embed lives
END_SEASON_CHANNEL_ID=123456789012345678      # Where base summaries are posted on season end

# Role ID with examiner permissions
CC_EXAMINER_ROLE_ID=123456789012345678

# (Optional) For Render keep-alive self-ping
RENDER_URL=https://your-app.onrender.com
KEEPALIVE_INTERVAL=300   # Seconds between pings (default: 300)

# (Optional) HTTP server port for keep-alive (default: 8080)
PORT=8080
```

---

## Database Schema

Three tables are created automatically on startup:

**`seasons`** — One row per exam season.

| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | Auto-increment ID |
| `month` | VARCHAR | Season name, e.g. `"June 2025"` |
| `districts` | TEXT[] | Array of 5 selected district names |
| `is_active` | BOOLEAN | Whether the season is ongoing |
| `leaderboard_message_id` | BIGINT | Discord message ID of the live leaderboard |
| `leaderboard_channel_id` | BIGINT | Discord channel ID of the live leaderboard |
| `created_at` | TIMESTAMP | When the season was created |

**`bases`** — One row per district per season (replaced on re-upload).

| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | Auto-increment ID |
| `season_id` | INTEGER FK | References `seasons.id` |
| `district_name` | VARCHAR | Name of the district |
| `link` | TEXT | CoC layout share link |
| `screenshot_url` | TEXT | Discord attachment URL of the screenshot |

**`scores`** — One row per player per season.

| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | Auto-increment ID |
| `season_id` | INTEGER FK | References `seasons.id` |
| `player_id` | BIGINT | Discord user ID |
| `district_scores` | JSONB | `{ "District Name": { "stars": 3, "percent": 99 }, … }` |
| `total_stars` | INT | Sum of all district stars |
| `total_percent` | INT | Sum of all district percentages |
| `three_star_count` | INT | Number of districts with 3 stars (used for grading) |
| `grade` | VARCHAR | Calculated grade (A+, A, B+, B, C, D) |
| `result_message_id` | BIGINT | Discord message ID of the score result embed |
| `submitted_at` | TIMESTAMP | When the score was submitted |

---

## Deployment

The bot is designed to run on **[Render](https://render.com)** (free tier).

1. Push to GitHub and connect the repo to a new Render **Web Service**.
2. Set **Start Command** to `python main.py`.
3. Add all environment variables from the `.env` section in the Render dashboard.
4. Set `RENDER_URL` to your Render service URL — the bot will self-ping every 5 minutes to prevent the free tier from spinning down.

The built-in HTTP server in `keep_alive.py` responds to `GET /` with `Bot is alive!` and serves as Render's health check endpoint.

---

## Districts

The 9 available Clan Capital districts (in canonical order):

1. Capital Peak
2. Barbarian Camp
3. Wizard Valley
4. Balloon Lagoon
5. Builder's Workshop
6. Dragon Cliffs
7. Golem Quarry
8. Skeleton Park
9. Goblin Mines

Each season uses exactly **5** of these districts, chosen by the examiner when starting the season.

---

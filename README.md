# Project Manager

A lightweight project and task manager that runs entirely on your Mac — no cloud, no account needed.

## Features

- Projects with tasks, subtasks, owners, priorities, and dates
- Gantt chart (day / week / month / quarter zoom)
- Grid view with parent/child task hierarchy and collapse
- Export to Excel, PowerPoint, PDF
- Radar integration (Apple internal)
- Status report generation

## Setup

**Requires Python 3.9+**

```bash
# 1. Clone the repo
git clone https://github.com/abhinav-mitra/pm-tool
cd pm-tool

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Run
python3 app.py

# 4. Open in browser
open http://localhost:5000
```

## Updating

```bash
git pull
python3 app.py
```

Your data lives in `pm.db` (SQLite) on your own Mac and is never shared.

## Customization

Fork the repo to make your own changes. The entire app is two files:
- `app.py` — Flask backend + REST API
- `templates/index.html` — Single-page frontend

## License

MIT

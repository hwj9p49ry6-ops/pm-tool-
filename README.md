# Project Manager

A lightweight project and task manager that runs entirely on your Mac — no cloud, no account needed.

## Features

- Projects with tasks, subtasks, owners, priorities, and dates
- Gantt chart (day / week / month / quarter zoom)
- Grid view with parent/child task hierarchy and collapse
- Export to Excel, PowerPoint, PDF
- Status report generation

## Setup (one time)

**Requires Python 3.9+**

```bash
# 1. Clone the repo
git clone https://github.com/hwj9p49ry6-ops/pm-tool-.git
cd pm-tool-

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Run
python3 app.py

# 4. Open in browser
open http://localhost:5000
```

## Getting updates

When new changes are available:

```bash
cd pm-tool-
git pull
python3 app.py
```

## Your data

Your projects and tasks are stored in `pm.db` on your own Mac. Nothing is shared or uploaded anywhere.

## Customization

Fork the repo to make your own changes. The entire app is two files:
- `app.py` — Flask backend + REST API
- `templates/index.html` — Single-page frontend

## License

MIT

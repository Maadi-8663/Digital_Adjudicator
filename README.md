# Digital Adjudicator

A web application for managing debating tournaments at universities. Built for the Literary and Debating Society of UET Lahore (LDS).

## Stack

- **Python 3.11+** with **Flask**
- **SQLite** via SQLAlchemy
- **Flask-Login** for sessions
- **Flask-WTF** for form validation and CSRF
- **Flask-SocketIO** for the real-time stopwatch (Phase 3)
- **Lora** + **Playfair Display** + **Cormorant Garamond** Google Fonts

## Local setup

```bash
# 1. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Save the background image
# Place your literary-style background at:
#   app/static/img/background.jpg

# 4. Run the app
python run.py
```

The app will be available at http://localhost:5000.

## Project structure

```
DigitalAdjudicator_App/
├── app/
│   ├── __init__.py            # App factory and extensions
│   ├── models.py              # SQLAlchemy models
│   ├── auth/                  # Login, register, logout
│   ├── admin/                 # (Phase 2)
│   ├── judge/                 # (Phase 3)
│   ├── participant/           # (Phase 4)
│   ├── static/css/style.css   # Literary theme
│   └── templates/             # Jinja2 templates
├── instance/                  # SQLite database (gitignored)
├── config.py
├── requirements.txt
└── run.py
```

## Roadmap

- **Phase 1** (this commit) - foundation, auth, base UI
- **Phase 2** - admin module, competition CRUD, motion release
- **Phase 3** - judge module, scoring, real-time stopwatch
- **Phase 4** - participant module, break calculation, COI detection

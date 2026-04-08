# Benchmark2A

Flask multi-page web application with MySQL database connectivity and role-based login.

## Files Included

- `app.py`
- `hashgen.py`
- `4.6.sql`
- `templates/`
- `static/`
- `js/`

## Requirements

- Python 3
- MySQL Server
- MySQL Workbench or MySQL CLI

## Setup

Open Terminal and run:

```bash
cd "/path/to/Benchmark2A"
python3 -m venv .venv
source .venv/bin/activate
pip install Flask Flask-Login Flask-MySQLdb mysqlclient

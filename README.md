# LabShare

LabShare is a campus resource sharing platform for discovering research equipment and shared facilities across Indian colleges and research institutions. It brings the catalog, booking requests, facility management, and activity history into one web application.

## Features

- Search and filter research equipment by name, category, availability, and institution.
- View facility details, operating conditions, pricing, and access requirements.
- Request, review, approve, reject, waitlist, and cancel bookings.
- Manage facility listings and booking activity through owner and administrator views.
- Record check-in, return, and incident details with photo uploads.
- Review an append-only activity ledger and basic billing calculations.
- Browse a source-checked demonstration catalog for IISc Bangalore, IIT Bombay, IIT Delhi, and TIFR Mumbai.

## Technology

- Python 3.10+
- Flask and Flask-Login
- Flask-SQLAlchemy / SQLAlchemy
- SQLite by default; another SQLAlchemy-supported database can be configured with `DATABASE_URL`
- Jinja templates and CSS for the web interface

## Run locally

1. Clone the repository and enter the project directory.

   ```bash
   git clone <repository-url>
   cd lab-share
   ```

2. Create and activate a virtual environment.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. Install the dependencies.

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Set a development secret key. `DATABASE_URL` is optional; without it, the app uses a local SQLite database.

   ```bash
   export SECRET_KEY="replace-this-with-a-local-secret"
   # Optional, for a separate SQLite database:
   # export DATABASE_URL="sqlite:///campus.db"
   ```

5. Create the sample data and start the development server.

   ```bash
   python seed.py
   python run.py
   ```

6. Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

`seed.py` drops and recreates all database tables before inserting demo data. Use it only with a disposable local database; it will erase existing records in the database selected by `DATABASE_URL`.

The application creates database tables when it starts. To add or refresh the source-checked catalog without resetting accounts, bookings, or audit history, run:

```bash
python scripts/populate_verified_catalog.py
```

The catalog script is designed to be idempotent. Back up important data before making database changes.

## Demo accounts

The seed script creates the following accounts. These credentials are for local demonstrations only; change or remove them before any shared deployment.

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@iisc.ac.in` | `admin1234` |
| Facility owner | `rajesh.raman@iisc.ac.in` | `owner1234` |
| Facility owner | `sunita.k@iitb.ac.in` | `owner1234` |
| Researcher | `ananya.d@iisc.ac.in` | `student1234` |
| Researcher | `rohan.sen@iitb.ac.in` | `student1234` |
| Researcher | `priya.nair@iitd.ac.in` | `student1234` |

## Configuration

Configuration is read from environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session signing key | Development-only fallback in `app/config.py` |
| `DATABASE_URL` | SQLAlchemy database connection URL | SQLite database at the project root |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated allowed institutional email suffixes | `.ac.in,.edu.in,.res.in,.edu,.ernet.in` |

For deployment, set a unique secret key, use a managed database, serve the app behind a production WSGI server and HTTPS, and review upload storage and access controls. `python run.py` starts Flask's debug development server and is intended only for local development.

## Verification

Run the included phase checks with:

```bash
python test_all_phases.py
```

The checks may create or modify database records. Run them against a disposable database by setting `DATABASE_URL` first.

## Integrations and demo behavior

DNS domain verification and AI compliance scanning are currently mocked for demonstration. They do not perform live DNS verification or an external AI review. Booking payment calculations are application-side estimates; no payment processor is connected.

## Project layout

```text
app/
  blueprints/    Authentication, catalog, booking, custody, audit, admin, billing routes
  services/      Booking, catalog, authentication, uploads, billing, custody, audit logic
  templates/     Jinja templates
  static/        Stylesheets and catalog images
scripts/         Catalog population utilities
seed.py          Rebuilds the local demo database and sample data
test_all_phases.py
requirements.txt
```

## License

No license file is currently included. All rights remain with the project authors unless a license is added to this repository.

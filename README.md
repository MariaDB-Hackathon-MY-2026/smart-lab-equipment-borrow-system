
# lendr+ Smart Lab Equipment Borrow System


  A role-based Django platform for managing laboratory equipment borrowing, returns, penalties, Stripe payments, and automated email reminders.


## Table of Contents

- [Overview](#overview)
- [Core Features](#core-features)
- [System Workflow](#system-workflow)
- [Technology Stack](#technology-stack)
- [Application Structure](#application-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Scheduled Notifications](#scheduled-notifications)
- [Stripe Payment Setup](#stripe-payment-setup)
- [Email Setup](#email-setup)
- [Testing](#testing)
- [GitHub Actions CI](#github-actions-ci)
- [Render Deployment](#render-deployment)
- [Operational Notes](#operational-notes)

## Overview

lendr+ is a smart laboratory equipment borrowing system designed for academic and faculty environments where equipment availability, borrower accountability, approval control, and penalty tracking matter.

The system separates user and administrator responsibilities. Users can browse available lab equipment, submit borrowing requests, return borrowed items, and pay penalties through Stripe Checkout. Administrators can manage the equipment manifest, approve or deny borrow requests, complete returns, apply return-related penalties, and resolve unpaid penalties through a controlled one-way status flow.

The platform also includes automated email notifications for request submission, approval, return reminders, completed returns, and penalty status updates.

## Core Features

### User Portal

- Browse available lab equipment with category, location, condition, status, and daily penalty rate.
- Submit single or bulk borrowing requests.
- View personal lending history and request details.
- Request return for currently borrowed equipment.
- View penalties in a floating modal.
- Pay unpaid penalties using Stripe hosted Checkout.
- Borrowing is blocked when the user has unsettled penalties.

### Administrator Portal

- Manage the equipment manifest.
- Create, edit, soft-delete, and categorize equipment.
- Prevent deletion of equipment that is currently borrowed.
- Review, approve, and deny borrowing requests.
- Mark approved requests as borrowed using a time-limited borrow code.
- Complete returns after the user submits a return request.
- Apply product return penalties during return completion.
- View all penalties in a floating modal.
- Mark unpaid penalties as paid or waived.
- Lock settled penalties so paid or waived decisions cannot be reversed.

### Penalty Management

- Automatic late penalty calculation based on the equipment daily penalty rate.
- Product return penalty support for damaged, incomplete, or problematic returns.
- Combined penalty formula:

```text
Total Penalty = (Late Penalty Rate x Days Overdue) + Product Return Penalty
```

- Daily unpaid penalty reminders until settlement.
- One-way status lifecycle: `Unpaid -> Paid` or `Unpaid -> Waived`.

### Email Notifications

- User and admin are notified when a borrow request is submitted.
- User is notified when a borrow request is approved.
- User receives return reminders:
  - 2 days before return date
  - 1 day before return date
  - On the return date
- User receives post-return email with penalty details when applicable.
- User receives email when a penalty is paid or waived.
- User receives daily reminders while a penalty remains unpaid.

## System Workflow

```text
User submits borrow request
        |
        v
Admin reviews request
        |
        +--> Denied
        |
        +--> Approved
                |
                v
User receives borrow code / admin marks item as borrowed
                |
                v
User submits return request
                |
                v
Admin completes return
                |
                +--> No penalty -> Return complete
                |
                +--> Penalty created -> User pays via Stripe or admin marks paid/waived
```

## Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Django 6.0.4 |
| Language | Python 3.13 |
| Database | MariaDB / MySQL via PyMySQL |
| Payments | Stripe Checkout |
| Email | Django email backend, SMTP compatible |
| Frontend | Django Templates, HTML, CSS, JavaScript |
| Authentication | Django Auth with role-aware profiles |
| Scheduling | Django management command, Windows Task Scheduler or cron |

## Application Structure

```text
smart-lab-equipment-borrow-system/
├── accounts/              # Authentication, profiles, roles, dashboards
├── equipment/             # Equipment catalog, manifest, categories
├── lending/               # Borrow requests, returns, penalties, payments
├── lendr/                 # Django project settings and root URLs
├── static/                # CSS, images, branding assets
├── templates/             # Shared layout templates
├── manage.py              # Django command entry point
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation
```

## Getting Started

### Prerequisites

Install the following before running the project:

- Python 3.13 or newer
- MariaDB or MySQL
- pip
- A Stripe test account for penalty payment testing
- SMTP credentials if email sending is required outside console mode

### Installation

Clone or open the project directory:

```powershell
cd "C:\Users\Lenovo ThinkPad T14\Desktop\Lendr\smart-lab-equipment-borrow-system"
```

Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root. Do not commit this file because it contains secrets.

```env
# Django
DEBUG=True
SECRET_KEY=django-insecure-change-this-for-local-development
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

# Database
DB_NAME=lendr
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=127.0.0.1
DB_PORT=3306
DB_SSL=false

# Stripe
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_CURRENCY=myr

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_smtp_username
EMAIL_HOST_PASSWORD=your_smtp_password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=lendr+ <no-reply@example.com>
```

For local development without SMTP, omit the email values and Django will use the console email backend where configured.

## Database Setup

Create the database in MariaDB or MySQL:

```sql
CREATE DATABASE lendr CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Apply Django migrations:

```powershell
venv\Scripts\python.exe manage.py migrate
```

Create an administrator account:

```powershell
venv\Scripts\python.exe manage.py createsuperuser
```

Seed default groups, categories, and sample equipment:

```powershell
venv\Scripts\python.exe manage.py seed_lendr
```

## Running the Application

Start the development server:

```powershell
venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Open the application:

```text
http://127.0.0.1:8000/
```

To test from another device on the same WiFi network, run the server on all interfaces:

```powershell
venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Then open:

```text
http://YOUR_LAPTOP_IP:8000/
```

## Scheduled Notifications

The system includes a daily management command that:

- Refreshes overdue requests and penalty amounts.
- Sends return reminders for bookings due in 2 days, 1 day, or today.
- Sends daily unpaid penalty reminders.

Run manually:

```powershell
venv\Scripts\python.exe manage.py send_lending_notifications
```

For production or realistic local testing, schedule this command once per day using Windows Task Scheduler, cron, or your hosting platform's scheduler.

Example Windows Task Scheduler values:

```text
Program:
C:\Users\Lenovo ThinkPad T14\Desktop\Lendr\smart-lab-equipment-borrow-system\venv\Scripts\python.exe

Arguments:
manage.py send_lending_notifications

Start in:
C:\Users\Lenovo ThinkPad T14\Desktop\Lendr\smart-lab-equipment-borrow-system
```

## Stripe Payment Setup

lendr+ uses Stripe hosted Checkout for penalty payments. This keeps payment handling secure and avoids storing card details inside the application.

1. Create or log in to a Stripe account.
2. Enable test mode.
3. Copy the test secret key and publishable key.
4. Add both keys to `.env`.
5. Restart the Django server after changing `.env`.

Required variables:

```env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_CURRENCY=myr
```

Payment lifecycle:

```text
User clicks Pay
        |
        v
Django creates Stripe Checkout Session
        |
        v
User completes payment on Stripe
        |
        v
Stripe redirects back to lendr+
        |
        v
Penalty is marked as Paid
```

## Email Setup

Email delivery is handled through Django's email backend. The project supports SMTP providers such as Brevo, Gmail SMTP, or any equivalent transactional email service.

To test email delivery:

```powershell
venv\Scripts\python.exe manage.py send_test_email your_email@example.com
```

If the email does not arrive:

- Confirm the SMTP username and password are correct.
- Confirm the sender email is verified by the email provider.
- Restart the Django server after changing `.env`.
- Check spam or junk folders.

## Testing

Run the Django system checks:

```powershell
venv\Scripts\python.exe manage.py check
```

Run the application tests:

```powershell
venv\Scripts\python.exe manage.py test equipment lending accounts
```

## GitHub Actions CI

The repository includes `.github/workflows/ci.yml`, following the lab CI pattern:

```text
push to GitHub -> install dependencies -> run python manage.py check
```

After pushing the repo to GitHub, open the repository Actions tab and confirm the latest `Django CI` run is green before deploying.

## Render Deployment

This project is prepared for Render using the lab workflow:

1. Commit the deployment files: `build.sh`, `render.yaml`, `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`, and the updated settings.
2. Push the `updated-application` branch to GitHub.
3. In Render, create a new Web Service from the GitHub repository, or use Render Blueprints with `render.yaml`.
4. Use these service commands if creating the Web Service manually:

```text
Build Command: bash build.sh
Start Command: gunicorn lendr.wsgi:application
```

5. Add the required Render environment variables:

```env
DEBUG=False
SECRET_KEY=<generate in Render>
DJANGO_ALLOWED_HOSTS=.onrender.com
CSRF_TRUSTED_ORIGINS=https://*.onrender.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
DB_NAME=<production database name>
DB_USER=<production database user>
DB_PASSWORD=<production database password>
DB_HOST=<production database host>
DB_PORT=3306
DB_SSL=True
STRIPE_SECRET_KEY=<stripe secret key>
STRIPE_PUBLISHABLE_KEY=<stripe publishable key>
STRIPE_CURRENCY=myr
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp username>
EMAIL_HOST_PASSWORD=<smtp password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=<verified sender email>
```

6. Deploy the latest GitHub commit. Render will install dependencies, collect static files, apply migrations, and start Gunicorn.
7. After the first successful deploy, open the Render Shell and create the production admin account:

```bash
python manage.py createsuperuser
```

The app uses MariaDB/MySQL. Render's native managed database is PostgreSQL, so keep using a MySQL-compatible production database provider and place those credentials in Render's environment variables.

## Operational Notes

- Keep `.env` private and never commit real credentials.
- Use Stripe test keys during development.
- Use HTTPS in production.
- Keep `DEBUG=False` in production.
- Configure `DJANGO_ALLOWED_HOSTS` for the deployed domain.
- Use a real scheduler for daily notification delivery.
- Back up the database regularly because borrowing history and penalty records are operational records.
- Settled penalties are intentionally irreversible from the admin interface for audit integrity.

## Project Status

This project is actively developed as a smart lab borrowing workflow system. The current implementation focuses on a complete internal borrowing lifecycle: request, approval, borrowing, return, penalty assessment, payment, and notification.

## License

No license has been specified yet. Add a license before distributing or publishing this project publicly.



from datetime import date, datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Message
from app_package import db, mail
from app_package.models import User, Vehicle, Document, ReminderLog


def check_expiry_and_send_reminders(app):
    """Daily job: find expiring documents and send email reminders."""
    with app.app_context():
        today = date.today()
        users = db.session.query(User).all()

        for user in users:
            vehicles = db.session.query(Vehicle).filter_by(user_id=user.id, is_active=True).all()
            vehicle_ids = [v.id for v in vehicles]
            if not vehicle_ids:
                continue

            # Find documents expiring within their reminder_days
            docs = db.session.query(Document).filter(
                Document.vehicle_id.in_(vehicle_ids),
                Document.status == "active",
                Document.expiry_date.isnot(None),
            ).all()

            expiring_docs = []
            for doc in docs:
                days_left = (doc.expiry_date - today).days
                if days_left <= doc.reminder_days:
                    # Check if already emailed today
                    already_sent = db.session.query(ReminderLog).filter(
                        ReminderLog.document_id == doc.id,
                        ReminderLog.reminder_type == "email",
                        db.func.date(ReminderLog.sent_at) == today,
                    ).first()
                    if not already_sent:
                        expiring_docs.append((doc, days_left))

            if not expiring_docs:
                continue

            # Build and send email
            try:
                lines = []
                for doc, days_left in expiring_docs:
                    vehicle = doc.vehicle
                    if days_left < 0:
                        status = f"EXPIRED ({abs(days_left)} days ago)"
                    elif days_left == 0:
                        status = "EXPIRES TODAY"
                    else:
                        status = f"Expires in {days_left} days"

                    lines.append(
                        f"- {vehicle.registration_number} | {doc.doc_type_label} | "
                        f"Expiry: {doc.expiry_date.strftime('%d %b %Y')} | {status}"
                    )

                body = (
                    f"Hello {user.name},\n\n"
                    f"The following vehicle documents need your attention:\n\n"
                    + "\n".join(lines)
                    + "\n\nPlease renew them at the earliest.\n\n"
                    "— Vehicle Tracker"
                )

                msg = Message(
                    subject="Vehicle Document Expiry Reminder",
                    recipients=[user.email],
                    body=body,
                )
                mail.send(msg)

                # Log reminders
                for doc, days_left in expiring_docs:
                    log = ReminderLog(
                        document_id=doc.id,
                        reminder_type="email",
                        message=f"Expiry reminder sent. {days_left} days remaining.",
                    )
                    db.session.add(log)

                db.session.commit()

            except Exception as e:
                print(f"[Reminder] Failed to send email to {user.email}: {e}")


def start_scheduler(app):
    """Start APScheduler with daily expiry check at 8:00 AM."""
    # Only start in the main process (avoid double-start with Flask reloader)
    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and app.debug:
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=check_expiry_and_send_reminders,
        args=[app],
        trigger="cron",
        hour=8,
        minute=0,
        id="expiry_reminder",
        replace_existing=True,
    )
    scheduler.start()

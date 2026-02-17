from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app_package import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    password_hash = db.Column(db.String(256), nullable=False)
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vehicles = db.relationship("Vehicle", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    registration_number = db.Column(db.String(20), nullable=False)
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.Integer)
    vehicle_type = db.Column(db.String(20))  # car/bike/truck/bus/auto
    fuel_type = db.Column(db.String(20))  # petrol/diesel/cng/electric
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship("Document", backref="vehicle", lazy=True, cascade="all, delete-orphan")

    @property
    def nearest_expiry(self):
        today = date.today()
        active_docs = [d for d in self.documents if d.expiry_date and d.status == "active"]
        if not active_docs:
            return None
        return min(active_docs, key=lambda d: d.expiry_date)


class Document(db.Model):
    __tablename__ = "documents"

    DOC_TYPES = ["rc", "insurance", "puc", "fitness", "permit", "tax", "dl"]
    DOC_TYPE_LABELS = {
        "rc": "Registration Certificate",
        "insurance": "Insurance",
        "puc": "PUC Certificate",
        "fitness": "Fitness Certificate",
        "permit": "Permit",
        "tax": "Road Tax",
        "dl": "Driving License",
    }

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    doc_type = db.Column(db.String(20), nullable=False)
    doc_number = db.Column(db.String(50))
    issuer = db.Column(db.String(100))
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    file_path = db.Column(db.String(256))
    file_type = db.Column(db.String(10))
    ocr_extracted_date = db.Column(db.String(50))
    reminder_days = db.Column(db.Integer, default=30)
    status = db.Column(db.String(20), default="active")  # active/expired/renewed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reminder_logs = db.relationship("ReminderLog", backref="document", lazy=True, cascade="all, delete-orphan")

    @property
    def doc_type_label(self):
        return self.DOC_TYPE_LABELS.get(self.doc_type, self.doc_type.upper())

    @property
    def days_remaining(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def urgency(self):
        days = self.days_remaining
        if days is None:
            return "unknown"
        if days < 0:
            return "expired"
        if days <= 30:
            return "warning"
        return "valid"


class ReminderLog(db.Model):
    __tablename__ = "reminder_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    reminder_type = db.Column(db.String(20))  # dashboard/email
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    message = db.Column(db.Text)

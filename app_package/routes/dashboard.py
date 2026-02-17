from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app_package import db
from app_package.models import Vehicle, Document

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    vehicles = db.session.query(Vehicle).filter_by(user_id=current_user.id, is_active=True).all()
    vehicle_ids = [v.id for v in vehicles]

    documents = db.session.query(Document).filter(
        Document.vehicle_id.in_(vehicle_ids),
        Document.status == "active",
        Document.expiry_date.isnot(None),
    ).order_by(Document.expiry_date.asc()).all()

    today = date.today()
    total_vehicles = len(vehicles)
    total_docs = len(documents)
    expired = [d for d in documents if d.expiry_date < today]
    expiring_soon = [d for d in documents if 0 <= (d.expiry_date - today).days <= 30]

    return render_template(
        "dashboard.html",
        vehicles=vehicles,
        documents=documents,
        total_vehicles=total_vehicles,
        total_docs=total_docs,
        expired_count=len(expired),
        expiring_soon_count=len(expiring_soon),
        today=today,
    )

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app_package import db
from app_package.models import Vehicle

vehicles_bp = Blueprint("vehicles", __name__, url_prefix="/vehicles")

VEHICLE_TYPES = ["car", "bike", "truck", "bus", "auto"]
FUEL_TYPES = ["petrol", "diesel", "cng", "electric"]


@vehicles_bp.route("/")
@login_required
def list_vehicles():
    vehicles = db.session.query(Vehicle).filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(Vehicle.created_at.desc()).all()
    return render_template("vehicles/list.html", vehicles=vehicles)


@vehicles_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_vehicle():
    if request.method == "POST":
        vehicle = Vehicle(
            user_id=current_user.id,
            registration_number=request.form.get("registration_number", "").strip().upper(),
            make=request.form.get("make", "").strip(),
            model=request.form.get("model", "").strip(),
            year=int(request.form["year"]) if request.form.get("year") else None,
            vehicle_type=request.form.get("vehicle_type"),
            fuel_type=request.form.get("fuel_type"),
            notes=request.form.get("notes", "").strip(),
        )
        if not vehicle.registration_number:
            flash("Registration number is required.", "danger")
            return render_template("vehicles/form.html", vehicle=None,
                                   vehicle_types=VEHICLE_TYPES, fuel_types=FUEL_TYPES)

        db.session.add(vehicle)
        db.session.commit()
        flash("Vehicle added successfully.", "success")
        return redirect(url_for("vehicles.list_vehicles"))

    return render_template("vehicles/form.html", vehicle=None,
                           vehicle_types=VEHICLE_TYPES, fuel_types=FUEL_TYPES)


@vehicles_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_vehicle(id):
    vehicle = db.session.get(Vehicle, id)
    if not vehicle or vehicle.user_id != current_user.id:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("vehicles.list_vehicles"))

    if request.method == "POST":
        vehicle.registration_number = request.form.get("registration_number", "").strip().upper()
        vehicle.make = request.form.get("make", "").strip()
        vehicle.model = request.form.get("model", "").strip()
        vehicle.year = int(request.form["year"]) if request.form.get("year") else None
        vehicle.vehicle_type = request.form.get("vehicle_type")
        vehicle.fuel_type = request.form.get("fuel_type")
        vehicle.notes = request.form.get("notes", "").strip()

        if not vehicle.registration_number:
            flash("Registration number is required.", "danger")
            return render_template("vehicles/form.html", vehicle=vehicle,
                                   vehicle_types=VEHICLE_TYPES, fuel_types=FUEL_TYPES)

        db.session.commit()
        flash("Vehicle updated.", "success")
        return redirect(url_for("vehicles.list_vehicles"))

    return render_template("vehicles/form.html", vehicle=vehicle,
                           vehicle_types=VEHICLE_TYPES, fuel_types=FUEL_TYPES)


@vehicles_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_vehicle(id):
    vehicle = db.session.get(Vehicle, id)
    if not vehicle or vehicle.user_id != current_user.id:
        flash("Vehicle not found.", "danger")
        return redirect(url_for("vehicles.list_vehicles"))

    db.session.delete(vehicle)
    db.session.commit()
    flash("Vehicle deleted.", "success")
    return redirect(url_for("vehicles.list_vehicles"))

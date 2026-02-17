import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from app_package import db
from app_package.models import Vehicle, Document
from app_package.ocr_utils import extract_expiry_from_image

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@documents_bp.route("/")
@login_required
def list_documents():
    vehicle_id = request.args.get("vehicle_id", type=int)
    vehicles = db.session.query(Vehicle).filter_by(user_id=current_user.id, is_active=True).all()
    vehicle_ids = [v.id for v in vehicles]

    query = db.session.query(Document).filter(Document.vehicle_id.in_(vehicle_ids))
    if vehicle_id:
        query = query.filter(Document.vehicle_id == vehicle_id)

    documents = query.order_by(Document.expiry_date.asc()).all()
    return render_template("documents/list.html", documents=documents, vehicles=vehicles,
                           selected_vehicle_id=vehicle_id)


@documents_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    vehicles = db.session.query(Vehicle).filter_by(user_id=current_user.id, is_active=True).all()

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        doc_type = request.form.get("doc_type")
        file = request.files.get("file")

        # Validate vehicle belongs to user
        vehicle = db.session.get(Vehicle, vehicle_id) if vehicle_id else None
        if not vehicle or vehicle.user_id != current_user.id:
            flash("Invalid vehicle selected.", "danger")
            return render_template("documents/upload.html", vehicles=vehicles,
                                   doc_types=Document.DOC_TYPES, doc_type_labels=Document.DOC_TYPE_LABELS)

        if not doc_type or doc_type not in Document.DOC_TYPES:
            flash("Invalid document type.", "danger")
            return render_template("documents/upload.html", vehicles=vehicles,
                                   doc_types=Document.DOC_TYPES, doc_type_labels=Document.DOC_TYPE_LABELS)

        # Handle file upload
        file_path = None
        file_type = None
        ocr_date = None
        ocr_text = None

        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)
            file_path = filename
            file_type = ext if ext != "jpeg" else "jpg"

            # Run OCR on images
            if ext in ("jpg", "jpeg", "png"):
                ocr_date, ocr_text = extract_expiry_from_image(save_path)

        # Parse manual dates
        issue_date = None
        expiry_date = None
        if request.form.get("issue_date"):
            try:
                issue_date = datetime.strptime(request.form["issue_date"], "%Y-%m-%d").date()
            except ValueError:
                pass
        if request.form.get("expiry_date"):
            try:
                expiry_date = datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

        # Use OCR date if no manual date provided
        if not expiry_date and ocr_date:
            expiry_date = ocr_date

        doc = Document(
            vehicle_id=vehicle_id,
            doc_type=doc_type,
            doc_number=request.form.get("doc_number", "").strip(),
            issuer=request.form.get("issuer", "").strip(),
            issue_date=issue_date,
            expiry_date=expiry_date,
            file_path=file_path,
            file_type=file_type,
            ocr_extracted_date=ocr_date.strftime("%d/%m/%Y") if ocr_date else None,
            reminder_days=int(request.form.get("reminder_days", 30)),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(doc)
        db.session.commit()

        if ocr_date:
            flash(f"Document uploaded. OCR detected expiry date: {ocr_date.strftime('%d/%m/%Y')}. Please verify.", "info")
        else:
            flash("Document uploaded successfully.", "success")

        return redirect(url_for("documents.view_document", id=doc.id))

    preselect_vehicle = request.args.get("vehicle_id", type=int)
    return render_template("documents/upload.html", vehicles=vehicles,
                           doc_types=Document.DOC_TYPES, doc_type_labels=Document.DOC_TYPE_LABELS,
                           preselect_vehicle=preselect_vehicle)


@documents_bp.route("/<int:id>")
@login_required
def view_document(id):
    doc = db.session.get(Document, id)
    if not doc or doc.vehicle.user_id != current_user.id:
        flash("Document not found.", "danger")
        return redirect(url_for("documents.list_documents"))
    return render_template("documents/view.html", doc=doc)


@documents_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_document(id):
    doc = db.session.get(Document, id)
    if not doc or doc.vehicle.user_id != current_user.id:
        flash("Document not found.", "danger")
        return redirect(url_for("documents.list_documents"))

    if request.method == "POST":
        doc.doc_number = request.form.get("doc_number", "").strip()
        doc.issuer = request.form.get("issuer", "").strip()
        doc.reminder_days = int(request.form.get("reminder_days", 30))
        doc.status = request.form.get("status", "active")
        doc.notes = request.form.get("notes", "").strip()

        if request.form.get("issue_date"):
            try:
                doc.issue_date = datetime.strptime(request.form["issue_date"], "%Y-%m-%d").date()
            except ValueError:
                pass
        if request.form.get("expiry_date"):
            try:
                doc.expiry_date = datetime.strptime(request.form["expiry_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

        db.session.commit()
        flash("Document updated.", "success")
        return redirect(url_for("documents.view_document", id=doc.id))

    vehicles = db.session.query(Vehicle).filter_by(user_id=current_user.id, is_active=True).all()
    return render_template("documents/upload.html", vehicles=vehicles,
                           doc_types=Document.DOC_TYPES, doc_type_labels=Document.DOC_TYPE_LABELS,
                           doc=doc, editing=True)


@documents_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete_document(id):
    doc = db.session.get(Document, id)
    if not doc or doc.vehicle.user_id != current_user.id:
        flash("Document not found.", "danger")
        return redirect(url_for("documents.list_documents"))

    # Delete uploaded file
    if doc.file_path:
        file_full = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.file_path)
        if os.path.exists(file_full):
            os.remove(file_full)

    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted.", "success")
    return redirect(url_for("documents.list_documents"))


@documents_bp.route("/file/<filename>")
@login_required
def serve_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

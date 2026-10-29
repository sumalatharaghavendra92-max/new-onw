from app import db
import enum

class ApprovalStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    blocked = "blocked"

class Driver(db.Model):
    __tablename__ = 'drivers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    dob = db.Column(db.Date)
    address = db.Column(db.Text)
    license_no = db.Column(db.String(50), unique=True)
    experience_years = db.Column(db.Integer)
    emergency_contact = db.Column(db.String(100))
    profile_photo_url = db.Column(db.String(255))
    license_doc_url = db.Column(db.String(255))
    address_proof_url = db.Column(db.String(255))
    approval_status = db.Column(db.Enum(ApprovalStatus), default=ApprovalStatus.pending)
    rejection_reason = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    eco_score = db.Column(db.Float, default=0.0)

    user = db.relationship('User', foreign_keys=[user_id], backref='driver_profile')
    approver = db.relationship('User', foreign_keys=[approved_by])

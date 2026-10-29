from app import db

class EmailOTP(db.Model):
    __tablename__ = 'email_otps'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)
    code_hash = db.Column(db.String(256), nullable=False)
    expires_at = db.Column(db.Float, nullable=False)
    sent_at = db.Column(db.Float, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint('email', 'purpose'),)

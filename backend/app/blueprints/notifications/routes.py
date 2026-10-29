from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Notification, User

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = get_jwt_identity()
    # Get unread notifications or all, sort by newest
    notifs = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(50).all()
    
    return jsonify([{
        "id": n.id,
        "type": n.type,
        "title": (n.type or 'notification').replace('_', ' ').title(),
        "message": n.message,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat()
    } for n in notifs]), 200

@notifications_bp.route('/<int:notif_id>/read', methods=['PATCH'])
@jwt_required()
def mark_read(notif_id):
    user_id = get_jwt_identity()
    notif = Notification.query.filter_by(id=notif_id, user_id=user_id).first()
    
    if not notif:
        return jsonify({"error": "not_found"}), 404
        
    notif.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read"}), 200

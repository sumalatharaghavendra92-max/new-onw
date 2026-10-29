from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask import jsonify
from app.models import User, UserStatus
from app import db

def role_required(required_role):
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = db.session.get(User, int(user_id))
            
            if not user or user.status != UserStatus.active or user.role.value != required_role:
                return jsonify({"error": "forbidden", "message": "Insufficient permissions"}), 403
                
            return fn(*args, **kwargs)
        return decorator
    return wrapper

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db, limiter
from app.models import User, UserStatus
from app.services.live_context import get_live_context

context_bp = Blueprint('context', __name__)


@context_bp.get('/weather')
@jwt_required()
@limiter.limit('30 per minute')
def weather():
    try:
        user = db.session.get(User, int(get_jwt_identity()))
    except (ValueError, TypeError):
        user = None
    if not user or user.status != UserStatus.active:
        return jsonify(message='An active account is required.'), 403
    try:
        result = get_live_context(request.args.get('latitude'), request.args.get('longitude'))
    except ValueError as exc:
        return jsonify(message=str(exc)), 422
    if result['status'] == 'unavailable':
        result['message'] = result['warning']
    return jsonify(result), 200 if result['status'] != 'unavailable' else 503

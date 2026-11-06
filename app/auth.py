"""Identidade compartilhada e permissões verificadas no banco."""
from datetime import datetime, timezone

from bson import ObjectId
from flask import current_app, session


def is_banned(user):
    ban = (user or {}).get('ban') or {}
    if ban.get('kind') == 'permanent':
        return True
    until = ban.get('until')
    if ban.get('kind') == 'temporary' and isinstance(until, datetime):
        return (until if until.tzinfo else until.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc)
    return False


def current_user():
    user_id = session.get('user_id')
    if not isinstance(user_id, str) or not ObjectId.is_valid(user_id):
        return None
    database = current_app.extensions['mongo_db']
    # Compatibilidade com administradores criados antes do login unificado.
    if session.get('account_source') == 'admins':
        user = database.admins.find_one({'_id': ObjectId(user_id)})
        if user:
            user['role'] = 'admin'
    else:
        user = database.users.find_one({'_id': ObjectId(user_id)})
    if user and (is_banned(user) or user.get('auth_version', 0) != session.get('auth_version', 0)):
        session.clear()
        return None
    return user


def is_admin(user):
    return bool(user and user.get('role') == 'admin')

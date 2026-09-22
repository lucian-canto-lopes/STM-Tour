"""Identidade compartilhada e permissões verificadas no banco."""
from bson import ObjectId
from flask import current_app, session


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
        return user
    return database.users.find_one({'_id': ObjectId(user_id)})


def is_admin(user):
    return bool(user and user.get('role') == 'admin')

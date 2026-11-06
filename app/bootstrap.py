"""Cadastro inicial opcional, configurado pelas variáveis do ambiente."""
import os

from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash


def create_initial_admin(app):
    email = os.getenv('INITIAL_ADMIN_EMAIL', '').strip().lower()
    password = os.getenv('INITIAL_ADMIN_PASSWORD', '')
    if not email and not password:
        return
    if not email or not password or '@' not in email or len(password) < 12:
        raise ValueError('Configure INITIAL_ADMIN_EMAIL e INITIAL_ADMIN_PASSWORD '
                         'com um e-mail válido e uma senha de pelo menos 12 caracteres.')

    database = app.extensions['mongo_db']
    if database.users.find_one({'email': email}) or database.admins.find_one({'email': email}):
        app.logger.info('Administrador inicial: e-mail já cadastrado; conta preservada.')
        return

    database.users.create_index('email', unique=True)
    try:
        database.users.insert_one({
            'name': 'Administrador',
            'email': email,
            'password_hash': generate_password_hash(password),
            'role': 'admin',
        })
    except DuplicateKeyError:
        # Outro worker pode ter criado a conta durante a inicialização.
        if not database.users.find_one({'email': email}):
            raise
        return
    app.logger.info('Administrador inicial criado com sucesso.')

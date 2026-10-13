"""Categorias e filtros compartilhados pelo mapa e pelos cadastros."""
import unicodedata
import re

from flask import current_app

CATEGORIES = {
    'praias': 'Praias',
    'cultura': 'Cultura',
    'gastronomia': 'Gastronomia',
    'natureza': 'Natureza',
    'outros': 'Outros',
}


def categories():
    result = dict(CATEGORIES)
    for item in current_app.extensions['mongo_db'].place_categories.find().sort('name', 1):
        if item['_id'] not in result:
            result[item['_id']] = item['name']
    return result


def new_category_name(values):
    return ' '.join(values.get('new_category', '').split())


def read_category(values):
    category = values.get('category', 'outros')
    available = categories()
    if category == 'outros' and new_category_name(values):
        name = new_category_name(values)
        if len(name) > 60:
            raise ValueError('O tipo de lugar deve ter até 60 caracteres.')
        for key, label in available.items():
            if normalized(label) == normalized(name):
                return key
        slug = re.sub(r'[^a-z0-9]+', '-', normalized(name)).strip('-')
        if not slug:
            raise ValueError('Informe um tipo de lugar com letras ou números.')
        return 'custom-' + slug
    if category not in available:
        raise ValueError('Selecione um tipo de lugar válido.')
    return category


def save_category(values, category):
    """Publica o tipo reutilizável somente após validar o cadastro inteiro."""
    if values.get('category') == 'outros' and new_category_name(values) and category not in CATEGORIES:
        current_app.extensions['mongo_db'].place_categories.update_one(
            {'_id': category}, {'$setOnInsert': {'name': new_category_name(values)}}, upsert=True)


def category_of(place):
    category = place.get('category', 'outros')
    return category if category in categories() else 'outros'


def normalized(value):
    return ''.join(char for char in unicodedata.normalize('NFD', value.casefold())
                   if not unicodedata.combining(char))


def map_places(query='', category=''):
    from app.contributions import public_places, public_place
    from app.location import coordinates
    results = []
    available = categories()
    terms = normalized(query).split()
    for entry in public_places():
        try:
            coordinates(entry)
        except ValueError:
            continue
        if category and category_of(entry) != category:
            continue
        place = public_place(str(entry['_id']))
        searchable = normalized(' '.join((place.get('name', ''), place.get('description', ''), available[category_of(place)])))
        if all(term in searchable for term in terms):
            results.append(place)
    return results

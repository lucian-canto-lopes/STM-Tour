"""Categorias e filtros compartilhados pelo mapa e pelos cadastros."""
import unicodedata

CATEGORIES = {
    'praias': 'Praias',
    'cultura': 'Cultura',
    'gastronomia': 'Gastronomia',
    'natureza': 'Natureza',
    'outros': 'Outros',
}


def read_category(values):
    category = values.get('category', 'outros')
    if category not in CATEGORIES:
        raise ValueError('Selecione um tipo de lugar válido.')
    return category


def category_of(place):
    category = place.get('category', 'outros')
    return category if category in CATEGORIES else 'outros'


def normalized(value):
    return ''.join(char for char in unicodedata.normalize('NFD', value.casefold())
                   if not unicodedata.combining(char))


def map_places(query='', category=''):
    from app.contributions import public_places, public_place
    from app.location import coordinates
    results = []
    terms = normalized(query).split()
    for entry in public_places():
        try:
            coordinates(entry)
        except ValueError:
            continue
        if category and category_of(entry) != category:
            continue
        place = public_place(str(entry['_id']))
        searchable = normalized(' '.join((place.get('name', ''), place.get('description', ''), CATEGORIES[category_of(place)])))
        if all(term in searchable for term in terms):
            results.append(place)
    return results

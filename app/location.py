"""Coordenadas compartilhadas pelos cadastros e mapas."""
import math


def coordinates(values, required=True):
    latitude = str(values.get('latitude', '')).strip().replace(',', '.')
    longitude = str(values.get('longitude', '')).strip().replace(',', '.')
    if not required and not latitude and not longitude:
        return {}
    try:
        lat, lng = float(latitude), float(longitude)
        if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Informe latitude entre -90 e 90 e longitude entre -180 e 180, ou escolha um ponto no mapa.') from None
    return {'latitude': lat, 'longitude': lng}

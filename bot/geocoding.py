"""Обратное геокодирование: координаты → адрес (Nominatim/OSM)."""

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

_geolocator = Nominatim(user_agent="taxi_po_yuzhnomu_bot")


def reverse_geocode(lat: float, lon: float) -> str:
    """Возвращает адрес по координатам или строку 'lat, lon' при ошибке."""
    try:
        loc = _geolocator.reverse(f"{lat}, {lon}", language="ru", timeout=5)
        return (loc.address or "").strip() or f"{lat:.5f}, {lon:.5f}"
    except (GeocoderTimedOut, GeocoderServiceError, AttributeError, ValueError):
        return f"{lat:.5f}, {lon:.5f}"

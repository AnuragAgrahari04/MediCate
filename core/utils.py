"""Utility functions for core app."""
import logging
logger = logging.getLogger(__name__)


def geocode_address(address_string):
    """Return (lat, lon) tuple for given address string, or (None, None)."""
    if not address_string or address_string.strip() in ('', ', , , India', ',,,'):
        return None, None
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent='medicate_app_v1')
        location = geolocator.geocode(address_string, timeout=5)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        logger.warning(f'Geocoding failed for "{address_string}": {e}')
    return None, None


def find_nearby_doctors(patient_lat, patient_lon, specialization=None, limit=5):
    from accounts.models import DoctorProfile
    from geopy.distance import geodesic

    qs = DoctorProfile.objects.filter(is_verified=True)
    if specialization:
        qs = qs.filter(specialization__icontains=specialization)

    doctors = list(qs)

    if patient_lat and patient_lon:
        def dist_key(doc):
            if doc.latitude and doc.longitude:
                return geodesic((patient_lat, patient_lon), (doc.latitude, doc.longitude)).km
            return 99999

        for doc in doctors:
            doc.distance_km = dist_key(doc)
        doctors.sort(key=lambda d: d.distance_km)
    else:
        doctors.sort(key=lambda d: d.rating, reverse=True)
        for doc in doctors:
            doc.distance_km = None

    return doctors[:limit]


def generate_video_token(channel_name, uid, role='publisher'):
    from django.conf import settings
    app_id   = getattr(settings, 'AGORA_APP_ID', '')
    app_cert = getattr(settings, 'AGORA_APP_CERT', '')
    if not app_id or not app_cert:
        return ''
    try:
        from agora_token_builder import RtcTokenBuilder
        import time
        expiry = int(time.time()) + 3600
        token = RtcTokenBuilder.buildTokenWithUid(app_id, app_cert, channel_name, uid, 1, expiry)
        return token
    except Exception as e:
        logger.error(f'Agora token error: {e}')
        return ''


def ai_medical_response(question, disease_context=''):
    from django.conf import settings
    import requests
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        return 'AI assistant is not configured. Please add OPENROUTER_API_KEY to your .env file.'
    try:
        system = (
            'You are a helpful medical assistant in the Medicate app. '
            'Provide helpful, accurate medical information but always remind patients '
            'to consult a qualified doctor for diagnosis and treatment. '
            f'Current patient context: {disease_context or "general inquiry"}'
        )
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': 'google/gemini-flash-1.5',
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user',   'content': question},
                ],
                'max_tokens': 400,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f'AI API error: {e}')
        return 'AI assistant temporarily unavailable. Please try again later.'


# ── Specialization → OSM healthcare tag mapping ───────────────────
OSM_SPEC_MAP = {
    'cardiologist':       'cardiologist',
    'dermatologist':      'dermatologist',
    'neurologist':        'neurologist',
    'endocrinologist':    'endocrinologist',
    'gynecologist':       'gynaecologist',
    'ophthalmologist':    'ophthalmologist',
    'pediatrician':       'paediatrician',
    'psychiatrist':       'psychiatrist',
    'urologist':          'urologist',
    'orthopedic':         'orthopaedist',
    'pulmonologist':      'pulmonologist',
    'ent specialist':     'ear_nose_throat',
    'oncologist':         'oncologist',
    'nephrologist':       'nephrologist',
    'rheumatologist':     'rheumatologist',
    'general physician':  'general',
}

SPEC_TO_SEARCH = {
    'Cardiologist':       'cardiologist',
    'Gastroenterologist': 'gastroenterologist',
    'Neurologist':        'neurologist',
    'Endocrinologist':    'endocrinologist',
    'Pulmonologist':      'pulmonologist',
    'Orthopedic':         'orthopedic doctor',
    'Dermatologist':      'dermatologist',
    'Urologist':          'urologist',
    'Ophthalmologist':    'ophthalmologist',
    'ENT Specialist':     'ENT specialist',
    'Psychiatrist':       'psychiatrist',
    'Pediatrician':       'pediatrician',
    'Gynecologist':       'gynecologist',
    'Oncologist':         'oncologist',
    'Rheumatologist':     'rheumatologist',
    'Nephrologist':       'nephrologist',
    'Hematologist':       'hematologist',
    'Hepatologist':       'hepatologist',
    'Infectious Disease': 'infectious disease specialist',
    'General Physician':  'general physician doctor',
}


def fetch_real_doctors(lat, lon, specialization='', city='', radius_meters=20000):
    """
    Fetch real nearby doctors.
    Priority: Google Places (if key set) → Overpass OSM → Nominatim fallback.
    Always returns a list of dicts.
    """
    from django.conf import settings
    api_key = getattr(settings, 'GOOGLE_MAPS_KEY', '')

    if api_key:
        result = _fetch_google(lat, lon, specialization, city, radius_meters, api_key)
        if result:
            return result

    # No Google key or Google failed — use OSM
    return _fetch_osm_broadened(lat, lon, specialization, city, radius_meters)


def _fetch_google(lat, lon, specialization, city, radius_meters, api_key):
    import requests as req
    from geopy.distance import geodesic

    search_term = SPEC_TO_SEARCH.get(specialization, specialization or 'doctor')
    query = f'{search_term} near {city}' if city else f'{search_term} doctor'

    try:
        params = {'query': query, 'key': api_key, 'type': 'doctor'}
        if lat and lon:
            params['location'] = f'{lat},{lon}'
            params['radius'] = radius_meters

        resp = req.get(
            'https://maps.googleapis.com/maps/api/place/textsearch/json',
            params=params, timeout=8
        )
        data = resp.json()

        results = []
        for place in data.get('results', [])[:10]:
            plat = place['geometry']['location']['lat']
            plon = place['geometry']['location']['lng']
            dist = round(geodesic((lat, lon), (plat, plon)).km, 1) if lat and lon else None

            phone = ''
            try:
                d = req.get(
                    'https://maps.googleapis.com/maps/api/place/details/json',
                    params={'place_id': place['place_id'],
                            'fields': 'formatted_phone_number',
                            'key': api_key},
                    timeout=4
                ).json().get('result', {})
                phone = d.get('formatted_phone_number', '')
            except Exception:
                pass

            results.append({
                'name':          place.get('name', ''),
                'address':       place.get('formatted_address', ''),
                'rating':        place.get('rating', 0),
                'total_ratings': place.get('user_ratings_total', 0),
                'lat':           plat,
                'lon':           plon,
                'distance_km':   dist,
                'phone':         phone,
                'maps_url':      f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id','')}",
                'open_now':      place.get('opening_hours', {}).get('open_now', None),
                'source':        'google',
                'speciality':    specialization,
            })
        return results
    except Exception as e:
        logger.warning(f'Google Places failed: {e}')
        return []


def _fetch_osm_broadened(lat, lon, specialization='', city='', radius=20000):
    """
    Broadened OSM query — tries specialization-specific first,
    then falls back to ALL healthcare nodes if nothing found.
    Also queries ways and relations (not just nodes) for better coverage.
    """
    import requests as req
    from geopy.distance import geodesic

    if not lat or not lon:
        return _fetch_nominatim(specialization, city)

    spec_lower = specialization.lower() if specialization else ''
    osm_spec   = OSM_SPEC_MAP.get(spec_lower, '')

    def run_query(q):
        try:
            resp = req.post(
                'https://overpass-api.de/api/interpreter',
                data={'data': q},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json().get('elements', [])
        except Exception as e:
            logger.warning(f'Overpass query failed: {e}')
            return []

    # Query 1: specialization-specific (nodes + ways)
    if osm_spec:
        q1 = f'''
        [out:json][timeout:20];
        (
          node["healthcare:speciality"~"{osm_spec}",i](around:{radius},{lat},{lon});
          way["healthcare:speciality"~"{osm_spec}",i](around:{radius},{lat},{lon});
          node["amenity"="clinic"]["healthcare:speciality"~"{osm_spec}",i](around:{radius},{lat},{lon});
          node["amenity"="doctors"]["healthcare:speciality"~"{osm_spec}",i](around:{radius},{lat},{lon});
        );
        out center body 15;
        '''
        elements = run_query(q1)
        results = _elements_to_results(elements, lat, lon)
        if results:
            return results[:10]

    # Query 2: broad healthcare — hospitals, clinics, doctors
    q2 = f'''
    [out:json][timeout:20];
    (
      node["amenity"="hospital"](around:{radius},{lat},{lon});
      node["amenity"="clinic"](around:{radius},{lat},{lon});
      node["amenity"="doctors"](around:{radius},{lat},{lon});
      node["healthcare"="doctor"](around:{radius},{lat},{lon});
      node["healthcare"="clinic"](around:{radius},{lat},{lon});
      node["healthcare"="hospital"](around:{radius},{lat},{lon});
      way["amenity"="hospital"](around:{radius},{lat},{lon});
      way["amenity"="clinic"](around:{radius},{lat},{lon});
    );
    out center body 25;
    '''
    elements = run_query(q2)
    results = _elements_to_results(elements, lat, lon)

    if results:
        return results[:10]

    # Query 3: last resort — any named medical/health place
    q3 = f'''
    [out:json][timeout:20];
    (
      node["name"~"hospital|clinic|medical|health|doctor|care|nursing",i](around:{radius},{lat},{lon});
      node["name"~"अस्पताल|क्लिनिक|चिकित्सा|स्वास्थ्य",i](around:{radius},{lat},{lon});
    );
    out body 20;
    '''
    elements = run_query(q3)
    results = _elements_to_results(elements, lat, lon)
    return results[:10] if results else _fetch_nominatim(specialization, city)


def _elements_to_results(elements, lat, lon):
    """Convert raw Overpass elements to result dicts."""
    from geopy.distance import geodesic

    results = []
    seen = set()

    for el in elements:
        tags = el.get('tags', {})
        name = tags.get('name', '') or tags.get('operator', '') or tags.get('brand', '')
        if not name or name in seen:
            continue
        seen.add(name)

        # Handle both nodes (lat/lon) and ways (center)
        if el.get('type') == 'way':
            center = el.get('center', {})
            elat = center.get('lat', 0)
            elon = center.get('lon', 0)
        else:
            elat = el.get('lat', 0)
            elon = el.get('lon', 0)

        if not elat or not elon:
            continue

        dist = round(geodesic((lat, lon), (elat, elon)).km, 1)

        # Build address from OSM tags
        addr_parts = []
        if tags.get('addr:housenumber'):
            addr_parts.append(tags['addr:housenumber'])
        if tags.get('addr:street'):
            addr_parts.append(tags['addr:street'])
        if tags.get('addr:suburb'):
            addr_parts.append(tags['addr:suburb'])
        if tags.get('addr:city'):
            addr_parts.append(tags['addr:city'])
        elif tags.get('addr:state'):
            addr_parts.append(tags['addr:state'])
        address = ', '.join(addr_parts) if addr_parts else tags.get('addr:full', '')

        # Determine type label
        speciality = (
            tags.get('healthcare:speciality') or
            tags.get('amenity') or
            tags.get('healthcare') or
            'clinic'
        )

        results.append({
            'name':          name,
            'address':       address,
            'rating':        0,
            'total_ratings': 0,
            'lat':           elat,
            'lon':           elon,
            'distance_km':   dist,
            'phone':         tags.get('phone', '') or tags.get('contact:phone', '') or tags.get('contact:mobile', ''),
            'maps_url':      f"https://www.openstreetmap.org/{el.get('type','node')}/{el.get('id','')}",
            'open_now':      None,
            'source':        'osm',
            'speciality':    speciality,
        })

    # Sort by distance
    results.sort(key=lambda x: x['distance_km'])
    return results


def _fetch_nominatim(specialization='', city=''):
    """Last resort: text search via Nominatim when no coordinates available."""
    import requests as req
    if not city:
        return []
    try:
        search = f'{specialization} hospital clinic {city}' if specialization else f'hospital clinic {city}'
        resp = req.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': search,
                'format': 'json',
                'limit': 8,
                'addressdetails': 1,
                'countrycodes': 'in',
            },
            headers={'User-Agent': 'Medicate/1.0'},
            timeout=8,
        )
        results = []
        seen = set()
        for r in resp.json():
            name = r.get('display_name', '').split(',')[0].strip()
            if not name or name in seen:
                continue
            seen.add(name)
            results.append({
                'name':          name,
                'address':       r.get('display_name', ''),
                'rating':        0,
                'total_ratings': 0,
                'lat':           float(r.get('lat', 0)),
                'lon':           float(r.get('lon', 0)),
                'distance_km':   None,
                'phone':         '',
                'maps_url':      f"https://www.openstreetmap.org/{r.get('osm_type','node')}/{r.get('osm_id','')}",
                'open_now':      None,
                'source':        'osm',
                'speciality':    specialization or 'clinic',
            })
        return results
    except Exception as e:
        logger.warning(f'Nominatim fallback failed: {e}')
        return []
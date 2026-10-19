import contextlib
import fcntl
import hmac
import io
import json
import os
import secrets
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import (Flask, request, jsonify, render_template, redirect, abort,
                   send_from_directory, Response, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeTimedSerializer, BadSignature
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import drive
import imaging
import weather

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Railway terminates HTTPS

BASE_DIR     = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
THUMB_FOLDER  = os.path.join(DATA_DIR, 'thumbs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)


@contextlib.contextmanager
def startup_lock():
    """Gunicorn starts two workers at once; let one finish database setup before the other looks."""
    with open(os.path.join(DATA_DIR, '.startup.lock'), 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _secret_key():
    """SECRET_KEY if set, otherwise one generated once and kept on the data volume."""
    if os.environ.get('SECRET_KEY'):
        return os.environ['SECRET_KEY']
    path = os.path.join(DATA_DIR, 'secret_key')
    if not os.path.exists(path):
        # Both gunicorn workers start at once: write to a temp file and link it into place,
        # so exactly one key wins and both workers read the same one.
        tmp = f'{path}.{os.getpid()}'
        with open(tmp, 'w') as f:
            f.write(secrets.token_hex(32))
        try:
            os.link(tmp, path)
        except FileExistsError:
            pass
        os.remove(tmp)
    with open(path) as f:
        return f.read().strip()


PASSCODE = os.environ.get('FOLIO_PASSCODE', '')
app.secret_key = _secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=bool(os.environ.get('RAILWAY_ENVIRONMENT')),
                  PERMANENT_SESSION_LIFETIME=timedelta(days=365))

app.config['SQLALCHEMY_DATABASE_URI']      = f"sqlite:///{os.path.join(DATA_DIR, 'journal.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER']               = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH']          = 100 * 1024 * 1024  # 100 MB

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'm4v', 'webm'}
ALLOWED_GPX_EXTENSIONS   = {'gpx'}

db = SQLAlchemy(app)

# Cache-buster for the stylesheet, so browsers pick up a new one after each deploy
app.jinja_env.globals['asset_v'] = str(int(os.path.getmtime(os.path.join(BASE_DIR, 'static', 'style.css'))))


# ── Models ────────────────────────────────────────────────────────────────────

class Entry(db.Model):
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text,        nullable=True)
    event      = db.Column(db.String(200), nullable=True)
    place      = db.Column(db.String(200), nullable=True)
    lat        = db.Column(db.Float,       nullable=True)
    lng        = db.Column(db.Float,       nullable=True)
    entry_date = db.Column(db.Date,        nullable=False, default=datetime.utcnow().date)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)
    share_token = db.Column(db.String(40), nullable=True, unique=True)
    weather    = db.Column(db.Text,        nullable=True)    # JSON from weather.lookup, '{}' if none
    photos     = db.relationship('Photo', backref='entry', lazy=True, cascade='all, delete-orphan')
    tracks     = db.relationship('Track', backref='entry', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':         self.id,
            'title':      self.title,
            'body':       self.body,
            'event':      self.event,
            'place':      self.place,
            'lat':        self.lat,
            'lng':        self.lng,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'created_at': self.created_at.isoformat(),
            'weather':    json.loads(self.weather) if self.weather else None,
            'shared':     bool(self.share_token),
            'photos':     [p.to_dict() for p in sorted(self.photos, key=lambda p: p.taken_at or p.uploaded_at or datetime.min)],
            'tracks':     [t.to_dict() for t in self.tracks],
        }


class Photo(db.Model):
    """A photo or video. Stored in UPLOAD_FOLDER, or in Google Drive when drive_id is set."""
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id      = db.Column(db.String(36), db.ForeignKey('entry.id'), nullable=False)
    filename      = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300), nullable=True)
    uploaded_at   = db.Column(db.DateTime,   default=datetime.utcnow)
    drive_id      = db.Column(db.String(100), nullable=True)
    mime_type     = db.Column(db.String(100), nullable=True)
    taken_at      = db.Column(db.DateTime,   nullable=True)    # from the photo's own details
    lat           = db.Column(db.Float,      nullable=True)
    lng           = db.Column(db.Float,      nullable=True)

    @property
    def kind(self):
        if self.mime_type:
            return 'video' if self.mime_type.startswith('video/') else 'image'
        ext = self.filename.rsplit('.', 1)[-1].lower()
        return 'video' if ext in ALLOWED_VIDEO_EXTENSIONS else 'image'

    def to_dict(self):
        return {'id': self.id, 'filename': self.filename, 'original_name': self.original_name,
                'kind': self.kind, 'url': f'/media/{self.id}', 'thumb_url': f'/media/{self.id}/thumb',
                'taken_at': self.taken_at.isoformat() if self.taken_at else None,
                'lat': self.lat, 'lng': self.lng}


class Setting(db.Model):
    key   = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)


def get_setting(key):
    row = db.session.get(Setting, key)
    return row.value if row else None


def set_setting(key, value):
    row = db.session.get(Setting, key) or Setting(key=key)
    row.value = value
    db.session.add(row)
    db.session.commit()


class Track(db.Model):
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id      = db.Column(db.String(36), db.ForeignKey('entry.id'), nullable=False)
    filename      = db.Column(db.String(300), nullable=False)   # stored .gpx file
    original_name = db.Column(db.String(300), nullable=True)
    track_name    = db.Column(db.String(300), nullable=True)    # name from GPX <name> tag
    distance_km   = db.Column(db.Float,       nullable=True)
    points        = db.Column(db.Text,        nullable=True)    # JSON-encoded [[lat,lng],…] (decimated)
    bbox          = db.Column(db.String(200), nullable=True)    # "minLat,minLng,maxLat,maxLng"
    elevations    = db.Column(db.Text,        nullable=True)    # JSON metres, aligned with points; '[]' if none
    ascent_m      = db.Column(db.Float,       nullable=True)
    uploaded_at   = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        pts = json.loads(self.points) if self.points else []
        return {
            'id':            self.id,
            'original_name': self.original_name,
            'track_name':    self.track_name,
            'distance_km':   self.distance_km,
            'points':        pts,
            'bbox':          self.bbox,
            'elevations':    json.loads(self.elevations) if self.elevations else [],
            'ascent_m':      self.ascent_m,
            'gpx_url':       f'/uploads/{self.filename}',
        }


with startup_lock(), app.app_context():
    db.create_all()
    # migrate: add lat/lng/tracks if upgrading
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    new_columns = {
        'entry': {'lat': 'FLOAT', 'lng': 'FLOAT', 'share_token': 'VARCHAR(40)', 'weather': 'TEXT'},
        'photo': {'drive_id': 'VARCHAR(100)', 'mime_type': 'VARCHAR(100)', 'taken_at': 'DATETIME',
                  'lat': 'FLOAT', 'lng': 'FLOAT'},
        'track': {'elevations': 'TEXT', 'ascent_m': 'FLOAT'},
    }
    with db.engine.connect() as conn:
        for table, cols in new_columns.items():
            have = {c['name'] for c in inspector.get_columns(table)}
            for col, typ in cols.items():
                if col not in have:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {typ}'))
                    conn.commit()


# ── GPX helpers ───────────────────────────────────────────────────────────────

GPX_NS = {
    'gpx':  'http://www.topografix.com/GPX/1/1',
    'gpx10':'http://www.topografix.com/GPX/1/0',
}

def _pts_from_gpx(path):
    """Return list of (lat, lng, ele) from a GPX file; ele is None when missing."""
    tree = ET.parse(path)
    root = tree.getroot()
    tag  = root.tag  # e.g. {http://...}gpx
    ns   = tag[1:tag.index('}')] if tag.startswith('{') else ''
    pre  = f'{{{ns}}}' if ns else ''

    def point(el):
        ele = el.find(f'{pre}ele')
        try:
            e = float(ele.text) if ele is not None and ele.text else None
        except ValueError:
            e = None
        return (float(el.attrib['lat']), float(el.attrib['lon']), e)

    pts = []
    for trkpt in root.iter(f'{pre}trkpt'):
        try:
            pts.append(point(trkpt))
        except (KeyError, ValueError):
            pass
    # also try wpt / rtept
    if not pts:
        for tag_name in (f'{pre}wpt', f'{pre}rtept'):
            for pt in root.iter(tag_name):
                try:
                    pts.append(point(pt))
                except (KeyError, ValueError):
                    pass
    return pts


def _ascent_m(eles, threshold=4.0):
    """Total climb, ignoring wiggles smaller than `threshold` metres (GPS altitude is noisy)."""
    total, base = 0.0, None
    for e in eles:
        if base is None or e < base:
            base = e
        elif e - base >= threshold:
            total += e - base
            base = e
    return round(total)


def _gpx_name(path):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        tag  = root.tag
        ns   = tag[1:tag.index('}')] if tag.startswith('{') else ''
        pre  = f'{{{ns}}}' if ns else ''
        el   = root.find(f'.//{pre}name')
        return el.text.strip() if el is not None and el.text else None
    except Exception:
        return None


def _decimate(pts, max_pts=800):
    """Simple nth-point decimation to keep stored JSON small."""
    if len(pts) <= max_pts:
        return pts
    step = len(pts) / max_pts
    return [pts[int(i * step)] for i in range(max_pts)]


def _haversine_km(pts):
    import math
    total = 0.0
    for i in range(1, len(pts)):
        lat1, lon1 = math.radians(pts[i-1][0]), math.radians(pts[i-1][1])
        lat2, lon2 = math.radians(pts[i][0]),   math.radians(pts[i][1])
        dlat, dlon = lat2-lat1, lon2-lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        total += 6371 * 2 * math.asin(min(1, a**.5))
    return round(total, 2)


def parse_gpx(path):
    """Returns (points, distance_km, bbox, name, elevations, ascent_m)."""
    full = _pts_from_gpx(path)
    if not full:
        return None, None, None, None, [], None
    pts      = [(p[0], p[1]) for p in full]
    dist     = _haversine_km(pts)
    decimated = _decimate(full)
    lats     = [p[0] for p in pts]
    lngs     = [p[1] for p in pts]
    bbox     = f"{min(lats)},{min(lngs)},{max(lats)},{max(lngs)}"
    name     = _gpx_name(path)
    has_ele  = all(p[2] is not None for p in full)
    eles     = [round(p[2], 1) for p in decimated] if has_ele else []
    ascent   = _ascent_m([p[2] for p in full]) if has_ele else None
    return [(p[0], p[1]) for p in decimated], dist, bbox, name, eles, ascent


# ── Routes ────────────────────────────────────────────────────────────────────

# ── Passcode lock ─────────────────────────────────────────────────────────────

PUBLIC_PATHS = ('/login', '/s/', '/manifest.webmanifest', '/sw.js', '/static/icons/', '/static/style.css')


@app.before_request
def require_passcode():
    if not PASSCODE or session.get('ok') or request.path.startswith(PUBLIC_PATHS):
        return
    if request.path == '/':
        return redirect(url_for('login'))
    return jsonify({'error': 'locked'}), 401


@app.route('/login', methods=['GET', 'POST'])
def login():
    if not PASSCODE or session.get('ok'):
        return redirect('/')
    error = None
    if request.method == 'POST':
        if hmac.compare_digest(request.form.get('passcode', '').encode(), PASSCODE.encode()):
            session.permanent = True
            session['ok'] = True
            return redirect('/')
        time.sleep(1)   # slow down guessing
        error = 'Wrong passcode'
    return render_template('login.html', error=error)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    return render_template('index.html', locked=bool(PASSCODE))


# ── Phone app install ─────────────────────────────────────────────────────────

@app.route('/manifest.webmanifest')
def manifest():
    return jsonify({
        'name': 'Folio', 'short_name': 'Folio', 'start_url': '/', 'scope': '/',
        'display': 'standalone', 'background_color': '#000000', 'theme_color': '#000000',
        'icons': [
            {'src': '/static/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/static/icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
            {'src': '/static/icons/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }), 200, {'Content-Type': 'application/manifest+json'}


@app.route('/sw.js')
def service_worker():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'sw.js', mimetype='text/javascript',
                               max_age=0)


# ── Private share links ───────────────────────────────────────────────────────

@app.route('/api/entries/<entry_id>/share', methods=['POST', 'DELETE'])
def share_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    if request.method == 'DELETE':
        entry.share_token = None
        db.session.commit()
        return jsonify({'shared': False})
    if not entry.share_token:
        entry.share_token = secrets.token_urlsafe(16)
        db.session.commit()
    return jsonify({'shared': True, 'url': f'{request.host_url}s/{entry.share_token}'})


def _shared_entry(token):
    return Entry.query.filter_by(share_token=token).first_or_404() if token else abort(404)


@app.route('/s/<token>')
def shared_page(token):
    entry = _shared_entry(token)
    data = entry.to_dict()
    for p in data['photos']:
        p['url'] = f"/s/{token}/media/{p['id']}"
        p['thumb_url'] = f"/s/{token}/media/{p['id']}/thumb"
    return render_template('share.html', e=data)


@app.route('/s/<token>/media/<photo_id>')
@app.route('/s/<token>/media/<photo_id>/<variant>')
def shared_media(token, photo_id, variant=None):
    entry = _shared_entry(token)
    photo = Photo.query.filter_by(id=photo_id, entry_id=entry.id).first_or_404()
    return serve_thumb(photo) if variant == 'thumb' else serve_media(photo)


@app.route('/api/entries', methods=['GET'])
def get_entries():
    sort_by      = request.args.get('sort', 'date')
    event_filter = request.args.get('event', '').strip()
    place_filter = request.args.get('place', '').strip()
    search       = request.args.get('search', '').strip()

    q = Entry.query
    if event_filter: q = q.filter(Entry.event.ilike(f'%{event_filter}%'))
    if place_filter:  q = q.filter(Entry.place.ilike(f'%{place_filter}%'))
    if search:
        q = q.filter(db.or_(
            Entry.title.ilike(f'%{search}%'), Entry.body.ilike(f'%{search}%'),
            Entry.event.ilike(f'%{search}%'), Entry.place.ilike(f'%{search}%'),
        ))
    if sort_by == 'event':  q = q.order_by(Entry.event.asc(),  Entry.entry_date.desc())
    elif sort_by == 'place': q = q.order_by(Entry.place.asc(), Entry.entry_date.desc())
    else:                    q = q.order_by(Entry.entry_date.desc())
    return jsonify([e.to_dict() for e in q.all()])


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
    entry_date = (datetime.strptime(data['entry_date'], '%Y-%m-%d').date()
                  if data.get('entry_date') else datetime.utcnow().date())
    entry = Entry(title=data['title'], body=data.get('body',''), event=data.get('event',''),
                  place=data.get('place',''), lat=data.get('lat'), lng=data.get('lng'),
                  entry_date=entry_date)
    refresh_weather(entry)
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


@app.route('/api/entries/<entry_id>', methods=['GET'])
def get_entry(entry_id):
    return jsonify(Entry.query.get_or_404(entry_id).to_dict())


@app.route('/api/entries/<entry_id>', methods=['PUT'])
def update_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    data  = request.get_json()
    before = (entry.lat, entry.lng, entry.entry_date)
    for f in ('title','body','event','place','lat','lng'):
        if f in data: setattr(entry, f, data[f])
    if 'entry_date' in data:
        entry.entry_date = datetime.strptime(data['entry_date'], '%Y-%m-%d').date()
    if (entry.lat, entry.lng, entry.entry_date) != before:
        refresh_weather(entry)
    db.session.commit()
    return jsonify(entry.to_dict())


def refresh_weather(entry):
    w = weather.lookup(entry.lat, entry.lng, entry.entry_date)
    entry.weather = json.dumps(w or {})


@app.route('/api/entries/<entry_id>/weather', methods=['POST'])
def fetch_weather(entry_id):
    """Fill in weather for older entries the first time they're viewed."""
    entry = Entry.query.get_or_404(entry_id)
    if entry.weather is None:
        refresh_weather(entry)
        db.session.commit()
    return jsonify(json.loads(entry.weather or '{}'))


@app.route('/api/entries/<entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    for photo in entry.photos:
        remove_media(photo)
    for track in entry.tracks:
        p = os.path.join(app.config['UPLOAD_FOLDER'], track.filename)
        if os.path.exists(p): os.remove(p)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'deleted': True})


@app.route('/api/entries/<entry_id>/photos', methods=['POST'])
def upload_photos(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    saved = []
    for file in request.files.getlist('photos'):
        if file and '.' in file.filename and file.filename.rsplit('.',1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS:
            ext  = file.filename.rsplit('.',1)[1].lower()
            name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
            p = Photo(id=str(uuid.uuid4()), entry_id=entry.id, filename=name,
                      original_name=secure_filename(file.filename))
            if p.kind == 'image':
                try:
                    p.taken_at, p.lat, p.lng = imaging.make_thumb(
                        os.path.join(app.config['UPLOAD_FOLDER'], name), thumb_path(p))
                except Exception as e:
                    app.logger.warning('No preview for %s: %s', name, e)
            db.session.add(p); saved.append(p)
    pin_from_photos(entry, saved)
    db.session.commit()
    return jsonify([p.to_dict() for p in saved]), 201


def pin_from_photos(entry, photos):
    """Pin an unpinned entry where its first geotagged photo was taken."""
    if entry.lat or entry.lng:
        return
    for p in photos:
        if p.lat is not None:
            entry.lat, entry.lng = p.lat, p.lng
            refresh_weather(entry)
            return


@app.route('/api/photos/<photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    remove_media(photo)
    db.session.delete(photo)
    db.session.commit()
    return jsonify({'deleted': True})


# ── Media (local files and Google Drive) ──────────────────────────────────────

MEDIA_CHUNK = 8 * 1024 * 1024  # cap open-ended range requests so video seeks stay quick


def drive_token():
    return get_setting('drive_refresh_token')


def thumb_path(photo):
    return os.path.join(THUMB_FOLDER, f'{photo.id}.jpg')


def remove_media(photo):
    if os.path.exists(thumb_path(photo)):
        os.remove(thumb_path(photo))
    if photo.drive_id:
        try:
            drive.trash(drive_token(), photo.drive_id)
        except drive.DriveError as e:
            app.logger.warning('Could not trash Drive file %s: %s', photo.drive_id, e)
        return
    p = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
    if os.path.exists(p): os.remove(p)


@app.route('/uploads/<path:filename>')
@app.route('/static/uploads/<path:filename>')  # URLs saved before media moved to DATA_DIR
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, max_age=31536000)


@app.route('/media/<photo_id>')
def media(photo_id):
    return serve_media(Photo.query.get_or_404(photo_id))


@app.route('/media/<photo_id>/thumb')
def media_thumb(photo_id):
    return serve_thumb(Photo.query.get_or_404(photo_id))


def serve_thumb(photo):
    """Small preview for grids and map pins; made on first request for older photos."""
    path = thumb_path(photo)
    if not os.path.exists(path) and photo.kind == 'image':
        try:
            if photo.drive_id:
                r = drive.open_media(drive_token(), photo.drive_id)
                src = io.BytesIO(r.content); r.close()
            else:
                src = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
            taken_at, lat, lng = imaging.make_thumb(src, path)
            if photo.taken_at is None and (taken_at or lat is not None):
                photo.taken_at, photo.lat, photo.lng = taken_at, lat, lng
                db.session.commit()
        except Exception as e:
            app.logger.warning('No preview for photo %s: %s', photo.id, e)
    if not os.path.exists(path):
        return serve_media(photo)
    return send_from_directory(THUMB_FOLDER, os.path.basename(path), max_age=31536000)


def serve_media(photo):
    if not photo.drive_id:
        return send_from_directory(app.config['UPLOAD_FOLDER'], photo.filename, max_age=31536000)

    rng = request.headers.get('Range')
    if rng and rng.startswith('bytes=') and rng.endswith('-'):
        start = int(rng[6:-1] or 0)
        rng = f'bytes={start}-{start + MEDIA_CHUNK - 1}'
    try:
        upstream = drive.open_media(drive_token(), photo.drive_id, rng)
    except drive.DriveError as e:
        app.logger.warning('%s', e)
        abort(502)

    headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'private, max-age=31536000, immutable'}
    for h in ('Content-Length', 'Content-Range'):
        if h in upstream.headers:
            headers[h] = upstream.headers[h]

    def body():
        try:
            yield from upstream.iter_content(256 * 1024)
        finally:
            upstream.close()

    return Response(body(), status=upstream.status_code, headers=headers,
                    mimetype=photo.mime_type or upstream.headers.get('Content-Type'))


@app.route('/api/drive/status')
def drive_status():
    return jsonify({'configured': drive.configured(), 'connected': bool(drive_token())})


def _state_signer():
    return URLSafeTimedSerializer(os.environ.get('DRIVE_SETUP_KEY', ''), salt='drive-connect')


@app.route('/drive/connect')
def drive_connect():
    # Only the owner, holding DRIVE_SETUP_KEY, may point Folio at a Drive account.
    key = os.environ.get('DRIVE_SETUP_KEY')
    if not drive.configured() or not key:
        return 'Google Drive is not configured on the server.', 503
    if request.args.get('key') != key:
        abort(403)
    return redirect(drive.auth_url(f'{request.host_url}drive/callback', _state_signer().dumps('connect')))


@app.route('/drive/callback')
def drive_callback():
    try:
        _state_signer().loads(request.args.get('state', ''), max_age=900)
    except BadSignature:
        abort(403)
    if 'error' in request.args:
        return f"Google said: {request.args['error']}", 400
    try:
        refresh = drive.exchange_code(request.args.get('code', ''), f'{request.host_url}drive/callback')
        set_setting('drive_refresh_token', refresh)
        if not get_setting('drive_folder_id'):
            set_setting('drive_folder_id', drive.create_folder(refresh))
    except drive.DriveError as e:
        return f'Could not connect Google Drive: {e}', 400
    return redirect('/?drive=connected')


@app.route('/api/entries/<entry_id>/media/start', methods=['POST'])
def start_media_upload(entry_id):
    Entry.query.get_or_404(entry_id)
    if not drive_token():
        return jsonify({'error': 'Google Drive is not connected'}), 409
    data = request.get_json() or {}
    mime = data.get('mime') or ''
    if not (mime.startswith('image/') or mime.startswith('video/')):
        return jsonify({'error': 'Only photos and videos can be uploaded'}), 400
    try:
        url = drive.start_upload(drive_token(), get_setting('drive_folder_id'),
                                 secure_filename(data.get('name') or 'upload') or 'upload',
                                 mime, int(data.get('size') or 0), request.headers.get('Origin'))
    except drive.DriveError as e:
        return jsonify({'error': str(e)}), 502
    return jsonify({'upload_url': url})


@app.route('/api/entries/<entry_id>/media/finish', methods=['POST'])
def finish_media_upload(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    data  = request.get_json() or {}
    try:
        meta = drive.get_meta(drive_token(), data.get('drive_id', ''))
    except drive.DriveError as e:
        return jsonify({'error': str(e)}), 400
    if get_setting('drive_folder_id') not in meta.get('parents', []):
        return jsonify({'error': 'File is not in the Folio folder'}), 400
    if Photo.query.filter_by(drive_id=meta['id']).first():
        return jsonify({'error': 'Already added'}), 409
    p = Photo(entry_id=entry.id, filename=meta['name'], original_name=meta['name'],
              drive_id=meta['id'], mime_type=meta.get('mimeType'))
    if p.kind == 'image':
        try:
            r = drive.open_media(drive_token(), p.drive_id, 'bytes=0-262143')
            p.taken_at, p.lat, p.lng = imaging.exif_from_bytes(r.content); r.close()
        except drive.DriveError:
            pass
    db.session.add(p)
    pin_from_photos(entry, [p])
    db.session.commit()
    return jsonify(p.to_dict()), 201


@app.route('/api/entries/<entry_id>/tracks', methods=['POST'])
def upload_track(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    file  = request.files.get('gpx')
    if not file or not file.filename.lower().endswith('.gpx'):
        return jsonify({'error': 'GPX file required'}), 400

    name = f"{uuid.uuid4().hex}.gpx"
    path = os.path.join(app.config['UPLOAD_FOLDER'], name)
    file.save(path)

    try:
        pts, dist, bbox, track_name, eles, ascent = parse_gpx(path)
    except Exception:
        os.remove(path)
        return jsonify({'error': 'Could not parse GPX file'}), 400

    if not pts:
        os.remove(path)
        return jsonify({'error': 'No track points found in GPX'}), 400

    track = Track(
        entry_id=entry.id, filename=name,
        original_name=secure_filename(file.filename),
        track_name=track_name, distance_km=dist,
        points=json.dumps(pts), bbox=bbox,
        elevations=json.dumps(eles), ascent_m=ascent,
    )
    # Auto-set entry pin to track start if not already set
    if not entry.lat and pts:
        entry.lat, entry.lng = pts[0][0], pts[0][1]
        refresh_weather(entry)

    db.session.add(track)
    db.session.commit()
    return jsonify(track.to_dict()), 201


@app.route('/api/tracks/<track_id>', methods=['DELETE'])
def delete_track(track_id):
    track = Track.query.get_or_404(track_id)
    p = os.path.join(app.config['UPLOAD_FOLDER'], track.filename)
    if os.path.exists(p): os.remove(p)
    db.session.delete(track)
    db.session.commit()
    return jsonify({'deleted': True})


@app.route('/api/meta/events')
def get_events():
    rows = db.session.query(Entry.event).filter(Entry.event != '').distinct().order_by(Entry.event).all()
    return jsonify([r[0] for r in rows if r[0]])

@app.route('/api/meta/places')
def get_places():
    rows = db.session.query(Entry.place).filter(Entry.place != '').distinct().order_by(Entry.place).all()
    return jsonify([r[0] for r in rows if r[0]])


with startup_lock(), app.app_context():
    for t in Track.query.filter(Track.elevations.is_(None)).all():
        path = os.path.join(UPLOAD_FOLDER, t.filename)
        try:
            pts, _, _, _, eles, ascent = parse_gpx(path) if os.path.exists(path) else (None,) * 4 + ([], None)
            if pts:
                t.points = json.dumps(pts)   # re-decimated the same way, so it lines up with eles
        except Exception:
            eles, ascent = [], None
        t.elevations, t.ascent_m = json.dumps(eles), ascent
    db.session.commit()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

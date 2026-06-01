import os
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR     = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI']      = f"sqlite:///{os.path.join(BASE_DIR, 'journal.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER']               = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH']          = 100 * 1024 * 1024  # 100 MB

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_GPX_EXTENSIONS   = {'gpx'}

db = SQLAlchemy(app)


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
            'photos':     [p.to_dict() for p in self.photos],
            'tracks':     [t.to_dict() for t in self.tracks],
        }


class Photo(db.Model):
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id      = db.Column(db.String(36), db.ForeignKey('entry.id'), nullable=False)
    filename      = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300), nullable=True)
    uploaded_at   = db.Column(db.DateTime,   default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'filename': self.filename,
                'original_name': self.original_name, 'url': f'/static/uploads/{self.filename}'}


class Track(db.Model):
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id      = db.Column(db.String(36), db.ForeignKey('entry.id'), nullable=False)
    filename      = db.Column(db.String(300), nullable=False)   # stored .gpx file
    original_name = db.Column(db.String(300), nullable=True)
    track_name    = db.Column(db.String(300), nullable=True)    # name from GPX <name> tag
    distance_km   = db.Column(db.Float,       nullable=True)
    points        = db.Column(db.Text,        nullable=True)    # JSON-encoded [[lat,lng],…] (decimated)
    bbox          = db.Column(db.String(200), nullable=True)    # "minLat,minLng,maxLat,maxLng"
    uploaded_at   = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        import json
        pts = json.loads(self.points) if self.points else []
        return {
            'id':            self.id,
            'original_name': self.original_name,
            'track_name':    self.track_name,
            'distance_km':   self.distance_km,
            'points':        pts,
            'bbox':          self.bbox,
            'gpx_url':       f'/static/uploads/{self.filename}',
        }


with app.app_context():
    db.create_all()
    # migrate: add lat/lng/tracks if upgrading
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    ecols = [c['name'] for c in inspector.get_columns('entry')]
    with db.engine.connect() as conn:
        for col in ('lat', 'lng'):
            if col not in ecols:
                conn.execute(text(f'ALTER TABLE entry ADD COLUMN {col} FLOAT'))
                conn.commit()


# ── GPX helpers ───────────────────────────────────────────────────────────────

GPX_NS = {
    'gpx':  'http://www.topografix.com/GPX/1/1',
    'gpx10':'http://www.topografix.com/GPX/1/0',
}

def _pts_from_gpx(path):
    """Return list of (lat, lng) from a GPX file. Tries 1.1 then 1.0 namespace."""
    tree = ET.parse(path)
    root = tree.getroot()
    tag  = root.tag  # e.g. {http://...}gpx
    ns   = tag[1:tag.index('}')] if tag.startswith('{') else ''
    pre  = f'{{{ns}}}' if ns else ''

    pts = []
    for trkpt in root.iter(f'{pre}trkpt'):
        try:
            pts.append((float(trkpt.attrib['lat']), float(trkpt.attrib['lon'])))
        except (KeyError, ValueError):
            pass
    # also try wpt / rtept
    if not pts:
        for tag_name in (f'{pre}wpt', f'{pre}rtept'):
            for pt in root.iter(tag_name):
                try:
                    pts.append((float(pt.attrib['lat']), float(pt.attrib['lon'])))
                except (KeyError, ValueError):
                    pass
    return pts


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
    pts = _pts_from_gpx(path)
    if not pts:
        return None, None, None, None
    dist     = _haversine_km(pts)
    decimated = _decimate(pts)
    lats     = [p[0] for p in pts]
    lngs     = [p[1] for p in pts]
    bbox     = f"{min(lats)},{min(lngs)},{max(lats)},{max(lngs)}"
    name     = _gpx_name(path)
    return decimated, dist, bbox, name


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


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
    for f in ('title','body','event','place','lat','lng'):
        if f in data: setattr(entry, f, data[f])
    if 'entry_date' in data:
        entry.entry_date = datetime.strptime(data['entry_date'], '%Y-%m-%d').date()
    db.session.commit()
    return jsonify(entry.to_dict())


@app.route('/api/entries/<entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    for photo in entry.photos:
        p = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
        if os.path.exists(p): os.remove(p)
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
        if file and '.' in file.filename and file.filename.rsplit('.',1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS:
            ext  = file.filename.rsplit('.',1)[1].lower()
            name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
            p = Photo(entry_id=entry.id, filename=name, original_name=secure_filename(file.filename))
            db.session.add(p); saved.append(p)
    db.session.commit()
    return jsonify([p.to_dict() for p in saved]), 201


@app.route('/api/photos/<photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    p = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
    if os.path.exists(p): os.remove(p)
    db.session.delete(photo)
    db.session.commit()
    return jsonify({'deleted': True})


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
        pts, dist, bbox, track_name = parse_gpx(path)
    except Exception:
        os.remove(path)
        return jsonify({'error': 'Could not parse GPX file'}), 400

    if not pts:
        os.remove(path)
        return jsonify({'error': 'No track points found in GPX'}), 400

    import json
    track = Track(
        entry_id=entry.id, filename=name,
        original_name=secure_filename(file.filename),
        track_name=track_name, distance_km=dist,
        points=json.dumps(pts), bbox=bbox,
    )
    # Auto-set entry pin to track start if not already set
    if not entry.lat and pts:
        entry.lat, entry.lng = pts[0][0], pts[0][1]

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

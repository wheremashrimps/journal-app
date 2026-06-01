import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'journal.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)


# ── Models ───────────────────────────────────────────────────────────────────

class Entry(db.Model):
    id          = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title       = db.Column(db.String(200), nullable=False)
    body        = db.Column(db.Text, nullable=True)
    event       = db.Column(db.String(200), nullable=True)
    place       = db.Column(db.String(200), nullable=True)
    lat         = db.Column(db.Float, nullable=True)
    lng         = db.Column(db.Float, nullable=True)
    entry_date  = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    photos      = db.relationship('Photo', backref='entry', lazy=True, cascade='all, delete-orphan')

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
        }


class Photo(db.Model):
    id            = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_id      = db.Column(db.String(36), db.ForeignKey('entry.id'), nullable=False)
    filename      = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300), nullable=True)
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':            self.id,
            'filename':      self.filename,
            'original_name': self.original_name,
            'url':           f'/static/uploads/{self.filename}',
        }


with app.app_context():
    db.create_all()
    # Add lat/lng columns if upgrading from old schema
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('entry')]
    with db.engine.connect() as conn:
        if 'lat' not in cols:
            conn.execute(text('ALTER TABLE entry ADD COLUMN lat FLOAT'))
            conn.commit()
        if 'lng' not in cols:
            conn.execute(text('ALTER TABLE entry ADD COLUMN lng FLOAT'))
            conn.commit()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


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
    if event_filter:
        q = q.filter(Entry.event.ilike(f'%{event_filter}%'))
    if place_filter:
        q = q.filter(Entry.place.ilike(f'%{place_filter}%'))
    if search:
        q = q.filter(db.or_(
            Entry.title.ilike(f'%{search}%'),
            Entry.body.ilike(f'%{search}%'),
            Entry.event.ilike(f'%{search}%'),
            Entry.place.ilike(f'%{place_filter}%'),
        ))

    if sort_by == 'event':
        q = q.order_by(Entry.event.asc(), Entry.entry_date.desc())
    elif sort_by == 'place':
        q = q.order_by(Entry.place.asc(), Entry.entry_date.desc())
    else:
        q = q.order_by(Entry.entry_date.desc())

    return jsonify([e.to_dict() for e in q.all()])


@app.route('/api/entries/mapped', methods=['GET'])
def get_mapped_entries():
    """Return only entries that have coordinates."""
    entries = Entry.query.filter(Entry.lat.isnot(None), Entry.lng.isnot(None)).all()
    return jsonify([e.to_dict() for e in entries])


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.get_json()
    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    entry_date = (datetime.strptime(data['entry_date'], '%Y-%m-%d').date()
                  if data.get('entry_date') else datetime.utcnow().date())

    entry = Entry(
        title      = data['title'],
        body       = data.get('body', ''),
        event      = data.get('event', ''),
        place      = data.get('place', ''),
        lat        = data.get('lat'),
        lng        = data.get('lng'),
        entry_date = entry_date,
    )
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
    for field in ('title', 'body', 'event', 'place', 'lat', 'lng'):
        if field in data:
            setattr(entry, field, data[field])
    if 'entry_date' in data:
        entry.entry_date = datetime.strptime(data['entry_date'], '%Y-%m-%d').date()
    db.session.commit()
    return jsonify(entry.to_dict())


@app.route('/api/entries/<entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    for photo in entry.photos:
        path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'deleted': True})


@app.route('/api/entries/<entry_id>/photos', methods=['POST'])
def upload_photos(entry_id):
    entry  = Entry.query.get_or_404(entry_id)
    files  = request.files.getlist('photos')
    saved  = []
    for file in files:
        if file and allowed_file(file.filename):
            ext         = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
            photo = Photo(entry_id=entry.id, filename=unique_name,
                          original_name=secure_filename(file.filename))
            db.session.add(photo)
            saved.append(photo)
    db.session.commit()
    return jsonify([p.to_dict() for p in saved]), 201


@app.route('/api/photos/<photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    path  = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(photo)
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

"""Google Drive storage for photos and videos.

Folio keeps one refresh token (from a one-time OAuth consent) and stores media in a
"Folio" folder in the owner's Drive. It uses the drive.file scope, so it can only see
files it created itself.
"""
import os
import time
import threading
from urllib.parse import urlencode

import requests

CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
SCOPE         = 'https://www.googleapis.com/auth/drive.file'
FOLDER_NAME   = 'Folio'
FOLDER_MIME   = 'application/vnd.google-apps.folder'

API    = 'https://www.googleapis.com/drive/v3'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3'

_token = {'value': None, 'expires': 0}
_lock  = threading.Lock()


class DriveError(Exception):
    pass


def configured():
    return bool(CLIENT_ID and CLIENT_SECRET)


# ── OAuth ─────────────────────────────────────────────────────────────────────

def auth_url(redirect_uri, state):
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': CLIENT_ID, 'redirect_uri': redirect_uri, 'response_type': 'code',
        'scope': SCOPE, 'access_type': 'offline', 'prompt': 'consent', 'state': state,
    })


def exchange_code(code, redirect_uri):
    """Swap the consent code for tokens; returns the refresh token."""
    r = requests.post('https://oauth2.googleapis.com/token', data={
        'code': code, 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'redirect_uri': redirect_uri, 'grant_type': 'authorization_code',
    }, timeout=20)
    data = r.json()
    if 'refresh_token' not in data:
        raise DriveError(data.get('error_description') or data.get('error') or 'No refresh token returned')
    with _lock:
        _token.update(value=data['access_token'], expires=time.time() + data.get('expires_in', 3600) - 60)
    return data['refresh_token']


def access_token(refresh_token):
    with _lock:
        if _token['value'] and time.time() < _token['expires']:
            return _token['value']
        r = requests.post('https://oauth2.googleapis.com/token', data={
            'refresh_token': refresh_token, 'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET, 'grant_type': 'refresh_token',
        }, timeout=20)
        data = r.json()
        if 'access_token' not in data:
            raise DriveError(data.get('error_description') or data.get('error') or 'Token refresh failed')
        _token.update(value=data['access_token'], expires=time.time() + data.get('expires_in', 3600) - 60)
        return _token['value']


def _auth(refresh_token):
    return {'Authorization': f'Bearer {access_token(refresh_token)}'}


def _check(r):
    if r.status_code >= 400:
        try:
            msg = r.json()['error']['message']
        except Exception:
            msg = r.text[:200]
        raise DriveError(f'Drive {r.status_code}: {msg}')
    return r


# ── Files ─────────────────────────────────────────────────────────────────────

def create_folder(refresh_token):
    r = _check(requests.post(f'{API}/files', headers=_auth(refresh_token), params={'fields': 'id'},
                             json={'name': FOLDER_NAME, 'mimeType': FOLDER_MIME}, timeout=20))
    return r.json()['id']


def start_upload(refresh_token, folder_id, name, mime, size, origin):
    """Open a resumable upload session the browser can PUT the file to directly.

    Passing the page's Origin makes Google allow the browser's cross-origin PUT.
    """
    headers = {**_auth(refresh_token), 'X-Upload-Content-Type': mime,
               'X-Upload-Content-Length': str(size)}
    if origin:
        headers['Origin'] = origin
    r = _check(requests.post(f'{UPLOAD}/files', headers=headers,
                             params={'uploadType': 'resumable', 'fields': 'id,name,mimeType,size'},
                             json={'name': name, 'parents': [folder_id]}, timeout=20))
    return r.headers['Location']


def get_meta(refresh_token, file_id):
    r = _check(requests.get(f'{API}/files/{file_id}', headers=_auth(refresh_token),
                            params={'fields': 'id,name,mimeType,size,parents,trashed'}, timeout=20))
    return r.json()


def open_media(refresh_token, file_id, range_header=None):
    """Start streaming a file's bytes; the caller iterates and closes the response."""
    headers = _auth(refresh_token)
    if range_header:
        headers['Range'] = range_header
    r = requests.get(f'{API}/files/{file_id}', headers=headers, params={'alt': 'media'},
                     stream=True, timeout=30)
    if r.status_code >= 400:
        r.close()
        raise DriveError(f'Drive {r.status_code} fetching {file_id}')
    return r


def trash(refresh_token, file_id):
    """Move to Drive's trash (recoverable for 30 days) rather than deleting outright."""
    _check(requests.patch(f'{API}/files/{file_id}', headers=_auth(refresh_token),
                          json={'trashed': True}, timeout=20))

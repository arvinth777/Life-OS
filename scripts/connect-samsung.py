#!/usr/bin/env python3
"""One-time macOS Samsung login. Credentials/callbacks stay out of files and logs.

The native callback helper forwards directly to this short-lived loopback server.
Life OS stores Samsung OAuth/master/PKCE state encrypted in Postgres. No mobile
application or always-on Mac service is installed. Run using backend/.venv Python.
"""
import argparse, getpass, json, os, plistlib, re, secrets, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import httpx

parser = argparse.ArgumentParser()
parser.add_argument('--api', default='https://life-os-api-six.vercel.app')
parser.add_argument('--country', default='us', help='Samsung sign-in page country, SDK default us')
parser.add_argument('--credentials', type=Path)
args = parser.parse_args()
if not args.api.startswith('https://') and not args.api.startswith('http://127.0.0.1:'):
    raise SystemExit('Use HTTPS for the Life OS API.')
repo = Path(__file__).resolve().parent.parent
bundle = repo.parent / 'Life OS Samsung Link.app'
binary = bundle / 'Contents/MacOS/SamsungLink'
resources = bundle / 'Contents/Resources'
resources.mkdir(parents=True, exist_ok=True)
binary.parent.mkdir(parents=True, exist_ok=True)
info = {'CFBundleIdentifier': 'local.lifeos.samsung-link', 'CFBundleName': 'Life OS Samsung Link', 'CFBundleExecutable': 'SamsungLink', 'CFBundlePackageType': 'APPL', 'LSUIElement': True, 'CFBundleURLTypes': [{'CFBundleURLName': 'Samsung account callback', 'CFBundleURLSchemes': ['ms-app']}]}
(bundle / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
subprocess.run(['xcrun', 'swiftc', '-module-cache-path', '/tmp/life-os-swift-cache', str(repo / 'desktop/SamsungLink.swift'), '-o', str(binary)], check=True)
username = 'owner'
if args.credentials:
    password = re.search(r'Password: `([^`]+)`', args.credentials.read_text(), re.I).group(1)
else:
    password = getpass.getpass('Life OS owner password: ')
http = httpx.Client(base_url=args.api.rstrip('/') + '/api', timeout=60, follow_redirects=False)
login = http.post('/auth/login', json={'username': username, 'password': password})
password = None
login.raise_for_status()
http.headers['Authorization'] = 'Bearer ' + login.json()['token']
nonce = secrets.token_urlsafe(32)
done = threading.Event()
outcome = {'ok': False, 'reason': 'no_callback'}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_POST(self):
        if self.path != '/callback' or not secrets.compare_digest(self.headers.get('X-Life-OS-Session', ''), nonce):
            self.send_error(403); return
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length < 50000:
            self.send_error(413); return
        try:
            data = json.loads(self.rfile.read(length))
            response = http.post('/integrations/samsung/auth/finish', json=data)
            outcome['ok'] = response.is_success and response.json().get('authenticated', False)
            if not outcome['ok']:
                detail = response.json().get('detail', {})
                code = detail.get('reason') if isinstance(detail, dict) else None
                allowed = {'expired','incomplete_callback','invalid_callback','unexpected_callback','provider_unreachable','provider_rejected','unexpected_provider','missing_credentials','unexpected_response'}
                outcome['reason'] = code if code in allowed else 'receiver_rejected'
            self.send_response(200 if outcome['ok'] else 400)
            self.end_headers()
        except Exception:
            self.send_error(400)
        finally:
            done.set()
server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
state = resources / 'session.json'
fd = os.open(state, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f: json.dump({'port': server.server_port, 'nonce': nonce}, f)
previous = ''
try:
    previous = subprocess.check_output([str(binary), '--register'], text=True).strip()
    start = http.post('/integrations/samsung/auth/start', json={'country': args.country})
    if not start.is_success:
        raise RuntimeError('Samsung sign-in could not start.')
    login_url = start.json()['login_url']
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    subprocess.run(['open', login_url], check=True)
    login_url = None
    print('Samsung sign-in window opened. Waiting for you to complete sign-in there.', flush=True)
    done.wait(900)
    print('Samsung account connected to Life OS.' if outcome['ok'] else 'Samsung connection needs attention (' + outcome['reason'] + '). Return to Life OS for the next step.', flush=True)
finally:
    server.shutdown() if 'thread' in locals() else None
    server.server_close()
    state.unlink(missing_ok=True)
    if previous: subprocess.run([str(binary), '--restore', previous], check=False)
    try: http.post('/auth/logout')
    except Exception: pass
    http.close()

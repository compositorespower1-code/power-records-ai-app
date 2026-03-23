import http.server
import socketserver
import os
import json
import datetime
import urllib.request
import urllib.parse
import threading

PORT = int(os.environ.get('PORT', 3001))
BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


def supabase_read(key, default=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return default
    try:
        url = f"{SUPABASE_URL}/rest/v1/artist_app?key=eq.{urllib.parse.quote(key)}&select=data"
        req = urllib.request.Request(url)
        req.add_header('apikey', SUPABASE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_KEY}')
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode())
            if rows and 'data' in rows[0]:
                return rows[0]['data']
        return default
    except Exception as e:
        print(f"[Supabase READ error] key={key}: {e}")
        return default


def supabase_write(key, data):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/artist_app?key=eq.{urllib.parse.quote(key)}"
        body = json.dumps({
            "key": key,
            "data": data,
            "updated_at": datetime.datetime.now().isoformat()
        }).encode()
        req = urllib.request.Request(url, data=body, method='PATCH')
        req.add_header('apikey', SUPABASE_KEY)
        req.add_header('Authorization', f'Bearer {SUPABASE_KEY}')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Prefer', 'return=minimal')
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
        return True
    except Exception as e:
        print(f"[Supabase WRITE error] key={key}: {e}")
        return False


ROUTE_MAP = {
    '/api/artist':     ('artist_profile', {"name": "", "photo": "", "plan": "motor", "recording_day": "", "rhythm": "enfocado"}),
    '/api/plan':       ('artist_plan', {"tasks": [], "completed": []}),
    '/api/metrics':    ('artist_metrics', {"spotify": 0, "instagram": 0, "tiktok": 0, "youtube": 0}),
    '/api/fandom':     ('artist_fandom', {"posts": [], "engagement": 0}),
    '/api/calendar':   ('artist_calendar', {"events": []}),
    '/api/portfolio':  ('artist_portfolio', {"tracks": [], "videos": []}),
    '/api/vault':      ('artist_vault', {"files": []}),
    '/api/resources':  ('artist_resources', {"items": []}),
    '/api/shows':      ('artist_shows', {"upcoming": [], "past": []}),
    '/api/alerts':     ('artist_alerts', {"items": []}),
    '/api/tareas-app': ('artist_tareas_app', {"semana": [], "mes": [], "ano12": [], "logros_semana": [], "logros_mes": [], "logros_ano12": []}),
    '/api/leads':      ('artist_leads', []),
    '/api/prompts':    ('artist_prompts', []),
    '/api/pipeline':   ('artist_pipeline', {"compositores": [], "producciones": [], "videoclips": []}),
    '/api/equipo':     ('artist_equipo', []),
    '/api/ideas':      ('artist_ideas', []),
}

POST_ROUTES = set(ROUTE_MAP.keys())


class ArtistHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        if self.path == '/health':
            self.send_json({"status": "ok"})
            return
        if self.path in ROUTE_MAP:
            key, default = ROUTE_MAP[self.path]
            data = supabase_read(key, default)
            self.send_json(data)
        else:
            super().do_GET()

    def read_post_body(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode('utf-8'))

    def do_POST(self):
        if self.path == '/api/leads':
            # Special handling: leads are appended, not overwritten
            new_lead = self.read_post_body()
            try:
                leads = supabase_read('artist_leads', [])
                new_lead['time'] = datetime.datetime.now().strftime("%H:%M")
                leads.insert(0, new_lead)
                leads = leads[:20]
                supabase_write('artist_leads', leads)
                self.send_json({"status": "success"})
            except Exception as e:
                self.send_json({"error": str(e)})
        elif self.path in POST_ROUTES:
            data = self.read_post_body()
            try:
                key, _ = ROUTE_MAP[self.path]
                supabase_write(key, data)
                self.send_json({"status": "success"})
            except Exception as e:
                self.send_json({"error": str(e)})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def keep_alive():
    """Ping self every 13 minutes to prevent Render free tier from sleeping."""
    import time
    url = f"http://localhost:{PORT}/health"
    while True:
        time.sleep(780)
        try:
            urllib.request.urlopen(url, timeout=5)
            print("[keep-alive] ping OK")
        except Exception:
            pass


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    print(f"Supabase: {'connected' if SUPABASE_URL else 'NOT SET'}")
    threading.Thread(target=keep_alive, daemon=True).start()
    print("[keep-alive] auto-ping every 13 min enabled")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ArtistHandler) as httpd:
        print(f"Power Records AI Artist App en puerto {PORT}")
        print(f"Directorio publico: {PUBLIC_DIR}")
        httpd.serve_forever()

import logging, os
log = logging.getLogger("brandguard.store")

class Store:
    """Firestore when FIREBASE_CREDENTIALS is set and valid, otherwise in-memory (data lost on restart).
    A bad or missing credentials file no longer crashes startup (which surfaced as HTTP 502 on Render): it is logged and
    the app falls back to in-memory storage. /api/health and Settings show which mode is active."""
    def __init__(self):
        self.mem, self.fs, self.init_error = {}, None, None
        path = os.getenv("FIREBASE_CREDENTIALS")
        if path:
            try:
                if not os.path.isfile(path):
                    raise FileNotFoundError(f"credentials file not found: {path}")
                import firebase_admin
                from firebase_admin import credentials, firestore
                firebase_admin.initialize_app(credentials.Certificate(path))
                self.fs = firestore.client()
            except Exception as e:
                self.init_error = f"{type(e).__name__}: {e}"
                log.error("Firestore init failed, using in-memory storage. %s", self.init_error)
    @property
    def mode(self): return "firestore" if self.fs else "in-memory"
    def put(self, col, id, data):
        (self.fs.collection(col).document(id).set(data) if self.fs else self.mem.setdefault(col, {}).__setitem__(id, data))
    def get(self, col, id):
        if self.fs:
            d = self.fs.collection(col).document(id).get(); return d.to_dict() if d.exists else None
        return self.mem.get(col, {}).get(id)
    def all(self, col):
        return [d.to_dict() for d in self.fs.collection(col).stream()] if self.fs else list(self.mem.get(col, {}).values())
    def delete(self, col, id):
        if self.fs: self.fs.collection(col).document(id).delete()
        else: self.mem.get(col, {}).pop(id, None)

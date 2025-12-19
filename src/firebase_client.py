import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore


_app: Optional[firebase_admin.App] = None
_db: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
    """Return a singleton Firestore client.

    Expects one of:
    - FIREBASE_CREDENTIALS: path to a service account JSON file, or
    - GOOGLE_APPLICATION_CREDENTIALS set in the environment, or
    - default application credentials configured in the runtime.
    """
    global _app, _db

    if _app is None:
        cred_path = os.getenv("FIREBASE_CREDENTIALS") or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )

        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _app = firebase_admin.initialize_app(cred)
        else:
            # Fallback: let firebase_admin try default credentials.
            _app = firebase_admin.initialize_app()

    if _db is None:
        _db = firestore.client()

    return _db

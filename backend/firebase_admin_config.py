import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

if os.environ.get("FIREBASE_CREDENTIALS"):
    # En producción (Render): la credencial viene como variable de entorno
    cred_dict = json.loads(os.environ["FIREBASE_CREDENTIALS"])
    cred = credentials.Certificate(cred_dict)
else:
    # En tu máquina local: sigue leyendo el archivo de siempre
    cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred)
db = firestore.client()
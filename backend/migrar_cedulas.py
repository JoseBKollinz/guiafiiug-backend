from firebase_admin_config import db
from crypto_utils import encriptar_cedula

docs = db.collection("usuarios").stream()
for doc in docs:
    data = doc.to_dict()
    cedula = data.get("cedula")
    # Evita cifrar dos veces si ya corriste esto antes
    if cedula and len(cedula) < 20:  # las cédulas cifradas son mucho más largas
        cifrada = encriptar_cedula(cedula)
        doc.reference.update({"cedula": cifrada})
        print(f"✅ Cifrado: {doc.id}")
    else:
        print(f"⏭️ Ya estaba cifrado o vacío: {doc.id}")
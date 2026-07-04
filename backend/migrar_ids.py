from firebase_admin_config import db
from crypto_utils import encriptar_cedula, desencriptar_cedula, hash_cedula

usuarios_ref = db.collection("usuarios")
docs = list(usuarios_ref.stream())

for doc in docs:
    data = doc.to_dict()
    cedula_actual = data.get("cedula")

    if not cedula_actual:
        print(f"⚠️ Saltado (sin cédula): {doc.id}")
        continue

    try:
        cedula_real = desencriptar_cedula(cedula_actual)
    except Exception:
        cedula_real = cedula_actual

    if not cedula_real:
        print(f"⚠️ Saltado (cédula vacía tras revisar): {doc.id}")
        continue

    nuevo_doc_ref = usuarios_ref.document()
    nuevo_doc_ref.set({
        "nombre": data.get("nombre"),
        "apellido": data.get("apellido"),
        "cedula": encriptar_cedula(cedula_real),
        "cedula_hash": hash_cedula(cedula_real),
        "fechaRegistro": data.get("fechaRegistro"),
    })

    favoritos = doc.reference.collection("favoritos").stream()
    for fav in favoritos:
        nuevo_doc_ref.collection("favoritos").document(fav.id).set(fav.to_dict())

    doc.reference.delete()
    print(f"✅ Migrado: {doc.id} → {nuevo_doc_ref.id}")

print("🎉 Migración completa")
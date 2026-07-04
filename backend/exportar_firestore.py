# backend/exportar_firestore.py
import json
from firebase_admin_config import db

def exportar_coleccion(nombre_coleccion):
    docs = db.collection(nombre_coleccion).stream()
    data = {}
    for doc in docs:
        data[doc.id] = doc.to_dict()
        # Si tiene subcolecciones (como favoritos), las agregamos aparte
        subcolecciones = doc.reference.collections()
        for sub in subcolecciones:
            sub_data = {d.id: d.to_dict() for d in sub.stream()}
            data[doc.id][f"_sub_{sub.id}"] = sub_data
    return data

resultado = {
    "usuarios": exportar_coleccion("usuarios"),
    "logs": exportar_coleccion("logs"),
    "espacios": exportar_coleccion("espacios"),
}

with open("export_firestore.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)

print("✅ Exportado a export_firestore.json")
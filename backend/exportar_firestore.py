import json
from firebase_admin_config import db

def exportar_coleccion(nombre_coleccion):
    docs = db.collection(nombre_coleccion).stream()
    data = {}
    for doc in docs:
        data[doc.id] = doc.to_dict()
    return data

resultado = {
    "lugares": exportar_coleccion("lugares"),
}

with open("export_lugares.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, indent=2, ensure_ascii=False, default=str)

print("✅ Exportado a export_lugares.json")
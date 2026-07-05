"""
Migración: reorganiza la colección plana "lugares" en:
  - bloques/{Bloque_X}/aulas/{aulaId}   → para aulas/laboratorios/auditorios con bloque identificable
  - areas_comunes/{areaId}              → para baños, canchas, parqueaderos, oficinas
                                           compartidas, escaleras, cafetería, etc.

Cómo se detecta el bloque:
  Se busca en el ID, nombre e info un patrón tipo "14A", "14B"... "14G"
  (ej. "Aula_14D-001" -> Bloque D) o "Bloque_X" explícito.
  Si no se encuentra ningún patrón, el lugar se considera un área común.

Ejecutar UNA SOLA VEZ, con el venv activado, desde la carpeta backend/:
    python migrar_lugares.py

No borra "lugares" automáticamente al final -- lo deja intacto como respaldo.
Si todo se ve bien en Firestore después de correr esto, puedes borrar
"lugares" manualmente desde la consola de Firebase.
"""

import re
from firebase_admin_config import db

PATRON_BLOQUE = re.compile(r'14([A-G])[-_]|Bloque[_ ]?([A-G])\b', re.IGNORECASE)


def detectar_bloque(lugar_id: str, data: dict):
    texto = f"{lugar_id} {data.get('nombre', '')} {data.get('info', '')}"
    m = PATRON_BLOQUE.search(texto)
    if m:
        letra = (m.group(1) or m.group(2)).upper()
        return f"Bloque_{letra}"
    return None


def migrar():
    lugares_ref = db.collection("lugares")
    docs = list(lugares_ref.stream())

    bloques_creados = set()
    contador_aulas = 0
    contador_areas = 0

    for doc in docs:
        lugar_id = doc.id
        data = doc.to_dict()

        bloque_id = detectar_bloque(lugar_id, data)

        if bloque_id:
            # Asegura que el documento del bloque exista (solo con su nombre)
            if bloque_id not in bloques_creados:
                nombre_bloque = bloque_id.replace("_", " ")
                db.collection("bloques").document(bloque_id).set({
                    "nombre": nombre_bloque
                }, merge=True)
                bloques_creados.add(bloque_id)

            # Copia el lugar como aula dentro del bloque, con el mismo ID
            db.collection("bloques").document(bloque_id) \
                .collection("aulas").document(lugar_id).set(data)

            contador_aulas += 1
            print(f"✅ {lugar_id} -> bloques/{bloque_id}/aulas/{lugar_id}")
        else:
            # Va a áreas comunes, con el mismo ID
            db.collection("areas_comunes").document(lugar_id).set(data)
            contador_areas += 1
            print(f"🌐 {lugar_id} -> areas_comunes/{lugar_id}")

    print()
    print("🎉 Migración completa")
    print(f"   Bloques creados: {len(bloques_creados)} ({', '.join(sorted(bloques_creados))})")
    print(f"   Aulas migradas: {contador_aulas}")
    print(f"   Áreas comunes migradas: {contador_areas}")
    print()
    print("La colección 'lugares' original NO fue borrada (queda como respaldo).")
    print("Revisa en Firebase Console que todo se vea bien antes de borrarla manualmente.")


if __name__ == "__main__":
    migrar()
import os
import pandas as pd
from database import engine, Base, SessionLocal
import models

def obtener_ruta_excel():
    nombre = "Check list Aseo 1 (1).xlsx"
    rutas = [os.path.join("data", nombre), nombre]
    for r in rutas:
        if os.path.exists(r):
            return r
    return None

def cargar_datos():
    # Crear las tablas en Neon/PostgreSQL si aún no existen
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    excel_path = obtener_ruta_excel()
    if not excel_path:
        print("❌ Archivo Excel 'Check list Aseo 1 (1).xlsx' no encontrado.")
        return

    xls = pd.ExcelFile(excel_path)
    mapeo = {
        'CD': {'id': 'CD', 'nombre': 'Comedor Didáctico'},
        'TG1': {'id': 'TG1', 'nombre': 'Taller de Gastronomía TG1'},
        'TG2': {'id': 'TG2', 'nombre': 'Taller Gastronomía TG2'},
        'TP ': {'id': 'TP', 'nombre': 'Taller de Pastelería TP'}
    }

    hojas = {h.strip(): h for h in xls.sheet_names}

    for clave, info in mapeo.items():
        hoja_real = hojas.get(clave.strip())
        if not hoja_real:
            print(f"⚠️ Advertencia: Hoja '{clave}' no encontrada en el Excel.")
            continue

        # Crear o buscar la plantilla
        plantilla = db.query(models.Plantilla).filter(models.Plantilla.id == info['id']).first()
        if not plantilla:
            plantilla = models.Plantilla(id=info['id'], nombre=info['nombre'])
            db.add(plantilla)
            db.commit()

        # Limpiar actividades previas de esa plantilla para no duplicar
        db.query(models.Actividad).filter(models.Actividad.plantilla_id == info['id']).delete()

        df = pd.read_excel(xls, sheet_name=hoja_real)
        inicio = False

        for _, row in df.iterrows():
            col1 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            col2 = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""

            if "ACTIVIDAD" in col1.upper() or "ACTIVIDAD" in col2.upper():
                inicio = True
                continue

            if inicio and col1:
                if not col1.upper().startswith("CHECK") and not col1.upper().startswith("DOCENTE"):
                    actividad = models.Actividad(plantilla_id=info['id'], descripcion=col1)
                    db.add(actividad)

        db.commit()
        print(f"✅ Cargada plantilla '{info['nombre']}' ({info['id']}) en PostgreSQL/Neon.")

    db.close()

if __name__ == "__main__":
    cargar_datos()
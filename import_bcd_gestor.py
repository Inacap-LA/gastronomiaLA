import os
import glob
import pandas as pd
from database import engine, Base, SessionLocal
import models

def buscar_archivo(patron):
    """Busca un archivo en la carpeta 'data/' y en la raíz del proyecto."""
    rutas = [
        os.path.join("data", patron),
        patron
    ]
    for r in rutas:
        coincidencias = glob.glob(r)
        if coincidencias:
            return coincidencias[0]
    return None

def importar_docentes_secciones_alumnos():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Buscar automáticamente archivos BCD y Gestor en data/ o en la raíz
    bcd_path = buscar_archivo("BCD*.xlsx") or buscar_archivo("BCD*.xls")
    gestor_path = buscar_archivo("gestor*.xlsx") or buscar_archivo("gestor*.xls")

    if not bcd_path or not gestor_path:
        print("❌ No se encontraron los archivos BCD o Gestor ni en la carpeta 'data/' ni en la raíz.")
        return

    print(f"📁 Archivo BCD encontrado en: {bcd_path}")
    print(f"📁 Archivo Gestor encontrado en: {gestor_path}")

    print("⏳ Procesando archivo BCD (Docentes y Secciones)...")
    bcd_df = pd.read_excel(bcd_path)
    bcd_clean = bcd_df.dropna(subset=['Sección'])
    bcd_clean = bcd_clean[bcd_clean['Sección'] != 'Sección']

    # 1. Cargar Docentes
    db.query(models.Docente).delete()
    docentes_df = bcd_clean[['Rut', 'Profesor']].drop_duplicates().dropna()
    for _, row in docentes_df.iterrows():
        docente = models.Docente(
            rut=str(row['Rut']).strip(),
            nombre=str(row['Profesor']).strip()
        )
        db.add(docente)
    db.commit()
    print(f"✅ Cargados {len(docentes_df)} docentes en la base de datos.")

    # 2. Cargar Secciones y Asignaturas
    db.query(models.Seccion).delete()
    secciones_df = bcd_clean[['Rut', 'Cód Asignatura', 'Asignatura', 'Sección']].drop_duplicates().dropna()
    for _, row in secciones_df.iterrows():
        seccion = models.Seccion(
            rut_docente=str(row['Rut']).strip(),
            cod_asignatura=str(row['Cód Asignatura']).strip(),
            nombre_asignatura=str(row['Asignatura']).strip(),
            codigo_seccion=str(row['Sección']).strip()
        )
        db.add(seccion)
    db.commit()
    print(f"✅ Cargadas {len(secciones_df)} secciones en la base de datos.")

    # 3. Cargar Alumnos Inscritos
    print("⏳ Procesando archivo Gestor (Alumnos)...")
    db.query(models.AlumnoInscrito).delete()
    gestor_df = pd.read_excel(gestor_path)

    secciones_unicas = sorted(secciones_df['Sección'].astype(str).str.strip().unique(), key=len, reverse=True)
    
    alumnos_registrados = 0
    for _, row in gestor_df.iterrows():
        rut_alum = str(row['RUT_ALUMNO']).strip() if pd.notna(row['RUT_ALUMNO']) else ""
        nom_alum = str(row['ALUMNO']).strip() if pd.notna(row['ALUMNO']) else ""
        carga = str(row['CARGA']).strip() if pd.notna(row['CARGA']) else ""

        if not rut_alum or not carga:
            continue

        items = carga.split(',')
        for item in items:
            item = item.strip()
            if not item:
                continue

            for sec_code in secciones_unicas:
                if sec_code in item:
                    alumno_entry = models.AlumnoInscrito(
                        rut_alumno=rut_alum,
                        nombre_alumno=nom_alum,
                        seccion=sec_code
                    )
                    db.add(alumno_entry)
                    alumnos_registrados += 1
                    break

    db.commit()
    print(f"✅ Cargadas {alumnos_registrados} inscripciones de alumnos en la base de datos.")
    db.close()

if __name__ == "__main__":
    importar_docentes_secciones_alumnos()
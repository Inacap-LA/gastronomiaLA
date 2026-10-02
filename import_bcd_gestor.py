import glob
import os
import pandas as pd
from database import Base, SessionLocal, engine
import models


def buscar_archivo(patron):
  rutas = [os.path.join('data', patron), patron]
  for r in rutas:
    coincidencias = glob.glob(r)
    if coincidencias:
      return coincidencias[0]
  return None


def importar_docentes_secciones_alumnos():
  Base.metadata.create_all(bind=engine)
  db = SessionLocal()

  bcd_path = buscar_archivo('BCD*.xlsx') or buscar_archivo('BCD*.xls')
  gestor_path = buscar_archivo('gestor*.xlsx') or buscar_archivo('gestor*.xls')

  if not bcd_path or not gestor_path:
    print('❌ No se encontraron los archivos BCD o Gestor.')
    return

  print(f'📁 Archivo BCD: {bcd_path}')
  print(f'📁 Archivo Gestor: {gestor_path}')

  # 1. Cargar Docentes
  bcd_df = pd.read_excel(bcd_path)
  bcd_clean = bcd_df.dropna(subset=['Sección'])
  bcd_clean = bcd_clean[bcd_clean['Sección'] != 'Sección']

  db.query(models.Docente).delete()
  docentes_df = bcd_clean[['Rut', 'Profesor']].drop_duplicates().dropna()
  for _, row in docentes_df.iterrows():
    docente = models.Docente(
        rut=str(row['Rut']).strip(), nombre=str(row['Profesor']).strip()
    )
    db.add(docente)
  db.commit()

  # 2. Cargar Secciones
  db.query(models.Seccion).delete()
  secciones_df = (
      bcd_clean[['Rut', 'Cód Asignatura', 'Asignatura', 'Sección']]
      .drop_duplicates()
      .dropna()
  )
  for _, row in secciones_df.iterrows():
    seccion = models.Seccion(
        rut_docente=str(row['Rut']).strip(),
        cod_asignatura=str(row['Cód Asignatura']).strip(),
        nombre_asignatura=str(row['Asignatura']).strip(),
        codigo_seccion=str(row['Sección']).strip(),
    )
    db.add(seccion)
  db.commit()

  # 3. Cargar Alumnos (Filtro de duplicados por RUT y Sección)
  print('⏳ Cargando alumnos sin duplicados...')
  db.query(models.AlumnoInscrito).delete()
  gestor_df = pd.read_excel(gestor_path)

  secciones_unicas = sorted(
      secciones_df['Sección'].astype(str).str.strip().unique(),
      key=len,
      reverse=True,
  )

  registrados = set()  # Para guardar pares (rut_alumno, seccion) únicos
  alumnos_registrados = 0

  for _, row in gestor_df.iterrows():
    rut_alum = (
        str(row['RUT_ALUMNO']).strip() if pd.notna(row['RUT_ALUMNO']) else ''
    )
    nom_alum = str(row['ALUMNO']).strip() if pd.notna(row['ALUMNO']) else ''
    carga = str(row['CARGA']).strip() if pd.notna(row['CARGA']) else ''

    if not rut_alum or not carga:
      continue

    items = carga.split(',')
    for item in items:
      item = item.strip()
      if not item:
        continue

      for sec_code in secciones_unicas:
        if sec_code in item:
          clave = (rut_alum, sec_code)
          if clave not in registrados:
            registrados.add(clave)
            alumno_entry = models.AlumnoInscrito(
                rut_alumno=rut_alum, nombre_alumno=nom_alum, seccion=sec_code
            )
            db.add(alumno_entry)
            alumnos_registrados += 1
          break

  db.commit()
  print(
      f'✅ Listo: {alumnos_registrados} inscripciones únicas guardadas en la'
      ' base de datos.'
  )
  db.close()


if __name__ == '__main__':
  importar_docentes_secciones_alumnos()
import glob
import json
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database import engine, SessionLocal, Base
import models

def inicializar_base_datos():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # 1. Carga de BCD (Docentes y Secciones)
        bcd_files = glob.glob("BCD*.xlsx")
        if bcd_files:
            archivo_bcd = bcd_files[0]
            df_bcd = pd.read_excel(archivo_bcd, sheet_name=0)
            df_bcd_clean = df_bcd.iloc[1:].dropna(subset=['Rut', 'Profesor']).copy()
            df_bcd_clean['Rut'] = df_bcd_clean['Rut'].astype(str).str.strip()
            df_bcd_clean['Profesor'] = df_bcd_clean['Profesor'].astype(str).str.strip()
            df_bcd_clean['Cód Asignatura'] = df_bcd_clean['Cód Asignatura'].astype(str).str.strip()
            df_bcd_clean['Asignatura'] = df_bcd_clean['Asignatura'].astype(str).str.strip()
            df_bcd_clean['Sección'] = df_bcd_clean['Sección'].astype(str).str.strip()

            # Insertar Docentes
            df_docentes = df_bcd_clean[['Rut', 'Profesor']].drop_duplicates()
            for _, row in df_docentes.iterrows():
                if not db.query(models.Docente).filter_by(rut=row['Rut']).first():
                    db.add(models.Docente(rut=row['Rut'], nombre=row['Profesor']))
            db.commit()

            # Insertar Secciones
            df_secciones = df_bcd_clean[['Rut', 'Cód Asignatura', 'Asignatura', 'Sección']].drop_duplicates()
            for _, row in df_secciones.iterrows():
                existe = db.query(models.Seccion).filter_by(
                    rut_docente=row['Rut'], 
                    codigo_seccion=row['Sección'],
                    cod_asignatura=row['Cód Asignatura']
                ).first()
                if not existe:
                    db.add(models.Seccion(
                        rut_docente=row['Rut'],
                        cod_asignatura=row['Cód Asignatura'],
                        nombre_asignatura=row['Asignatura'],
                        codigo_seccion=row['Sección']
                    ))
            db.commit()

        # 2. Carga de Gestor (Alumnos por Sección)
        gestor_files = glob.glob("gestor*.xlsx")
        if gestor_files and bcd_files:
            archivo_gestor = gestor_files[0]
            df_gestor = pd.read_excel(archivo_gestor, sheet_name=0)
            df_gestor_clean = df_gestor.iloc[4:].copy()
            df_gestor_clean.columns = df_gestor_clean.iloc[0]
            df_gestor_clean = df_gestor_clean.iloc[1:].reset_index(drop=True)

            secciones_existentes = set([s.codigo_seccion for s in db.query(models.Seccion.codigo_seccion).all()])

            for _, row in df_gestor_clean.iterrows():
                rut_alumno = str(row['RUT_ALUMNO']).strip()
                nombre_alumno = str(row['ALUMNO']).strip()
                carga = str(row['CARGA'])

                if pd.isna(carga) or not carga:
                    continue

                for sec in secciones_existentes:
                    if sec in carga:
                        existe = db.query(models.AlumnoInscrito).filter_by(
                            rut_alumno=rut_alumno,
                            seccion=sec
                        ).first()
                        if not existe:
                            db.add(models.AlumnoInscrito(
                                rut_alumno=rut_alumno,
                                nombre_alumno=nombre_alumno,
                                seccion=sec
                            ))
            db.commit()

        # 3. Crear Plantilla por Defecto si no existe
        if not db.query(models.Plantilla).filter_by(id="TG2").first():
            plantilla_tg2 = models.Plantilla(id="TG2", nombre="Taller Gastronomía TG2")
            db.add(plantilla_tg2)
            db.commit()

            actividades_defecto = [
                "Devolución y verificación de artículos para la docencia al finalizar la clase",
                "Limpieza y orden estante de aseo",
                "Limpieza de filtros, interior y exterior de campana",
                "Limpieza de lavamanos (limpio y secos)",
                "Limpieza de maquinar para freír",
                "Limpieza de mesones (todo el contorno, arriba y abajo)",
                "Limpieza de planchas electricas",
                "Limpieza vidrios taller (limpios y secos)",
                "Limpieza y eliminación de residuos de desagües",
                "Limpieza y lavado de horno TECHNIPAN (interior, exterior) incluidas las bandejas pulidas",
                "Limpieza y lavado de horno EKA (interior, exterior) incluidas las bandejas pulidas"
            ]
            for act in actividades_defecto:
                db.add(models.Actividad(plantilla_id="TG2", descripcion=act))
            db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error cargando datos de Excel: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inicializar_base_datos()
    print("Base de datos inicializada correctamente.")
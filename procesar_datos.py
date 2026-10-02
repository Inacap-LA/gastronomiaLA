import re
import pandas as pd
import sqlite3 # O psycopg2 / SQLAlchemy para PostgreSQL en Render

def procesar_y_cargar_datos(bcd_path, gestor_path, db_path="app_database.db"):
    # 1. Leer y limpiar BCD (Docentes y Secciones)
    raw_bcd = pd.read_excel(bcd_path)
    df_bcd = raw_bcd.drop(0).reset_index(drop=True)
    
    # Filtrar columnas clave
    bcd_clean = df_bcd[['Cód Asignatura', 'Asignatura', 'Sección', 'Rut', 'Profesor']].dropna(subset=['Sección', 'Rut']).drop_duplicates()
    
    # 2. Leer y parsear Gestor (Alumnos y Cargas)
    raw_gestor = pd.read_excel(gestor_path)
    df_gestor = raw_gestor.iloc[5:].reset_index(drop=True)
    df_gestor.columns = raw_gestor.iloc[4].values
    
    parsed_inscripciones = []
    # Expresión regular para separar: CODIGO(6) SECCION - NOMBRE
    pattern = re.compile(r'([A-Z0-9]{6})\s+([A-Za-z0-9\-\(\)]+)-(.*?)(?=(?:,\s*[A-Z0-9]{6}\s+|$))')
    
    for _, row in df_gestor.iterrows():
        rut_alumno = str(row['RUT_ALUMNO']).strip()
        nombre_alumno = str(row['ALUMNO']).strip()
        carga = str(row['CARGA']) if pd.notna(row['CARGA']) else ''
        
        matches = pattern.findall(carga)
        for m in matches:
            cod_asig = m[0]
            seccion_raw = m[1]
            # Limpiar sufijos como (F) o (E-F) para hacer match directo con BCD
            seccion_clean = re.sub(r'\([A-Z\-]+\)', '', seccion_raw).strip()
            
            parsed_inscripciones.append({
                'rut_alumno': rut_alumno,
                'nombre_alumno': nombre_alumno,
                'cod_asignatura': cod_asig,
                'seccion': seccion_clean
            })
            
    df_inscripciones = pd.DataFrame(parsed_inscripciones).drop_duplicates()

    # 3. Guardar en Base de Datos
    conn = sqlite3.connect(db_path)
    
    # Tabla Docentes / Secciones
    bcd_clean.to_sql('docentes_secciones', conn, if_exists='replace', index=False)
    
    # Tabla Alumnos e Inscripciones
    df_inscripciones.to_sql('alumnos_inscritos', conn, if_exists='replace', index=False)
    
    conn.close()
    print("¡Base de datos actualizada con éxito!")

if __name__ == "__main__":
    procesar_y_cargar_datos('BCD_01_10_2026 17_04_14.xlsx', 'gestor_27_16987896_1_1732.xlsx')
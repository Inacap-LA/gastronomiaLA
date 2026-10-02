import os
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Request, Depends, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

import models
from database import get_db, engine

# Configuración de logs para depuración en Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gastronomia")

# 1. Garantizar la existencia de 'static' ANTES de iniciar FastAPI/StaticFiles
os.makedirs("static", exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejador del ciclo de vida de la aplicación."""
    if engine:
        try:
            models.Base.metadata.create_all(bind=engine)
            logger.info("Tablas de la BD verificadas/creadas exitosamente.")
        except Exception as e:
            logger.error(f"Error al inicializar la base de datos en arranque: {e}")
    yield

app = FastAPI(
    title="Gestión de Aseo Gastronomía",
    description="Sistema para registro de checklist de aseo, control de talleres y asignación de alumnos.",
    version="1.3.1",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ==========================================
# ESQUEMAS PYDANTIC (Pydantic V2)
# ==========================================
class DocenteOut(BaseModel):
    rut: str
    nombre: str

    model_config = ConfigDict(from_attributes=True)

class SeccionOut(BaseModel):
    cod_asignatura: Optional[str] = None
    asignatura: str
    seccion: str

    model_config = ConfigDict(from_attributes=True)

class AlumnoOut(BaseModel):
    rut: str
    nombre: str

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# RUTAS DE VISTAS WEB (HTML)
# ==========================================

@app.get("/", response_class=HTMLResponse, tags=["Vistas Web"])
async def index(request: Request, db: Session = Depends(get_db)):
    """Página principal: Muestra plantillas activas y los últimos 10 registros."""
    plantillas_db = db.query(models.Plantilla).all()
    plantillas = [
        {
            "id": p.id,
            "nombre": p.nombre,
            "actividades": [a.descripcion for a in p.actividades]
        }
        for p in plantillas_db
    ]

    revisiones_db = (
        db.query(models.RegistroLimpieza)
        .order_by(models.RegistroLimpieza.fecha_registro.desc())
        .limit(10)
        .all()
    )

    revisiones = []
    for r in revisiones_db:
        actividades = json.loads(r.actividades_json) if r.actividades_json else []
        revisiones.append({
            "id": r.id,
            "taller_id": r.taller_id,
            "taller_nombre": r.taller_nombre,
            "docente": r.docente or "N/A",
            "clase": r.clase or "N/A",
            "fecha": r.fecha or "N/A",
            "encargado_taller": r.encargado_taller or "N/A",
            "actividades": actividades,
            "fecha_registro": r.fecha_registro.strftime("%Y-%m-%d %H:%M") if r.fecha_registro else ""
        })

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "plantillas": plantillas,
            "revisiones": revisiones
        }
    )


@app.get("/checklist/{taller_id}", response_class=HTMLResponse, tags=["Vistas Web"])
async def ver_checklist(request: Request, taller_id: str, db: Session = Depends(get_db)):
    """Vista de formulario para completado de checklist de un taller."""
    plantilla = db.query(models.Plantilla).filter(models.Plantilla.id == taller_id).first()
    if not plantilla:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    data = {
        "id": plantilla.id,
        "nombre": plantilla.nombre,
        "actividades": [a.descripcion for a in plantilla.actividades]
    }
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    return templates.TemplateResponse(
        request=request,
        name="checklist_form.html",
        context={
            "taller": data,
            "fecha_actual": fecha_actual
        }
    )


@app.post("/guardar-checklist", tags=["Vistas Web"])
async def guardar_checklist(request: Request, db: Session = Depends(get_db)):
    """Procesa y almacena la evaluación del checklist de un taller."""
    form_data = await request.form()

    taller_id = form_data.get("taller_id")
    docente = form_data.get("docente")
    clase = form_data.get("clase")
    fecha = form_data.get("fecha")
    encargado_taller = form_data.get("encargado_taller")

    plantilla = db.query(models.Plantilla).filter(models.Plantilla.id == taller_id).first()
    if not plantilla:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    actividades_raw = [a.descripcion for a in plantilla.actividades]
    actividades_evaluadas = []

    for idx, act in enumerate(actividades_raw):
        alumno = form_data.get(f"alumno_{idx}", "")
        estado = form_data.get(f"estado_{idx}", "CONFORME")
        observacion = form_data.get(f"obs_{idx}", "")

        actividades_evaluadas.append({
            "actividad": act,
            "alumno_encargado": alumno,
            "estado": estado,
            "observaciones": observacion
        })

    nuevo_registro = models.RegistroLimpieza(
        taller_id=taller_id,
        taller_nombre=plantilla.nombre,
        docente=docente,
        clase=clase,
        fecha=fecha,
        encargado_taller=encargado_taller,
        actividades_json=json.dumps(actividades_evaluadas, ensure_ascii=False),
        fecha_registro=datetime.now(timezone.utc)
    )

    try:
        db.add(nuevo_registro)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error en BD al guardar checklist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de base de datos al guardar la revisión: {str(e)}"
        )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ==========================================
# ENDPOINTS API REST (Selectores Dinámicos)
# ==========================================

@app.get("/api/docentes", response_model=List[DocenteOut], tags=["API Selectores"])
def obtener_docentes(db: Session = Depends(get_db)):
    """Retorna el listado de docentes ordenados por nombre."""
    return db.query(models.Docente).order_by(models.Docente.nombre).all()


@app.get("/api/docentes/{rut_docente}/secciones", response_model=List[SeccionOut], tags=["API Selectores"])
def obtener_secciones_por_docente(rut_docente: str, db: Session = Depends(get_db)):
    """Obtiene las secciones asignadas a un docente según su RUT."""
    secciones = (
        db.query(models.Seccion)
        .filter(models.Seccion.rut_docente == rut_docente)
        .order_by(models.Seccion.nombre_asignatura)
        .all()
    )
    return [
        {
            "cod_asignatura": s.cod_asignatura or "",
            "asignatura": s.nombre_asignatura,
            "seccion": s.codigo_seccion
        }
        for s in secciones
    ]


@app.get("/api/secciones/{seccion_id}/alumnos", response_model=List[AlumnoOut], tags=["API Selectores"])
def obtener_alumnos_por_seccion(seccion_id: str, db: Session = Depends(get_db)):
    """Obtiene el listado de alumnos inscritos en una sección dada."""
    alumnos = (
        db.query(models.AlumnoInscrito)
        .filter(models.AlumnoInscrito.seccion == seccion_id)
        .order_by(models.AlumnoInscrito.nombre_alumno)
        .all()
    )
    return [{"rut": a.rut_alumno, "nombre": a.nombre_alumno} for a in alumnos]
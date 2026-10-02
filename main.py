import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from database import engine, get_db
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import models
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gastronomia")

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
    description=(
        "Sistema para registro de checklist de aseo, control de talleres y"
        " asignación de alumnos."
    ),
    version="1.4.0",
    lifespan=lifespan,
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
  """Página principal: Muestra plantillas activas y listado de checklists (borradores y finalizados)."""
  plantillas_db = db.query(models.Plantilla).all()
  plantillas = [
      {
          "id": p.id,
          "nombre": p.nombre,
          "actividades": [a.descripcion for a in p.actividades],
      }
      for p in plantillas_db
  ]

  checklists_db = (
      db.query(models.Checklist)
      .order_by(models.Checklist.fecha_actualizacion.desc())
      .limit(15)
      .all()
  )

  revisiones = []
  for c in checklists_db:
    actividades = (
        json.loads(c.actividades_json)
        if hasattr(c, "actividades_json") and c.actividades_json
        else []
    )
    revisiones.append({
        "id": c.id,
        "taller_id": c.taller,
        "docente": c.rut_docente or "N/A",
        "clase": c.codigo_seccion or "N/A",
        "fecha": c.fecha.strftime("%Y-%m-%d") if c.fecha else "N/A",
        "encargado_taller": getattr(c, "encargado_taller", "N/A"),
        "estado": c.estado,
        "actividades": actividades,
        "fecha_actualizacion": (
            c.fecha_actualizacion.strftime("%Y-%m-%d %H:%M")
            if c.fecha_actualizacion
            else ""
        ),
    })

  return templates.TemplateResponse(
      request=request,
      name="index.html",
      context={"plantillas": plantillas, "revisiones": revisiones},
  )


@app.get(
    "/checklist/{taller_id}", response_class=HTMLResponse, tags=["Vistas Web"]
)
async def nuevo_checklist(
    request: Request, taller_id: str, db: Session = Depends(get_db)
):
  """Vista de formulario para crear un checklist desde cero."""
  plantilla = (
      db.query(models.Plantilla)
      .filter(models.Plantilla.id == taller_id)
      .first()
  )
  if not plantilla:
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

  data = {
      "id": plantilla.id,
      "nombre": plantilla.nombre,
      "actividades": [a.descripcion for a in plantilla.actividades],
  }
  fecha_actual = datetime.now().strftime("%Y-%m-%d")

  return templates.TemplateResponse(
      request=request,
      name="checklist_form.html",
      context={
          "taller": data,
          "checklist": None,
          "checklist_json": None,
          "fecha_actual": fecha_actual,
      },
  )


@app.get(
    "/checklist/editar/{checklist_id}",
    response_class=HTMLResponse,
    tags=["Vistas Web"],
)
async def editar_checklist(
    request: Request, checklist_id: int, db: Session = Depends(get_db)
):
  """Vista para reabrir y continuar un borrador pendiente."""
  checklist = (
      db.query(models.Checklist)
      .filter(models.Checklist.id == checklist_id)
      .first()
  )
  if not checklist:
    raise HTTPException(
        status_code=404, detail="Checklist en borrador no encontrado"
    )

  plantilla = (
      db.query(models.Plantilla)
      .filter(models.Plantilla.id == checklist.taller)
      .first()
  )
  taller_nombre = plantilla.nombre if plantilla else f"Taller {checklist.taller}"
  actividades_base = (
      [a.descripcion for a in plantilla.actividades] if plantilla else []
  )

  taller_data = {
      "id": checklist.taller,
      "nombre": taller_nombre,
      "actividades": actividades_base,
  }

  actividades_guardadas = (
      json.loads(checklist.actividades_json)
      if hasattr(checklist, "actividades_json") and checklist.actividades_json
      else []
  )

  checklist_dict = {
      "id": checklist.id,
      "taller_id": checklist.taller,
      "rut_docente": checklist.rut_docente,
      "codigo_seccion": checklist.codigo_seccion,
      "fecha": checklist.fecha.strftime("%Y-%m-%d") if checklist.fecha else "",
      "encargado_taller": getattr(checklist, "encargado_taller", ""),
      "estado": checklist.estado,
      "actividades": actividades_guardadas,
  }

  return templates.TemplateResponse(
      request=request,
      name="checklist_form.html",
      context={
          "taller": taller_data,
          "checklist": checklist,
          "checklist_json": json.dumps(checklist_dict, ensure_ascii=False),
          "fecha_actual": (
              checklist.fecha.strftime("%Y-%m-%d")
              if checklist.fecha
              else datetime.now().strftime("%Y-%m-%d")
          ),
      },
  )


@app.post("/guardar-checklist", tags=["Vistas Web"])
async def guardar_checklist(request: Request, db: Session = Depends(get_db)):
  """Procesa el guardado parcial (Borrador) o definitivo (Finalizar) del checklist."""
  form_data = await request.form()

  checklist_id = form_data.get("checklist_id")
  taller_id = form_data.get("taller_id")
  docente = form_data.get("docente")
  clase = form_data.get("clase")
  fecha_str = form_data.get("fecha")
  encargado_taller = form_data.get("encargado_taller")
  accion = form_data.get("accion", "borrador")  # 'borrador' o 'finalizar'

  plantilla = (
      db.query(models.Plantilla)
      .filter(models.Plantilla.id == taller_id)
      .first()
  )
  if not plantilla:
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

  actividades_raw = [a.descripcion for a in plantilla.actividades]
  actividades_evaluadas = []

  for idx, act in enumerate(actividades_raw):
    alumno = form_data.get(f"alumno_{idx}", "")
    estado_eval = form_data.get(f"estado_{idx}", "CONFORME")
    observacion = form_data.get(f"obs_{idx}", "")

    actividades_evaluadas.append({
        "actividad": act,
        "alumno_encargado": alumno,
        "estado": estado_eval,
        "observaciones": observacion,
    })

  # Extraer RUT y Código de Sección limpios
  rut_docente = (
      docente.split("(")[-1].replace(")", "").strip()
      if docente and "(" in docente
      else docente
  )
  codigo_seccion = (
      clase.split(" - ")[0].strip() if clase and " - " in clase else clase
  )
  fecha_obj = (
      datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else None
  )
  nuevo_estado = "FINALIZADO" if accion == "finalizar" else "BORRADOR"

  # Actualizar borrador existente o crear un nuevo registro
  if checklist_id and checklist_id.strip():
    checklist = (
        db.query(models.Checklist)
        .filter(models.Checklist.id == int(checklist_id))
        .first()
    )
    if not checklist:
      raise HTTPException(
          status_code=status.HTTP_404_NOT_FOUND,
          detail="Checklist no encontrado",
      )
  else:
    checklist = models.Checklist()
    db.add(checklist)

  checklist.taller = taller_id
  checklist.rut_docente = rut_docente or docente
  checklist.codigo_seccion = codigo_seccion or clase
  checklist.fecha = fecha_obj
  checklist.estado = nuevo_estado

  if hasattr(checklist, "encargado_taller"):
    checklist.encargado_taller = encargado_taller
  if hasattr(checklist, "actividades_json"):
    checklist.actividades_json = json.dumps(
        actividades_evaluadas, ensure_ascii=False
    )

  try:
    db.commit()
    db.refresh(checklist)
  except SQLAlchemyError as e:
    db.rollback()
    logger.error(f"Error en BD al guardar checklist: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Error de base de datos al guardar el checklist: {str(e)}",
    )

  if nuevo_estado == "FINALIZADO":
    return RedirectResponse(
        url="/?msg=finalizado", status_code=status.HTTP_303_SEE_OTHER
    )
  else:
    return RedirectResponse(
        url=f"/checklist/editar/{checklist.id}?msg=borrador_guardado",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================
# ENDPOINTS API REST (Selectores Dinámicos)
# ==========================================


@app.get(
    "/api/docentes", response_model=List[DocenteOut], tags=["API Selectores"]
)
def obtener_docentes(db: Session = Depends(get_db)):
  """Retorna el listado de docentes ordenados por nombre."""
  return db.query(models.Docente).order_by(models.Docente.nombre).all()


@app.get(
    "/api/docentes/{rut_docente}/secciones",
    response_model=List[SeccionOut],
    tags=["API Selectores"],
)
def obtener_secciones_por_docente(
    rut_docente: str, db: Session = Depends(get_db)
):
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
          "seccion": s.codigo_seccion,
      }
      for s in secciones
  ]


@app.get(
    "/api/secciones/{seccion_id}/alumnos",
    response_model=List[AlumnoOut],
    tags=["API Selectores"],
)
def obtener_alumnos_por_seccion(
    seccion_id: str, db: Session = Depends(get_db)
):
  """Obtiene el listado de alumnos inscritos en una sección dada."""
  alumnos = (
      db.query(models.AlumnoInscrito)
      .filter(models.AlumnoInscrito.seccion == seccion_id)
      .order_by(models.AlumnoInscrito.nombre_alumno)
      .all()
  )
  return [{"rut": a.rut_alumno, "nombre": a.nombre_alumno} for a in alumnos]
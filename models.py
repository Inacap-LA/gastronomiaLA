from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Plantilla(Base):
    __tablename__ = "plantillas"

    id = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)

    actividades = relationship("Actividad", back_populates="plantilla", cascade="all, delete-orphan")


class Actividad(Base):
    __tablename__ = "actividades"

    id = Column(Integer, primary_key=True, index=True)
    plantilla_id = Column(String, ForeignKey("plantillas.id"), nullable=False)
    descripcion = Column(Text, nullable=False)

    plantilla = relationship("Plantilla", back_populates="actividades")


class RegistroLimpieza(Base):
    __tablename__ = "registros_limpieza"

    id = Column(Integer, primary_key=True, index=True)
    taller_id = Column(String, nullable=False)
    taller_nombre = Column(String, nullable=False)
    docente = Column(String, nullable=True)
    clase = Column(String, nullable=True)
    fecha = Column(String, nullable=True)
    encargado_taller = Column(String, nullable=True)
    actividades_json = Column(Text, nullable=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow)


class Docente(Base):
    __tablename__ = "docentes"

    rut = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)


class Seccion(Base):
    __tablename__ = "secciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rut_docente = Column(String, index=True, nullable=False)
    cod_asignatura = Column(String, nullable=True)
    nombre_asignatura = Column(String, nullable=False)
    codigo_seccion = Column(String, index=True, nullable=False)


class AlumnoInscrito(Base):
    __tablename__ = "alumnos_inscritos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rut_alumno = Column(String, nullable=False)
    nombre_alumno = Column(String, nullable=False)
    seccion = Column(String, index=True, nullable=False)
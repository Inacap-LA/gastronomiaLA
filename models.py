from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Plantilla(Base):
    __tablename__ = "plantillas"

    id = Column(String, primary_key=True)  # CD, TG, TG2, TP
    nombre = Column(String, nullable=False)

    actividades = relationship("Actividad", back_populates="plantilla", cascade="all, delete-orphan")

class Actividad(Base):
    __tablename__ = "actividades"

    id = Column(Integer, primary_key=True, index=True)
    plantilla_id = Column(String, ForeignKey("plantillas.id"))
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
    actividades_json = Column(Text, nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
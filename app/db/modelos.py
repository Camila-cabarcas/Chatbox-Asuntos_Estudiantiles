"""
Tablas de la base de datos.

Registro ANÓNIMO de consultas para las métricas del proyecto. A propósito
NO se guarda: IP, navegador, nombre, documento ni ningún dato que permita
identificar al estudiante. La pregunta se guarda ya enmascarada.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Consulta(Base):
    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    pregunta: Mapped[str] = mapped_column(Text)            # ya enmascarada
    respuesta: Mapped[str] = mapped_column(Text)
    fichas_usadas: Mapped[list] = mapped_column(JSON, default=list)
    fuera_de_alcance: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[bool] = mapped_column(Boolean, default=False)
    latencia_ms: Mapped[int] = mapped_column(Integer)
    proveedor_llm: Mapped[str] = mapped_column(String(120))
    util: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # valoración

from sqlalchemy import String, Integer, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Registro(Base):
    __tablename__ = "registros"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    programa: Mapped[str] = mapped_column(String(100), index=True)
    lote: Mapped[int] = mapped_column(Integer, index=True)
    analito: Mapped[str] = mapped_column(String(150), index=True)
    unidad: Mapped[str] = mapped_column(String(50))

    media: Mapped[float | None] = mapped_column(Float, nullable=True)
    desviacion_estandar: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (UniqueConstraint("programa", "lote", "analito", "unidad", name="uq_registro_key"),)

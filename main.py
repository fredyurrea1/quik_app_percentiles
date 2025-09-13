from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typing import Optional, Dict, Any
import os
import pandas as pd

from .database import Base, engine, get_db
from .models import Registro

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(title="QUIK Medias y Desviaciones")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(['html', 'xml'])
)

def render_template(name: str, **context):
    template = templates_env.get_template(name)
    return HTMLResponse(template.render(**context))

# --- VISTA PRINCIPAL ---
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db),
          programa: Optional[str] = None, lote: Optional[int] = None):
    programas = [row[0] for row in db.execute(select(distinct(Registro.programa))).all() if row[0] is not None]
    lotes = []
    if programa:
        lotes = [row[0] for row in db.execute(
            select(distinct(Registro.lote)).where(Registro.programa == programa)
        ).all()]

    rows = []
    if programa and lote is not None:
        rows = db.execute(
            select(Registro)
            .where(Registro.programa == programa, Registro.lote == lote)
            .order_by(Registro.analito, Registro.unidad)
        ).scalars().all()

    return render_template("index.html",
                           request=request,
                           programas=programas,
                           lotes=lotes,
                           selected_programa=programa,
                           selected_lote=lote,
                           rows=rows)

# --- LISTA DE PROGRAMAS ---
@app.get("/programas", response_class=JSONResponse)
def get_programas(db: Session = Depends(get_db)):
    programas = [row[0] for row in db.execute(select(distinct(Registro.programa))).all() if row[0] is not None]
    return JSONResponse(programas)

# --- LISTA DE LOTES ---
@app.get("/lotes", response_class=JSONResponse)
def get_lotes(programa: str, db: Session = Depends(get_db)):
    lotes = [row[0] for row in db.execute(
        select(distinct(Registro.lote)).where(Registro.programa == programa)
    ).all()]
    return JSONResponse(lotes)

# --- TABLA DE REGISTROS ---
@app.get("/tabla", response_class=HTMLResponse)
def tabla(programa: str, lote: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Registro)
        .where(Registro.programa == programa, Registro.lote == lote)
        .order_by(Registro.analito, Registro.unidad)
    ).scalars().all()
    return render_template("_tabla.html", rows=rows)

# --- ACTUALIZAR MEDIA Y DESVIACIÓN ---
@app.post("/update", response_class=JSONResponse)
async def update(data: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Data format:
    {
      "changes": [
        {"id": 123, "media": 4.5, "desviacion_estandar": 0.8}
      ]
    }
    """
    changes = data.get("changes", [])
    updated = 0
    for ch in changes:
        reg = db.get(Registro, ch.get("id"))
        if not reg:
            continue
        for fld in ["media", "desviacion_estandar"]:
            if fld in ch:
                val = ch[fld]
                setattr(reg, fld, float(val) if val is not None else None)
        updated += 1
    db.commit()
    return JSONResponse({"updated": updated})

# --- OPCIONAL: SUBIR EXCEL INICIAL ---
SEED_TOKEN = os.getenv("SEED_TOKEN", "")

@app.post("/seed-excel", response_class=JSONResponse)
async def seed_excel(file: UploadFile = File(...), x_seed_token: str = Header(None), db: Session = Depends(get_db)):
    if SEED_TOKEN and x_seed_token != SEED_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    df = pd.read_excel(file.file)
    required = {"Programa","Lote","Analito","Unidad"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas: {missing}")
    inserted = 0
    for _, r in df.iterrows():
        ex = db.execute(select(Registro).where(
            Registro.programa==str(r['Programa']),
            Registro.lote==int(r['Lote']),
            Registro.analito==str(r['Analito']),
            Registro.unidad==str(r['Unidad']),
        )).scalar_one_or_none()
        if not ex:
            ob = Registro(
                programa=str(r['Programa']),
                lote=int(r['Lote']),
                analito=str(r['Analito']),
                unidad=str(r['Unidad']),
                media=None,
                desviacion_estandar=None
            )
            db.add(ob)
        inserted += 1
    db.commit()
    return {"processed": inserted}

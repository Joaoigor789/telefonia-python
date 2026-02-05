from fastapi import FastAPI, HTTPException, Query
from typing import List
from dataclasses import asdict
from pathlib import Path
import time

from tel import (
    PhoneValidator,
    PhoneLookup,
    GeolocationService
)

from drop.gra import grafico_por_operadora

app = FastAPI(
    title="API de Consulta Telefônica BR",
    description="API própria para validação, consulta e gráficos de telefones brasileiros",
    version="1.1.0"
)

BASE_DIR = Path(__file__).parent
GRAPH_DIR = BASE_DIR / "graficos"
GRAPH_DIR.mkdir(exist_ok=True)

@app.get("/")
def root():
    return {
        "status": "online",
        "api": "Consulta Telefônica BR"
    }

@app.get("/consulta")
def consultar_telefone(
    numero: str = Query(..., example="83993437321"),
    geo: bool = Query(False, description="Incluir geolocalização aproximada")
):
    normalized = PhoneValidator.normalize(numero)

    if not normalized:
        raise HTTPException(status_code=400, detail="Número inválido")

    info = PhoneLookup.lookup(normalized)

    if not info.valido:
        raise HTTPException(status_code=400, detail="Formato não reconhecido")

    if geo:
        geo_data = GeolocationService.get_cell_location()
        if geo_data:
            info.latitude = geo_data["latitude"]
            info.longitude = geo_data["longitude"]

    return asdict(info)


@app.post("/consulta/lote")
def consulta_em_lote(numeros: List[str]):
    resultados = []

    for numero in numeros:
        normalized = PhoneValidator.normalize(numero)
        if not normalized:
            continue

        info = PhoneLookup.lookup(normalized)
        resultados.append(asdict(info))

    return {
        "total": len(resultados),
        "resultados": resultados
    }


@app.post("/grafico/operadoras")
def grafico_operadoras(numeros: List[str]):
    resultados = []

    for numero in numeros:
        normalized = PhoneValidator.normalize(numero)
        if not normalized:
            continue

        info = PhoneLookup.lookup(normalized)
        resultados.append(asdict(info))

    if not resultados:
        raise HTTPException(status_code=400, detail="Nenhum número válido")

    
    filename = f"operadoras_{int(time.time())}.png"
    filepath = GRAPH_DIR / filename

    
    grafico_por_operadora(resultados)
    

    import matplotlib.pyplot as plt
    plt.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "status": "ok",
        "arquivo": filename,
        "caminho": str(filepath),
        "total": len(resultados)
    }

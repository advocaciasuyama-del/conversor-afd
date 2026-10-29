# -*- coding: utf-8 -*-
"""AFD (Portaria 671 tipo 3 / Control iD) → layout 13 SCI, empresa 14."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

CODIGO_EMPRESA_PADRAO = "14"


def _digitos(valor: str) -> str:
    return "".join(ch for ch in str(valor) if ch.isdigit())


def _norm_chave(valor: str) -> str:
    d = _digitos(valor)
    if not d:
        return ""
    return d.zfill(12)


def _mapa_norm(origem: dict) -> dict[str, str]:
    saida: dict[str, str] = {}
    for chave, codigo in (origem or {}).items():
        k = _norm_chave(chave)
        if k:
            saida[k] = str(codigo).strip()
    return saida


def _conjunto_norm(origem) -> set[str]:
    return {_norm_chave(x) for x in (origem or []) if _norm_chave(x)}


def carregar_depara() -> tuple[str, dict[str, str], set[str]]:
    empresa = CODIGO_EMPRESA_PADRAO
    depara: dict[str, str] = {}
    ignorados: set[str] = set()
    try:
        import sci_depara as local

        empresa = str(getattr(local, "CODIGO_EMPRESA", empresa))
        depara = _mapa_norm(getattr(local, "DEPARA_FUNCIONARIOS", {}))
        ignorados = _conjunto_norm(getattr(local, "PIS_IGNORADOS", set()))
    except ImportError:
        pass
    try:
        import streamlit as st

        sci = st.secrets.get("sci", {})
        if sci:
            empresa = str(sci.get("empresa", empresa))
            depara = {**depara, **_mapa_norm(sci.get("depara", {}))}
            ignorados = ignorados | _conjunto_norm(sci.get("ignorados", []))
    except Exception:
        pass
    return str(empresa).zfill(4)[-4:], depara, ignorados


def gerar_sci_de_batidas(
    df: pd.DataFrame,
    competencia: str | None = None,
) -> dict:
    """Monta o TXT no layout 13: EEEEFFFFFFDDMMHH:MM."""
    empresa, depara, ignorados = carregar_depara()
    convertidos = 0
    ignorados_n = 0
    sem_mapa = 0
    por_pis: Counter[str] = Counter()
    linhas_out: list[str] = []

    if df is None or df.empty:
        return {
            "texto": "",
            "registros": 0,
            "ignorados": 0,
            "sem_mapa": 0,
            "empresa": empresa,
            "diagnostico": [],
            "depara_ok": bool(depara),
        }

    trabalho = df.copy()
    if competencia:
        trabalho = trabalho[trabalho["data"].astype(str).str.startswith(competencia)]

    for row in trabalho.itertuples(index=False):
        pis = _norm_chave(getattr(row, "identificador", ""))
        if not pis:
            continue
        por_pis[pis] += 1
        if pis in ignorados:
            ignorados_n += 1
            continue
        codigo = depara.get(pis)
        if not codigo:
            sem_mapa += 1
            continue
        data = str(getattr(row, "data", ""))
        hora = str(getattr(row, "hora", ""))
        if len(data) < 10 or len(hora) < 5:
            continue
        ano, mes, dia = data.split("-")
        fun_str = str(codigo).zfill(6)[-6:]
        linhas_out.append(f"{empresa}{fun_str}{dia}{mes}{hora[:5]}\n")
        convertidos += 1

    diagnostico = []
    nomes = {}
    if "nome" in trabalho.columns and "identificador" in trabalho.columns:
        for ident, nome in trabalho.drop_duplicates("identificador")[["identificador", "nome"]].itertuples(index=False):
            nomes[_norm_chave(ident)] = str(nome)

    for pis, n in sorted(por_pis.items()):
        if pis in ignorados:
            status = "ignorado"
        elif pis in depara:
            status = f"SCI {depara[pis]}"
        else:
            status = "sem mapeamento"
        diagnostico.append(
            {
                "pis": pis,
                "nome": nomes.get(pis, ""),
                "batidas": int(n),
                "status": status,
            }
        )

    return {
        "texto": "".join(linhas_out),
        "registros": convertidos,
        "ignorados": ignorados_n,
        "sem_mapa": sem_mapa,
        "empresa": empresa,
        "diagnostico": diagnostico,
        "depara_ok": bool(depara),
    }


def gerar_arquivo_sci(
    caminho_afd: Path,
    caminho_saida: Path,
    competencia: str | None = None,
) -> dict:
    from converter import parse_afd

    df, _emp, meta = parse_afd(Path(caminho_afd))
    resultado = gerar_sci_de_batidas(df, competencia=competencia)
    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho_saida).write_text(resultado["texto"], encoding="utf-8")
    resultado["arquivo"] = str(caminho_saida)
    resultado["periodo_afd"] = meta.get("periodo", "")
    return resultado

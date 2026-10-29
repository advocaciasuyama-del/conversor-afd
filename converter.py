# -*- coding: utf-8 -*-
"""Converte AFD (Portaria 1510 ou 671) em CSV/Excel de cartão de ponto."""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def pasta_base() -> Path:
    """Pasta do .exe (amigo) ou da pasta do script (desenvolvimento)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE = pasta_base()
ENTRADA = BASE / "1-COLE-OS-AFD-AQUI"
SAIDA = BASE / "2-PLANILHAS-PRONTAS"
EXTS_AFD = {".txt", ".afd", ".dat"}

TIPOS = {
    "1": "cabecalho",
    "2": "empregador",
    "3": "marcacao",
    "4": "ajuste_relogio",
    "5": "empregado",
    "6": "evento",
    "9": "trailer",
}


def _ler_linhas(caminho: Path) -> list[str]:
    raw = caminho.read_bytes()
    for enc in ("latin-1", "iso-8859-1", "utf-8", "cp1252"):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        texto = raw.decode("latin-1", errors="replace")
    return [ln.rstrip("\r\n") for ln in texto.splitlines() if ln.strip()]


def _detectar_layout(linhas: list[str]) -> str:
    for ln in linhas:
        if len(ln) > 34 and ln[9] == "3":
            return "671" if ln[10:14].isdigit() and "T" in ln[10:34] else "1510"
    return "671"


def _cpf_fmt(ident: str) -> str:
    d = "".join(ch for ch in ident if ch.isdigit())
    d = d.lstrip("0") or "0"
    d = d.zfill(11)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return ident.strip()


def _parse_tipo5_671(ln: str) -> dict | None:
    if len(ln) < 99:
        return None
    return {
        "operacao": ln[34],
        "identificador": ln[35:47].strip(),
        "nome": ln[47:99].strip(),
    }


def _parse_tipo3_671(ln: str) -> dict | None:
    if len(ln) < 46:
        return None
    try:
        dt = datetime.strptime(ln[10:29], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return {
        "nsr": ln[0:9],
        "identificador": ln[34:46].strip(),
        "data": dt.date().isoformat(),
        "hora": dt.strftime("%H:%M"),
        "datahora": dt,
    }


def _parse_tipo3_1510(ln: str) -> dict | None:
    if len(ln) < 34:
        return None
    try:
        dt = datetime.strptime(ln[10:18] + ln[18:22], "%d%m%Y%H%M")
    except ValueError:
        return None
    return {
        "nsr": ln[0:9],
        "identificador": ln[22:34].strip(),
        "data": dt.date().isoformat(),
        "hora": dt.strftime("%H:%M"),
        "datahora": dt,
    }


def _parse_cabecalho(ln: str) -> dict:
    info: dict[str, str] = {"nsr": ln[0:9], "tipo": ln[9] if len(ln) > 9 else ""}
    if "CONDOMINIO" in ln or "LTDA" in ln.upper() or len(ln) > 50:
        # tenta nome do empregador em bloco de espaços (layout 671)
        trecho = ln[9:]
        nome = " ".join(trecho.split())
        info["cabecalho_bruto"] = nome[:180]
    return info


def parse_afd(caminho: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    linhas = _ler_linhas(caminho)
    layout = _detectar_layout(linhas)
    empregados: dict[str, str] = {}
    batidas: list[dict] = []
    contagem: dict[str, int] = defaultdict(int)

    for ln in linhas:
        if len(ln) < 10:
            continue
        tipo = ln[9]
        contagem[TIPOS.get(tipo, f"tipo_{tipo}")] += 1
        if tipo == "5" and layout == "671":
            rec = _parse_tipo5_671(ln)
            if rec and rec["identificador"]:
                empregados[rec["identificador"]] = rec["nome"]
        elif tipo == "3":
            rec = _parse_tipo3_671(ln) if layout == "671" else _parse_tipo3_1510(ln)
            if rec:
                batidas.append(rec)

    df = pd.DataFrame(batidas)
    if df.empty:
        df_emp = pd.DataFrame(columns=["identificador", "cpf", "nome"])
        return df, df_emp, {"layout": layout, "contagem": dict(contagem), "arquivo": str(caminho)}

    df["nome"] = df["identificador"].map(empregados).fillna("")
    df["cpf"] = df["identificador"].map(_cpf_fmt)
    df = df.sort_values(["nome", "identificador", "datahora", "nsr"]).reset_index(drop=True)

    df_emp = pd.DataFrame(
        [
            {"identificador": k, "cpf": _cpf_fmt(k), "nome": v, "batidas": int((df["identificador"] == k).sum())}
            for k, v in sorted(empregados.items(), key=lambda x: x[1])
        ]
    )
    sem_cadastro = sorted(set(df["identificador"]) - set(empregados))
    for ident in sem_cadastro:
        df_emp.loc[len(df_emp)] = {
            "identificador": ident,
            "cpf": _cpf_fmt(ident),
            "nome": "",
            "batidas": int((df["identificador"] == ident).sum()),
        }

    meta = {
        "layout": layout,
        "contagem": dict(contagem),
        "arquivo": caminho.name,
        "periodo": f"{df['data'].min()} a {df['data'].max()}" if not df.empty else "",
        "empregados": len(df_emp),
        "marcacoes": len(df),
    }
    return df, df_emp, meta


def _minutos_pares(horas: list[str]) -> tuple[int, str]:
    """Soma intervalos 1-2, 3-4... Se ímpar, a última fica sem par."""
    total = 0
    i = 0
    while i + 1 < len(horas):
        t1 = datetime.strptime(horas[i], "%H:%M")
        t2 = datetime.strptime(horas[i + 1], "%H:%M")
        if t2 < t1:
            t2 += timedelta(days=1)
        total += int((t2 - t1).total_seconds() // 60)
        i += 2
    alerta = ""
    if len(horas) % 2 == 1:
        alerta = "batidas ímpares"
    if any(h == "00:00" for h in horas):
        alerta = (alerta + "; " if alerta else "") + "tem 00:00"
    return total, alerta


def _fmt_horas(minutos: int) -> str:
    sinal = "-" if minutos < 0 else ""
    minutos = abs(minutos)
    return f"{sinal}{minutos // 60:02d}:{minutos % 60:02d}"


def montar_cartoes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    grp = (
        df.groupby(["identificador", "cpf", "nome", "data"], dropna=False)["hora"]
        .apply(list)
        .reset_index()
    )
    max_bat = int(grp["hora"].map(len).max())
    colunas = [f"Batida {i}" for i in range(1, max_bat + 1)]
    expandido = pd.DataFrame(grp["hora"].tolist(), columns=colunas)
    cartao = pd.concat(
        [grp[["identificador", "cpf", "nome", "data"]].reset_index(drop=True), expandido],
        axis=1,
    )
    horas_calc = grp["hora"].map(_minutos_pares)
    cartao["Horas trabalhadas"] = [ _fmt_horas(m) for m, _ in horas_calc ]
    cartao["Alerta"] = [ a for _, a in horas_calc ]
    cartao["N batidas"] = grp["hora"].map(len).values
    cartao["Justificativa / ajuste manual"] = ""
    return cartao


def montar_analise(cartao: pd.DataFrame, df_emp: pd.DataFrame) -> pd.DataFrame:
    if cartao.empty:
        return pd.DataFrame()
    minutos = cartao["Horas trabalhadas"].map(
        lambda h: int(h.split(":")[0]) * 60 + int(h.split(":")[1]) if isinstance(h, str) and ":" in h else 0
    )
    tmp = cartao.copy()
    tmp["_min"] = minutos
    resumo = (
        tmp.groupby(["identificador", "cpf", "nome"], dropna=False)
        .agg(
            dias=("data", "nunique"),
            total_batidas=("N batidas", "sum"),
            dias_impares=("Alerta", lambda s: int(s.astype(str).str.contains("ímpares").sum())),
            minutos=("_min", "sum"),
        )
        .reset_index()
    )
    resumo["horas_total"] = resumo["minutos"].map(_fmt_horas)
    resumo = resumo.drop(columns=["minutos"])
    return resumo.sort_values(["nome", "identificador"])


def _nome_seguro(stem: str) -> str:
    limpo = re.sub(r'[<>:"/\\|?*]', "_", stem).strip(" .")
    return limpo or "AFD"


def listar_afds(pasta: Path | None = None) -> list[Path]:
    pasta = pasta or ENTRADA
    if not pasta.exists():
        return []
    arquivos: list[Path] = []
    for p in sorted(pasta.iterdir()):
        if not p.is_file():
            continue
        if p.name.startswith("_") or p.name.upper().startswith("LEIA"):
            continue
        if p.suffix.lower() in EXTS_AFD or p.name.upper().startswith("AFD"):
            arquivos.append(p)
    return arquivos


def _abas_excel(
    df_batidas: pd.DataFrame,
    df_emp: pd.DataFrame,
    cartao: pd.DataFrame,
    analise: pd.DataFrame,
):
    cols_bat = ["nsr", "identificador", "cpf", "nome", "data", "hora"]
    return {
        "Cartoes": cartao if not cartao.empty else pd.DataFrame({"aviso": ["Nenhuma batida tipo 3"]}),
        "Analise": analise if not analise.empty else pd.DataFrame(),
        "Funcionarios": df_emp if not df_emp.empty else pd.DataFrame(),
        "Batidas": df_batidas[cols_bat] if not df_batidas.empty else pd.DataFrame(),
    }


def excel_bytes(
    df_batidas: pd.DataFrame,
    df_emp: pd.DataFrame,
    cartao: pd.DataFrame,
    analise: pd.DataFrame,
) -> bytes:
    from io import BytesIO

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for aba, frame in _abas_excel(df_batidas, df_emp, cartao, analise).items():
            frame.to_excel(xw, sheet_name=aba, index=False)
    return buf.getvalue()


def processar_memoria(nome_arquivo: str, conteudo: bytes) -> dict:
    import tempfile

    sufixo = Path(nome_arquivo).suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
        tmp.write(conteudo)
        caminho = Path(tmp.name)
    try:
        df_batidas, df_emp, meta = parse_afd(caminho)
    finally:
        caminho.unlink(missing_ok=True)
    cartao = montar_cartoes(df_batidas)
    analise = montar_analise(cartao, df_emp)
    stem = _nome_seguro(Path(nome_arquivo).stem)
    meta["arquivo"] = nome_arquivo
    meta["stem"] = stem
    meta["xlsx_bytes"] = excel_bytes(df_batidas, df_emp, cartao, analise)
    meta["xlsx_nome"] = f"{stem}.xlsx"
    return meta


def salvar(
    df_batidas: pd.DataFrame,
    df_emp: pd.DataFrame,
    cartao: pd.DataFrame,
    analise: pd.DataFrame,
    pasta_detalhe: Path,
    xlsx_destino: Path,
) -> Path:
    pasta_detalhe.mkdir(parents=True, exist_ok=True)
    xlsx_destino.parent.mkdir(parents=True, exist_ok=True)
    sep = ";"
    cols_bat = ["nsr", "identificador", "cpf", "nome", "data", "hora"]
    if not df_emp.empty:
        df_emp.to_csv(pasta_detalhe / "funcionarios.csv", index=False, sep=sep, encoding="utf-8-sig")
    if not df_batidas.empty:
        df_batidas[cols_bat].to_csv(pasta_detalhe / "batidas.csv", index=False, sep=sep, encoding="utf-8-sig")
    if not cartao.empty:
        cartao.to_csv(pasta_detalhe / "cartoes_ponto.csv", index=False, sep=sep, encoding="utf-8-sig")
    if not analise.empty:
        analise.to_csv(pasta_detalhe / "analise.csv", index=False, sep=sep, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_destino, engine="openpyxl") as xw:
        (cartao if not cartao.empty else pd.DataFrame({"aviso": ["Nenhuma batida tipo 3"]})).to_excel(
            xw, sheet_name="Cartoes", index=False
        )
        (analise if not analise.empty else pd.DataFrame()).to_excel(xw, sheet_name="Analise", index=False)
        (df_emp if not df_emp.empty else pd.DataFrame()).to_excel(xw, sheet_name="Funcionarios", index=False)
        (df_batidas[cols_bat] if not df_batidas.empty else pd.DataFrame()).to_excel(
            xw, sheet_name="Batidas", index=False
        )
    return xlsx_destino


def processar_arquivo(origem: Path, pasta_saida: Path | None = None) -> dict:
    pasta_saida = pasta_saida or SAIDA
    pasta_saida.mkdir(parents=True, exist_ok=True)
    stem = _nome_seguro(origem.stem)
    pasta_detalhe = pasta_saida / "csv" / stem
    xlsx = pasta_saida / f"{stem}.xlsx"

    df_batidas, df_emp, meta = parse_afd(origem)
    cartao = montar_cartoes(df_batidas)
    analise = montar_analise(cartao, df_emp)
    salvar(df_batidas, df_emp, cartao, analise, pasta_detalhe, xlsx)
    meta["xlsx"] = str(xlsx)
    meta["pasta_csv"] = str(pasta_detalhe)
    return meta


def processar_pasta(pasta_entrada: Path | None = None, pasta_saida: Path | None = None) -> list[dict]:
    ENTRADA.mkdir(parents=True, exist_ok=True)
    SAIDA.mkdir(parents=True, exist_ok=True)
    resultados = []
    for arq in listar_afds(pasta_entrada):
        resultados.append(processar_arquivo(arq, pasta_saida))
    return resultados


def main() -> None:
    parser = argparse.ArgumentParser(description="AFD → planilha de cartão de ponto")
    parser.add_argument("arquivo", nargs="?", help="Um AFD específico. Sem argumento: processa a pasta 1-COLE-OS-AFD-AQUI")
    parser.add_argument("-o", "--saida", default=str(SAIDA))
    args = parser.parse_args()

    if args.arquivo:
        origem = Path(args.arquivo)
        if not origem.exists():
            raise SystemExit(f"Arquivo não encontrado: {origem}")
        meta = processar_arquivo(origem, Path(args.saida))
        print(f"Layout: Portaria {meta['layout']}")
        print(f"Arquivo: {meta['arquivo']}")
        print(f"Período: {meta.get('periodo')}")
        print(f"Marcações: {meta.get('marcacoes')} | Funcionários: {meta.get('empregados')}")
        print(f"Planilha: {meta['xlsx']}")
        return

    arquivos = listar_afds()
    if not arquivos:
        print(f"Nenhum AFD em {ENTRADA}")
        print("Cole os .txt / .afd nessa pasta e rode de novo.")
        return
    for meta in processar_pasta(pasta_saida=Path(args.saida)):
        print(f"OK {meta['arquivo']} → {meta['xlsx']} ({meta.get('marcacoes')} batidas)")


if __name__ == "__main__":
    main()

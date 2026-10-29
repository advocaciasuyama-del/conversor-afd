# -*- coding: utf-8 -*-
"""Gera o TXT no layout 13 do SCI (empresa 14) a partir do AFD."""
from __future__ import annotations

from pathlib import Path

from sci import gerar_arquivo_sci

AFD = Path(__file__).resolve().parent / "1-COLE-OS-AFD-AQUI" / "AFD0001400375039428351065456000170REP_C.txt"
SAIDA = Path(__file__).resolve().parent / "2-PLANILHAS-PRONTAS" / "cevr_ponto_102026_tratado.txt"


if __name__ == "__main__":
    r = gerar_arquivo_sci(AFD, SAIDA, competencia="2026-10")
    print("====================================================")
    print("          DIAGNOSTICO DE PIS ENCONTRADOS            ")
    print("====================================================")
    for item in r["diagnostico"]:
        print(f" -> {item['pis']} | {item['nome']} | {item['batidas']} batidas | {item['status']}")
    print("----------------------------------------------------")
    print(f"Empresa SCI: {r['empresa']}")
    print(f"Periodo no AFD: {r.get('periodo_afd')}")
    print(f"Competencia exportada: 2026-10")
    print(f"Marcacoes convertidas: {r['registros']}")
    print(f"Ignoradas: {r['ignorados']} | Sem mapeamento: {r['sem_mapa']}")
    print(f"Arquivo: {r['arquivo']}")
    print("====================================================")

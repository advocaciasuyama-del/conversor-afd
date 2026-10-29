# -*- coding: utf-8 -*-
"""Interface web: login, envia AFD e baixa a planilha."""
from __future__ import annotations

import zipfile
from io import BytesIO

import streamlit as st

from converter import processar_memoria

USUARIO = "ponto"
SENHA = "Ribeira2026"

st.set_page_config(page_title="Conversor AFD → planilha", layout="centered")


def _credenciais() -> tuple[str, str]:
    try:
        auth = st.secrets.get("auth", {})
        return str(auth.get("usuario", USUARIO)), str(auth.get("senha", SENHA))
    except Exception:
        return USUARIO, SENHA


def exigir_login() -> None:
    if st.session_state.get("logado"):
        with st.sidebar:
            st.caption(f"Logado como {st.session_state.get('usuario_ok', '')}")
            if st.button("Sair"):
                st.session_state.clear()
                st.rerun()
        return

    usuario_ok, senha_ok = _credenciais()
    st.title("Conversor de ponto AFD")
    st.caption("Entre com o login que você recebeu.")
    with st.form("login"):
        usuario = st.text_input("Login")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if entrar:
        if usuario.strip() == usuario_ok and senha == senha_ok:
            st.session_state["logado"] = True
            st.session_state["usuario_ok"] = usuario.strip()
            st.rerun()
        st.error("Login ou senha incorretos.")
    st.stop()


exigir_login()

st.title("Conversor de ponto AFD")
st.caption("Envie o arquivo do relógio e baixe a planilha de cada um.")

arquivos = st.file_uploader(
    "Arquivos AFD (.txt, .afd, .dat)",
    type=["txt", "afd", "dat"],
    accept_multiple_files=True,
)

if not arquivos:
    st.info("Solte um ou mais arquivos do pen drive acima.")
    st.stop()

if st.button("Processar e gerar planilhas", type="primary", use_container_width=True):
    resultados = []
    erros = []
    barra = st.progress(0.0)
    for i, up in enumerate(arquivos):
        try:
            resultados.append(processar_memoria(up.name, up.getvalue()))
        except Exception as exc:
            erros.append(f"{up.name}: {exc}")
        barra.progress((i + 1) / len(arquivos))
    st.session_state["resultados"] = resultados
    st.session_state["erros"] = erros

resultados = st.session_state.get("resultados") or []
erros = st.session_state.get("erros") or []

for msg in erros:
    st.error(msg)

if not resultados:
    st.stop()

st.success(f"{len(resultados)} planilha(s) pronta(s) para baixar.")

if len(resultados) > 1:
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in resultados:
            zf.writestr(r["xlsx_nome"], r["xlsx_bytes"])
    st.download_button(
        "Baixar todas em um ZIP",
        data=zip_buf.getvalue(),
        file_name="planilhas_ponto.zip",
        mime="application/zip",
        use_container_width=True,
    )

st.divider()
for r in resultados:
    with st.container(border=True):
        st.subheader(r["xlsx_nome"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Batidas", r.get("marcacoes") or 0)
        c2.metric("Funcionários", r.get("empregados") or 0)
        c3.metric("Portaria", r.get("layout") or "—")
        if r.get("periodo"):
            st.caption(f"Período: {r['periodo']}")
        st.download_button(
            f"Baixar {r['xlsx_nome']}",
            data=r["xlsx_bytes"],
            file_name=r["xlsx_nome"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl-{r['xlsx_nome']}",
            use_container_width=True,
        )

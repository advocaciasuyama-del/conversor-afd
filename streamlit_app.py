# -*- coding: utf-8 -*-
"""Interface web Conmari: login, envia AFD e baixa a planilha."""
from __future__ import annotations

import base64
import zipfile
from io import BytesIO
from pathlib import Path

import streamlit as st

from converter import processar_memoria

USUARIO = "ponto"
SENHA = "Ribeira2026"
TITULO = "Tratamento de Ponto Eletrônico"
MARCA = "Conmari"
LOGO = Path(__file__).resolve().parent / "static" / "logo_conmari.svg"

st.set_page_config(
    page_title=f"{TITULO} — {MARCA}",
    page_icon=str(LOGO) if LOGO.exists() else "⏱️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def _logo_data_uri() -> str:
    if not LOGO.exists():
        return ""
    payload = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def aplicar_visual() -> None:
    logo = _logo_data_uri()
    st.markdown(
        f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {{
    font-family: "Instrument Sans", "Segoe UI", sans-serif;
  }}
  .stApp {{
    background: #0B0F14;
    color: #E8EEF4;
  }}
  [data-testid="stHeader"] {{
    background: transparent;
  }}
  [data-testid="stToolbar"] {{
    display: none;
  }}
  footer {{
    visibility: hidden;
  }}
  .block-container {{
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 760px;
  }}
  .cm-brand {{
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: .35rem;
    margin: .4rem 0 1.6rem;
  }}
  .cm-brand img {{
    width: 220px;
    max-width: 70vw;
  }}
  .cm-kicker {{
    margin: 0;
    letter-spacing: .28em;
    text-transform: uppercase;
    font-size: .68rem;
    color: #B8954A;
    font-weight: 600;
  }}
  .cm-title {{
    margin: .15rem 0 0;
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -.02em;
    color: #F4F7FB;
  }}
  .cm-sub {{
    margin: .15rem 0 0;
    color: #9AA8B6;
    font-size: .95rem;
  }}
  [data-testid="stForm"] {{
    background: #121820;
    border: 1px solid #2A3340;
    border-radius: 18px;
    padding: 1.15rem 1.15rem .35rem;
  }}
  [data-testid="stTextInput"] input {{
    background: #0B0F14 !important;
    color: #F4F7FB !important;
    border-radius: 12px !important;
  }}
  .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
    background: #B8954A !important;
    color: #14110C !important;
    border: 0 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    letter-spacing: .02em;
    height: 2.8rem;
    box-shadow: none !important;
  }}
  .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {{
    background: #A68542 !important;
    filter: none;
  }}
  [data-testid="stFileUploader"] {{
    background: #121820;
    border: 1px dashed #3A4554;
    border-radius: 18px;
    padding: .85rem 1rem 1.1rem;
  }}
  [data-testid="stMetric"] {{
    background: #121820;
    border: 1px solid #2A3340;
    border-radius: 14px;
    padding: .7rem .85rem;
  }}
  [data-testid="stAlert"] {{
    border-radius: 14px;
  }}
  [data-testid="stSidebar"] {{
    background: #10151C;
    border-right: 1px solid #243040;
  }}
  .cm-card {{
    background: #121820;
    border: 1px solid #2A3340;
    border-radius: 18px;
    padding: 1rem 1.1rem 1.15rem;
    margin-bottom: .9rem;
  }}
</style>
<div class="cm-brand">
  {"<img src='" + logo + "' alt='Conmari' />" if logo else f'<p class="cm-kicker">{MARCA}</p>'}
  <h1 class="cm-title">{TITULO}</h1>
  <p class="cm-sub">Conversão de AFD do relógio em planilha de ponto</p>
</div>
""",
        unsafe_allow_html=True,
    )


def _credenciais() -> tuple[str, str]:
    try:
        auth = st.secrets.get("auth", {})
        return str(auth.get("usuario", USUARIO)), str(auth.get("senha", SENHA))
    except Exception:
        return USUARIO, SENHA


def exigir_login() -> None:
    if st.session_state.get("logado"):
        with st.sidebar:
            if LOGO.exists():
                st.image(str(LOGO), use_container_width=True)
            st.caption(MARCA)
            st.caption(f"Logado como **{st.session_state.get('usuario_ok', '')}**")
            if st.button("Sair", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        return

    usuario_ok, senha_ok = _credenciais()
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


aplicar_visual()
exigir_login()

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
        if r.get("sci_bytes"):
            st.download_button(
                f"Baixar TXT SCI empresa 14 ({r.get('sci_registros') or 0} marcações)",
                data=r["sci_bytes"],
                file_name=r.get("sci_nome") or "ponto_sci.txt",
                mime="text/plain",
                key=f"sci-{r['xlsx_nome']}",
                use_container_width=True,
            )
            if r.get("sci_diagnostico"):
                with st.expander("De-para SCI"):
                    for item in r["sci_diagnostico"]:
                        st.caption(
                            f"{item.get('nome') or '—'} · {item.get('pis')} · "
                            f"{item.get('batidas')} batidas · {item.get('status')}"
                        )

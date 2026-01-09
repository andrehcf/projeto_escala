import streamlit as st

st.set_page_config(layout="wide", page_title="Sistema de Escalas", page_icon="🗓️")

# --- Definicao das Paginas ---
# Aqui estamos dizendo: "Entre na pasta 'pages' e pegue o arquivo"

pg_gerador = st.Page("pages/Gerador_de_Escala.py", title="Gerar Escala (Matriz)", icon="🚀", default=True)
pg_historico = st.Page("pages/Historico_de_escalas.py", title="Histórico e Excel", icon="📂") # Atenção ao 'escalas' minusculo ou maiusculo
pg_ciclo = st.Page("pages/Gerador_de_ciclo.py", title="Criar Novo Ciclo", icon="🔄")

pg_analistas = st.Page("pages/Gerenciar_Analistas.py", title="Gerenciar Analistas", icon="👥")
pg_indisp = st.Page("pages/Registrar_Indisponibilidade.py", title="Registrar Indisponibilidade", icon="⛔")
pg_sobreaviso = st.Page("pages/Sobreaviso.py", title="Cadastrar Sobreaviso", icon="⚠️")

pg_config = st.Page("pages/Configuracoes.py", title="Configurações do Sistema", icon="⚙️")

# --- Montagem do Menu ---
pg = st.navigation({
    "Escala & Geração": [pg_gerador, pg_ciclo, pg_historico],
    "Gestão de Dados": [pg_analistas, pg_indisp, pg_sobreaviso],
    "Sistema": [pg_config]
})

pg.run()

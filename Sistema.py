import streamlit as st

# --- Configuracao Geral da Pagina ---
st.set_page_config(layout="wide", page_title="Sistema de Escalas", page_icon="🗓️")

# --- Definicao das Paginas ---
# ATENÇÃO: Verifique se os nomes dos arquivos abaixo batem EXATAMENTE (maiúsculas/minúsculas) com o GitHub

pg_gerador = st.Page("Gerador_de_Escala.py", title="Gerar Escala (Matriz)", icon="🚀", default=True)

# Corrigido "Escalas" para "escalas" (verifique qual o nome real do seu arquivo)
pg_historico = st.Page("Historico_de_escalas.py", title="Histórico e Excel", icon="📂") 

pg_ciclo = st.Page("Gerador_de_ciclo.py", title="Criar Novo Ciclo", icon="🔄")

pg_analistas = st.Page("Gerenciar_Analistas.py", title="Gerenciar Analistas", icon="👥")
pg_indisp = st.Page("Registrar_Indisponibilidade.py", title="Registrar Indisponibilidade", icon="⛔")
pg_sobreaviso = st.Page("Sobreaviso.py", title="Cadastrar Sobreaviso", icon="⚠️")

pg_config = st.Page("Configuracoes.py", title="Configurações do Sistema", icon="⚙️")

# --- Montagem do Menu com Grupos e Ordem ---
pg = st.navigation({
    "Escala & Geração": [pg_gerador, pg_ciclo, pg_historico],
    "Gestão de Dados": [pg_analistas, pg_indisp, pg_sobreaviso],
    "Sistema": [pg_config]
})

# --- Executa a navegacao ---
pg.run()

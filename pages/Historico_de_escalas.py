import streamlit as st
import sqlite3
import pandas as pd
import database
import utils

# Carrega configurações
HORAS_TURNO = utils.load_shift_hours_from_db()

st.title("Consulta de Escalas Salvas (Historico)")
database.init_all_db_tables()

try:
    conn = database.get_db_connection()
    # CORREÇÃO SQL: Adicionamos c.data_inicio no SELECT para poder usar no ORDER BY
    query_ciclos = """
        SELECT DISTINCT c.id, c.nome_ciclo, c.data_inicio 
        FROM ciclos c 
        JOIN escala_salva e ON c.id = e.id_ciclo 
        ORDER BY c.data_inicio DESC
    """
    df_ciclos_salvos = pd.read_sql_query(query_ciclos, conn)
    
    ciclos_dict = dict(zip(df_ciclos_salvos['id'], df_ciclos_salvos['nome_ciclo']))
    conn.close()
except Exception as e:
    st.error(f"Erro ao carregar ciclos: {e}")
    ciclos_dict = {}

if not ciclos_dict:
    st.info("Nenhuma escala foi salva no historico ainda.")
else:
    st.header("1. Selecione o Ciclo para Consultar")
    id_ciclo_selecionado = st.selectbox(
        "Selecione o Ciclo",
        options=ciclos_dict.keys(),
        format_func=lambda x: ciclos_dict[x]
    )

    if id_ciclo_selecionado:
        conn = database.get_db_connection()
        try:
            # Carrega dados da escala salva
            df_historico = pd.read_sql_query(
                f"SELECT nome_analista, nome_coluna_dia, turno FROM escala_salva WHERE id_ciclo = {id_ciclo_selecionado}",
                conn)
            
            # Carrega ordem das colunas (dias)
            df_dias_ciclo = pd.read_sql_query(
                f"SELECT nome_coluna FROM ciclo_dias WHERE id_ciclo = {id_ciclo_selecionado} ORDER BY data_dia ASC",
                conn)
            colunas_ordenadas = df_dias_ciclo['nome_coluna'].tolist()

            # Define ordem das linhas (Analistas + Mentor + Sobreaviso)
            df_analistas = pd.read_sql_query("SELECT nome FROM analistas ORDER BY nome", conn)
            linhas_salvas = df_historico['nome_analista'].unique()
            linhas_analistas = sorted([nome for nome in linhas_salvas if nome not in ["MENTOR", "SOBREAVISO"]])

            linhas_ordenadas = linhas_analistas
            if "MENTOR" in linhas_salvas: linhas_ordenadas.append("MENTOR")
            if "SOBREAVISO" in linhas_salvas: linhas_ordenadas.append("SOBREAVISO")

            conn.close()

            # Monta a Matriz Visual
            df_escala_matrix = df_historico.pivot(
                index='nome_analista',
                columns='nome_coluna_dia',
                values='turno'
            )

            # Reordena colunas e linhas
            df_escala_matrix = df_escala_matrix.reindex(columns=colunas_ordenadas)
            df_escala_matrix = df_escala_matrix.reindex(index=linhas_ordenadas).dropna(how='all')

            st.markdown(f"### 📅 Escala: {ciclos_dict[id_ciclo_selecionado]}")
            st.dataframe(df_escala_matrix, use_container_width=True)

            st.markdown("---")
            st.header("2. Download")
            
            df_excel = utils.to_excel(df_escala_matrix)
            
            # Ajuste no nome do arquivo para evitar caracteres inválidos
            nome_arquivo = f"escala_{ciclos_dict[id_ciclo_selecionado]}.xlsx".replace('/', '-').replace(' ', '_')
            
            st.download_button(
                label="📥 Baixar esta Escala como Excel",
                data=df_excel,
                file_name=nome_arquivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        except Exception as e:
            st.error(f"Erro ao carregar a escala do historico: {e}")
            if conn: conn.close()

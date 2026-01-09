import streamlit as st
import sqlite3
import pandas as pd
import database
import utils
HORAS_TURNO = utils.load_shift_hours_from_db()
st.title("Consulta de Escalas Salvas (Historico)")
database.init_all_db_tables()

try:
    conn = database.get_db_connection()
    df_ciclos_salvos = pd.read_sql_query(
        "SELECT DISTINCT c.id, c.nome_ciclo FROM ciclos c JOIN escala_salva e ON c.id = e.id_ciclo ORDER BY c.data_inicio DESC",
        conn
    )
    ciclos_dict = dict(zip(df_ciclos_salvos['id'], df_ciclos_salvos['nome_ciclo']))
    conn.close()
except Exception as e:
    st.error(f"Erro ao carregar ciclos: {e}")
    ciclos_dict = {}

if not ciclos_dict:
    st.error("Nenhuma escala foi salva no historico ainda.")
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
            df_historico = pd.read_sql_query(
                f"SELECT nome_analista, nome_coluna_dia, turno FROM escala_salva WHERE id_ciclo = {id_ciclo_selecionado}",
                conn)
            df_dias_ciclo = pd.read_sql_query(
                f"SELECT nome_coluna FROM ciclo_dias WHERE id_ciclo = {id_ciclo_selecionado} ORDER BY data_dia ASC",
                conn)
            colunas_ordenadas = df_dias_ciclo['nome_coluna'].tolist()

            df_analistas = pd.read_sql_query("SELECT nome FROM analistas ORDER BY nome", conn)
            linhas_salvas = df_historico['nome_analista'].unique()
            linhas_analistas = sorted([nome for nome in linhas_salvas if nome not in ["MENTOR", "SOBREAVISO"]])

            linhas_ordenadas = linhas_analistas
            if "MENTOR" in linhas_salvas: linhas_ordenadas.append("MENTOR")
            if "SOBREAVISO" in linhas_salvas: linhas_ordenadas.append("SOBREAVISO")

            conn.close()

            df_escala_matrix = df_historico.pivot(
                index='nome_analista',
                columns='nome_coluna_dia',
                values='turno'
            )

            df_escala_matrix = df_escala_matrix.reindex(columns=colunas_ordenadas)
            df_escala_matrix = df_escala_matrix.reindex(index=linhas_ordenadas).dropna(how='all')

            st.header(f"Escala Salva: {ciclos_dict[id_ciclo_selecionado]}")
            st.dataframe(df_escala_matrix, use_container_width=True)

            st.header("2. Download")
            df_excel = utils.to_excel(df_escala_matrix)
            st.download_button(
                label="Baixar esta Escala como Excel",
                data=df_excel,
                file_name=f"escala_{ciclos_dict[id_ciclo_selecionado]}.xlsx".replace('/', '-'),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Erro ao carregar a escala do historico: {e}")
            if conn: conn.close()
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import holidays
import sys
import database

st.title("Gerenciador de Ciclos")

database.init_all_db_tables()

# --- 1. Criar Novo Ciclo ---
st.header("1. Criar Novo Ciclo")

with st.form("form_novo_ciclo", clear_on_submit=True):
    nome_ciclo = st.text_input("Nome do Ciclo*", help="Ex: Ciclo Nov/Dez 2025")
    col1, col2 = st.columns(2)
    with col1:
        today = datetime.today()
        default_start_date = today.replace(day=15)
        cycle_start_input = st.date_input("Selecione o dia 15 do mes de INICIO", value=default_start_date)
    with col2:
        # Obs: Os estados aqui serao usados apenas se a data NAO estiver no banco mestre
        states = ["PR", "SP"]
        st.write("Feriados Estaduais Padrão: PR, SP (Use 'Configurações' para personalizar)")

    submit_button = st.form_submit_button("Analisar e Salvar Ciclo")

if submit_button:
    if not nome_ciclo:
        st.warning("Preencha o nome do ciclo.")
    else:
        with st.spinner(f"Calculando '{nome_ciclo}' usando Banco Mestre..."):
            cycle_start_date = cycle_start_input
            cycle_end_date = (cycle_start_date + relativedelta(months=1)).replace(day=16)

            # --- MUDANÇA: Carrega Feriados do Banco Mestre ---
            conn = database.get_db_connection()
            # Pega feriados dentro do range, que estejam marcados para usar
            df_mestre = pd.read_sql_query(
                f"""SELECT data_iso, nome_feriado 
                    FROM feriados_anuais 
                    WHERE usar_na_escala = 1 
                    AND data_iso BETWEEN '{cycle_start_date}' AND '{cycle_end_date}'
                """, conn)
            # Cria um dicionario {data_obj: nome_feriado}
            mapa_feriados_custom = {}
            if not df_mestre.empty:
                for _, row in df_mestre.iterrows():
                    d_obj = datetime.strptime(row['data_iso'], '%Y-%m-%d').date()
                    mapa_feriados_custom[d_obj] = row['nome_feriado']

            conn.close()
            # -------------------------------------------------

            dias_para_salvar = []
            current_date = cycle_start_date
            dias_semana_map = {5: "Sab", 6: "Dom"}

            while current_date <= cycle_end_date:
                weekday = current_date.weekday()
                is_weekend = weekday in [5, 6]
                data_str = current_date.strftime('%d/%m')

                # 1. Verifica no Banco Mestre Primeiro (Prioridade Total)
                if current_date in mapa_feriados_custom:
                    nome_custom = mapa_feriados_custom[current_date]
                    # Formata bonitinho
                    nome_curto = (nome_custom[:20] + '...') if len(nome_custom) > 20 else nome_custom
                    col_name = f"{data_str}\n{nome_curto}"
                    dias_para_salvar.append((col_name, current_date.strftime('%Y-%m-%d')))

                # 2. Se não estiver no banco, verifica se é Fim de Semana
                elif is_weekend:
                    dia_str = dias_semana_map.get(weekday, "Dia")
                    col_name = f"{data_str}\n{dia_str}"
                    dias_para_salvar.append((col_name, current_date.strftime('%Y-%m-%d')))

                current_date += timedelta(days=1)

            try:
                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO ciclos (nome_ciclo, data_inicio, data_fim) VALUES (?, ?, ?)",
                               (nome_ciclo, cycle_start_date.strftime('%Y-%m-%d'), cycle_end_date.strftime('%Y-%m-%d')))
                id_ciclo_novo = cursor.lastrowid

                for nome_coluna, data_dia in dias_para_salvar:
                    # Inserimos com ativo=1 por padrao
                    cursor.execute(
                        "INSERT INTO ciclo_dias (id_ciclo, nome_coluna, data_dia, ativo) VALUES (?, ?, ?, 1)",
                        (id_ciclo_novo, nome_coluna, data_dia))

                conn.commit()
                st.success(
                    f"Ciclo '{nome_ciclo}' criado! {len(dias_para_salvar)} dias (baseado no Banco Mestre + Fins de Semana).")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Nome do ciclo já existe.")
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                conn.close()

# --- 2. Visualizar Ciclos ---
st.divider()
st.header("2. Ciclos Salvos")
try:
    conn = database.get_db_connection()
    df_ciclos = pd.read_sql_query("SELECT id, nome_ciclo, data_inicio, data_fim FROM ciclos ORDER BY data_inicio DESC",
                                  conn)
    conn.close()
    if df_ciclos.empty:
        st.info("Nenhum ciclo.")
    else:
        st.dataframe(df_ciclos, use_container_width=True, hide_index=True)
except:
    pass
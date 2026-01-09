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
        # Ajuste para garantir dia valido
        try:
            default_start_date = today.replace(day=15)
        except ValueError:
            # Caso hoje seja dia 31 e o mes seguinte nao tenha, etc (raro mas possivel)
            default_start_date = today.replace(day=1) 
            
        cycle_start_input = st.date_input("Selecione o dia 15 do mes de INICIO", value=default_start_date)
    with col2:
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
            
            # CORREÇÃO CRÍTICA PARA POSTGRES:
            # Mudamos "WHERE usar_na_escala = 1" para "WHERE usar_na_escala"
            # Isso funciona tanto para Boolean (Postgres) quanto Integer/Boolean (SQLite)
            query = f"""
                SELECT data_iso, nome_feriado 
                FROM feriados_anuais 
                WHERE usar_na_escala 
                AND data_iso BETWEEN '{cycle_start_date}' AND '{cycle_end_date}'
            """
            
            try:
                df_mestre = pd.read_sql_query(query, conn)
            except Exception as e:
                st.error(f"Erro na consulta SQL: {e}")
                df_mestre = pd.DataFrame()
            
            # Cria um dicionario {data_obj: nome_feriado}
            mapa_feriados_custom = {}
            if not df_mestre.empty:
                for _, row in df_mestre.iterrows():
                    # Pandas as vezes traz como string, as vezes como date, garantimos aqui
                    val_data = row['data_iso']
                    if isinstance(val_data, str):
                        d_obj = datetime.strptime(val_data, '%Y-%m-%d').date()
                    else:
                        d_obj = val_data # Já é date/timestamp
                        
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
                
                # Conversao segura para date python puro para comparar com o mapa
                curr_date_obj = current_date if isinstance(current_date, datetime) else current_date

                # 1. Verifica no Banco Mestre Primeiro (Prioridade Total)
                if curr_date_obj in mapa_feriados_custom:
                    nome_custom = mapa_feriados_custom[curr_date_obj]
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
                
                # CORREÇÃO: Usar database.run_query para inserções
                database.run_query(conn, 
                    "INSERT INTO ciclos (nome_ciclo, data_inicio, data_fim) VALUES (?, ?, ?)",
                    (nome_ciclo, cycle_start_date.strftime('%Y-%m-%d'), cycle_end_date.strftime('%Y-%m-%d'))
                )
                
                # Pega o ID gerado. 
                # No Postgres/Psycopg2 com run_query, precisamos recuperar de forma diferente ou fazer uma nova query.
                # O jeito mais seguro universalmente é consultar pelo nome unico
                df_id = pd.read_sql_query(f"SELECT id FROM ciclos WHERE nome_ciclo = '{nome_ciclo}'", conn)
                id_ciclo_novo = int(df_id.iloc[0]['id'])

                for nome_coluna, data_dia in dias_para_salvar:
                    # Inserimos com ativo=TRUE (Postgres exige True, nao 1)
                    database.run_query(conn,
                        "INSERT INTO ciclo_dias (id_ciclo, nome_coluna, data_dia, ativo) VALUES (?, ?, ?, TRUE)",
                        (id_ciclo_novo, nome_coluna, data_dia))

                conn.commit()
                st.success(
                    f"Ciclo '{nome_ciclo}' criado! {len(dias_para_salvar)} dias (baseado no Banco Mestre + Fins de Semana).")
                st.cache_data.clear() # Limpa cache para aparecer na lista abaixo
                st.rerun()
                
            except Exception as e:
                # Tratamento de erro generico, incluindo integridade (nome duplicado)
                if "unique" in str(e).lower():
                    st.error("Nome do ciclo já existe. Escolha outro nome.")
                else:
                    st.error(f"Erro ao salvar ciclo: {e}")
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

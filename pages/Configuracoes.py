import streamlit as st
import pandas as pd
import database
import utils
import holidays
import time 
from datetime import time as dt_time, datetime

st.set_page_config(page_title="Configurações", page_icon="⚙️")
st.title("Configurações do Sistema")

# --- Funcoes de Banco de Dados ---
def get_db_connection():
    return database.get_db_connection()

# --- Funcao: Carregar Regras ---
def carregar_regras_atualizadas():
    database.init_all_db_tables()
    conn = get_db_connection()
    regras = {}
    padrao = {
        "Sabado": {"Manha": 5, "Noite": 4, "Integral": 1},
        "Domingo": {"Manha": 4, "Noite": 3, "Integral": 1},
        "Feriado": {"Manha": 5, "Noite": 4, "Integral": 1}
    }
    try:
        df = pd.read_sql_query("SELECT dia_tipo, turno, quantidade FROM regras_staff", conn)
        if df.empty: return padrao
        for _, row in df.iterrows():
            if row['dia_tipo'] not in regras: regras[row['dia_tipo']] = {}
            regras[row['dia_tipo']][row['turno']] = row['quantidade']
        for dia, turnos in padrao.items():
            if dia not in regras: regras[dia] = turnos
            else:
                for turno, qtd in turnos.items():
                    if turno not in regras[dia]: regras[dia][turno] = qtd
        return regras
    except Exception as e:
        return padrao
    finally:
        conn.close()

# --- Funcoes de Salvamento ---
def save_staff_rules(regras):
    conn = database.get_db_connection()
    try:
        for dia, turnos in regras.items():
            for turno, qtd in turnos.items():
                database.run_query(conn, """
                    INSERT INTO regras_staff (dia_tipo, turno, quantidade)
                    VALUES (?, ?, ?) 
                    ON CONFLICT(dia_tipo, turno) 
                    DO UPDATE SET quantidade = excluded.quantidade
                """, (dia, turno, qtd))
        conn.commit()
        st.toast("Regras de Staff salvas com sucesso!", icon="✅")
        time.sleep(0.5) 
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
    finally:
        conn.close()

def save_shift_hours(horas):
    conn = database.get_db_connection()
    try:
        for turno, qtd in horas.items():
            database.run_query(conn, """
                INSERT INTO configuracao_turnos (turno, horas) VALUES (?, ?) 
                ON CONFLICT(turno) DO UPDATE SET horas = excluded.horas
            """, (turno, qtd))
        conn.commit()
        st.toast("Carga horária atualizada!", icon="⏰")
        time.sleep(0.5)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar horas: {e}")
        return False
    finally:
        conn.close()

def save_limits(limite):
    conn = database.get_db_connection()
    try:
        database.run_query(conn, """
            INSERT INTO configuracao_limites (chave, valor) VALUES ('max_horas_ciclo', ?) 
            ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor
        """, (limite,))
        conn.commit()
        st.toast(f"Limite de horas salvo: {limite}h", icon="🛡️")
        time.sleep(0.5)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar limite: {e}")
        return False
    finally:
        conn.close()

def delete_all_data():
    conn = database.get_db_connection()
    try:
        # Ordem importante para não quebrar Constraints (Foreign Keys)
        # Apagamos primeiro quem depende (filhos), depois os pais
        tables = [
            "indisponibilidades", 
            "escala_salva", 
            "ciclo_dias", 
            "sobreaviso", 
            "regras_staff",
            "configuracao_turnos", 
            "configuracao_limites", 
            "analistas", 
            "ciclos", 
            "feriados_anuais"
        ]
        
        # CORREÇÃO CRÍTICA: Não tentar apagar sqlite_sequence no Postgres
        # Se tentar, a transação aborta e nada é apagado.
        is_postgres = "POSTGRES_URL" in st.secrets
        if not is_postgres:
            tables.append("sqlite_sequence")

        for t in tables: 
            try:
                database.run_query(conn, f"DELETE FROM {t}")
            except Exception as e:
                # Se der erro, printa no log do servidor mas segue o baile
                print(f"Aviso ao limpar {t}: {e}")
            
        conn.commit()
        st.balloons() 
        st.success("Banco de dados resetado com sucesso!")
        st.cache_data.clear()
        time.sleep(2)
    except Exception as e:
        st.error(f"Erro crítico ao resetar: {e}")
        # Tenta rollback se der erro grave
        try: conn.rollback()
        except: pass
    finally:
        conn.close()

# Auxiliares de tempo
def decimal_to_time(val):
    if pd.isna(val): return dt_time(0, 0)
    h = int(val); m = int(round((val - h) * 60))
    if m == 60: h += 1; m = 0
    return dt_time(h % 24, m)
def time_to_decimal(t): return t.hour + t.minute / 60.0


# ==============================================================================
# 1. REGRAS DE STAFF
# ==============================================================================
st.header("1. Regras de Staff (Quantidade de Pessoas)")
st.info("Defina quantos analistas são necessários em cada turno.")

regras_atuais = carregar_regras_atualizadas()

with st.form("form_regras_staff"):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Sábado")
        s_m = st.number_input("Manhã", min_value=0, value=int(regras_atuais["Sabado"]["Manha"]), key="sm")
        s_n = st.number_input("Noite", min_value=0, value=int(regras_atuais["Sabado"]["Noite"]), key="sn")
        s_i = st.number_input("Integral", min_value=0, value=int(regras_atuais["Sabado"]["Integral"]), key="si")
    with col2:
        st.subheader("Domingo")
        d_m = st.number_input("Manhã", min_value=0, value=int(regras_atuais["Domingo"]["Manha"]), key="dm")
        d_n = st.number_input("Noite", min_value=0, value=int(regras_atuais["Domingo"]["Noite"]), key="dn")
        d_i = st.number_input("Integral", min_value=0, value=int(regras_atuais["Domingo"]["Integral"]), key="di")
    with col3:
        st.subheader("Feriado")
        f_m = st.number_input("Manhã", min_value=0, value=int(regras_atuais["Feriado"]["Manha"]), key="fm")
        f_n = st.number_input("Noite", min_value=0, value=int(regras_atuais["Feriado"]["Noite"]), key="fn")
        f_i = st.number_input("Integral", min_value=0, value=int(regras_atuais["Feriado"]["Integral"]), key="fi")

    if st.form_submit_button("💾 Salvar Regras de Staff", type="primary"):
        novas_regras = {
            "Sabado": {"Manha": s_m, "Noite": s_n, "Integral": s_i},
            "Domingo": {"Manha": d_m, "Noite": d_n, "Integral": d_i},
            "Feriado": {"Manha": f_m, "Noite": f_n, "Integral": f_i}
        }
        if save_staff_rules(novas_regras):
            st.rerun()

# ==============================================================================
# 2. CARGA HORÁRIA
# ==============================================================================
st.divider()
st.header("2. Carga Horária (Turnos)")
h_atuais = utils.load_shift_hours_from_db()

with st.form("form_horas"):
    c1, c2, c3 = st.columns(3)
    with c1: hm = st.time_input("Manhã", value=decimal_to_time(h_atuais.get("Manha", 5.5)), step=1800)
    with c2: hn = st.time_input("Noite", value=decimal_to_time(h_atuais.get("Noite", 5.0)), step=1800)
    with c3: hi = st.time_input("Integral", value=decimal_to_time(h_atuais.get("Integral", 10.0)), step=1800)

    if st.form_submit_button("Salvar Horas"):
        if save_shift_hours({"Manha": time_to_decimal(hm), "Noite": time_to_decimal(hn), "Integral": time_to_decimal(hi)}):
            st.rerun()

# ==============================================================================
# 3. LIMITES
# ==============================================================================
st.divider()
st.header("3. Limite de Horas (Ciclo)")
lim = utils.load_max_hours_limit()

with st.form("form_lim"):
    c1, c2 = st.columns(2)
    lh = st.number_input("Horas", 0, 300, int(lim))
    lm = st.selectbox("Minutos", [0, 15, 30, 45], index=0)

    if st.form_submit_button("Salvar Limite"):
        if save_limits(lh + lm / 60.0):
            st.rerun()

# ==============================================================================
# 4. BANCO MESTRE DE FERIADOS
# ==============================================================================
st.divider()
st.header("4. Banco de Feriados (Template)")

with st.expander("🛠️ Gerar Feriados Automaticamente", expanded=False):
    col_ano, col_est, col_btn = st.columns([1, 2, 1])
    with col_ano:
        ano_geracao = st.number_input("Ano", min_value=2024, max_value=2030, value=datetime.now().year + 1)
    with col_est:
        states = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE",
                  "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
        estados_sel = st.multiselect("Estados", states, default=['PR', 'SP'])
    with col_btn:
        st.write("")
        st.write("")
        if st.button("Gerar e Salvar", type="primary"):
            br_holidays = holidays.BR(years=ano_geracao)
            for state in estados_sel:
                br_holidays += holidays.BR(state=state, years=ano_geracao)
            conn = database.get_db_connection()
            count_new = 0
            for date, name in br_holidays.items():
                try:
                    database.run_query(conn, 
                        "INSERT INTO feriados_anuais (data_iso, nome_feriado, usar_na_escala) VALUES (?, ?, TRUE) ON CONFLICT(data_iso) DO NOTHING",
                        (date.strftime('%Y-%m-%d'), name))
                    count_new += 1
                except: pass
            conn.commit()
            conn.close()
            st.toast(f"{count_new} novos feriados adicionados!", icon="📅")
            time.sleep(1)
            st.rerun()

# --- Editor ---
conn = database.get_db_connection()
try:
    df_feriados = pd.read_sql_query("SELECT * FROM feriados_anuais ORDER BY data_iso", conn)
    if not df_feriados.empty:
        df_feriados['data_iso'] = pd.to_datetime(df_feriados['data_iso'])
        anos_dispo = sorted(df_feriados['data_iso'].dt.year.unique())

        st.write("---")
        ano_view = st.selectbox("Filtrar por Ano:", ["Todos"] + anos_dispo, index=len(anos_dispo))
        df_view = df_feriados[df_feriados['data_iso'].dt.year == ano_view].copy() if ano_view != "Todos" else df_feriados.copy()
        df_view['usar_na_escala'] = df_view['usar_na_escala'].apply(lambda x: True if x else False)

        df_editado = st.data_editor(
            df_view,
            column_config={
                "id": None,
                "data_iso": st.column_config.DateColumn("Data", disabled=True, format="DD/MM/YYYY"),
                "nome_feriado": st.column_config.TextColumn("Nome"),
                "usar_na_escala": st.column_config.CheckboxColumn("Ativo?")
            },
            hide_index=True,
            use_container_width=True,
            key="editor_master_feriados"
        )

        if st.button("💾 Salvar Alterações nos Feriados"):
            conn_save = database.get_db_connection()
            try:
                for i, row in df_editado.iterrows():
                    database.run_query(conn_save, 
                        "UPDATE feriados_anuais SET nome_feriado = ?, usar_na_escala = ? WHERE id = ?",
                        (row['nome_feriado'], bool(row['usar_na_escala']), row['id']))
                conn_save.commit()
                st.toast("Feriados atualizados com sucesso!", icon="✨")
                time.sleep(1)
                st.rerun()
            finally:
                conn_save.close()
    else:
        st.info("Nenhum feriado cadastrado.")
except Exception as e:
    st.error(f"Erro ao carregar feriados: {e}")
finally:
    conn.close()

# ==============================================================================
# 5. AJUSTE FINO (CICLOS CRIADOS)
# ==============================================================================
st.divider()
st.header("5. Ajuste Fino (Ciclo Atual)")
conn = database.get_db_connection()
try:
    df_ciclos = pd.read_sql_query("SELECT id, nome_ciclo FROM ciclos ORDER BY data_inicio DESC", conn)
    if not df_ciclos.empty:
        ciclos_dict = dict(zip(df_ciclos['id'], df_ciclos['nome_ciclo']))
        id_ciclo_edit = st.selectbox("Selecione o Ciclo:", options=ciclos_dict.keys(), format_func=lambda x: ciclos_dict[x])

        df_dias = pd.read_sql_query(f"SELECT id, nome_coluna, data_dia, ativo FROM ciclo_dias WHERE id_ciclo = {id_ciclo_edit} ORDER BY data_dia ASC", conn)
        if not df_dias.empty:
            df_dias['ativo'] = df_dias['ativo'].apply(lambda x: True if x else False)
            df_editado_ciclo = st.data_editor(df_dias, column_config={"ativo": st.column_config.CheckboxColumn("Ativo?"), "id": None, "nome_coluna": "Nome", "data_dia": st.column_config.DateColumn("Data", disabled=True)}, hide_index=True, use_container_width=True)

            if st.button("💾 Atualizar Ciclo Atual"):
                conn_save = database.get_db_connection()
                try:
                    for i, row in df_editado_ciclo.iterrows():
                        database.run_query(conn_save, 
                            "UPDATE ciclo_dias SET nome_coluna = ?, ativo = ? WHERE id = ?", 
                            (row['nome_coluna'], bool(row['ativo']), row['id']))
                    conn_save.commit()
                    st.toast("Ciclo atualizado!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                finally:
                    conn_save.close()
except: pass
finally: conn.close()

# ==============================================================================
# 6. ZONA DE PERIGO
# ==============================================================================
st.divider()
st.header("6. Zona de Perigo")
c = st.checkbox("Confirmar exclusão total")
if st.button("RESETAR TUDO", type="primary", disabled=not c):
    if c: delete_all_data(); st.rerun()

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import database
import re
import unicodedata
import pytz

st.title("Registrar Indisponibilidade (Folgas)")

# --- Funcoes Auxiliares ---
def get_br_time():
    try:
        tz = pytz.timezone('America/Sao_Paulo')
        return datetime.now(tz)
    except:
        return datetime.utcnow() - timedelta(hours=3)

def normalizar_chave(texto):
    if not isinstance(texto, str): return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return texto_sem_acento.lower().strip()

def carregar_analistas_ativos():
    database.init_all_db_tables()
    conn = database.get_db_connection()
    try:
        # PostgreSQL exige TRUE, SQLite aceita 1. O Pandas lida bem com isso na leitura.
        # Mas para garantir, usamos a query compatível.
        # Se for SQLite, ativo=1. Se for Postgres, ativo=TRUE. 
        # O jeito mais seguro é ler tudo e filtrar no pandas ou confiar que o driver ajusta.
        # Vamos ler tudo e filtrar no python para garantir 100%
        df = pd.read_sql_query("SELECT id, nome, ativo FROM analistas ORDER BY nome", conn)
        
        # Filtro agnóstico (funciona se for 1 ou True)
        df_ativos = df[df['ativo'].apply(lambda x: True if x == 1 or x == True else False)]
        
        return dict(zip(df_ativos['id'], df_ativos['nome']))
    except:
        return {}
    finally:
        conn.close()

def get_analista_email_map():
    database.init_all_db_tables()
    conn = database.get_db_connection()
    try:
        analistas_df = pd.read_sql_query("SELECT id, email FROM analistas", conn)
        return {str(email).lower().strip(): id_ for email, id_ in zip(analistas_df['email'], analistas_df['id']) if email}
    except:
        return {}
    finally:
        conn.close()

# --- 1. Manual ---
analistas_dict_manual = carregar_analistas_ativos()
with st.expander("Cadastrar Manualmente"):
    if not analistas_dict_manual:
        st.error("Nenhum analista ativo encontrado.")
    else:
        with st.form("form_indisponibilidade", clear_on_submit=True):
            analista_id = st.selectbox("Analista", options=analistas_dict_manual.keys(), format_func=lambda x: analistas_dict_manual[x])
            data_indisponivel = st.date_input("Data", value=datetime.today())
            
            if st.form_submit_button("Salvar"):
                conn = database.get_db_connection()
                try:
                    ts_agora = get_br_time().strftime('%Y-%m-%d %H:%M:%S')
                    # CORREÇÃO: Usar run_query
                    database.run_query(conn, """
                        INSERT INTO indisponibilidades (id_analista, data, data_importacao) 
                        VALUES (?, ?, ?) 
                        ON CONFLICT(id_analista, data) DO NOTHING
                    """, (analista_id, data_indisponivel.strftime('%Y-%m-%d'), ts_agora))
                    
                    conn.commit()
                    st.success("Salvo!")
                except Exception as e:
                    st.error(f"Erro: {e}")
                finally:
                    conn.close()

# --- 2. Importar Arquivo ---
st.divider()
st.header("Importar Indisponibilidade")
st.info("Suporta CSV (Google Forms) e Excel (.xlsx).")

uploaded_file = st.file_uploader("Escolha o arquivo", type=["csv", "xlsx"], key="file_indisp")

if 'df_preview_indisp' not in st.session_state:
    st.session_state.df_preview_indisp = None

if uploaded_file is not None:
    with st.spinner("Lendo e validando arquivo..."):
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=None, engine='python')
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=';')

            st.session_state.df_preview_indisp = df
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            st.session_state.df_preview_indisp = None

    if st.session_state.df_preview_indisp is not None:
        st.success("Arquivo lido com sucesso! Confira uma prévia abaixo:")
        st.dataframe(st.session_state.df_preview_indisp.head(3), use_container_width=True)
        st.caption("Se os dados acima parecerem corretos, clique no botão abaixo para processar.")

        if st.button("Confirmar e Importar Dados", type="primary"):
            df = st.session_state.df_preview_indisp
            mapa_email_id = get_analista_email_map()

            if not mapa_email_id:
                st.error("Nenhum analista com email cadastrado no sistema.")
            else:
                conn = database.get_db_connection()
                try:
                    # Identifica colunas
                    col_email = None
                    col_folgas = None
                    col_ferias_ini = None
                    col_ferias_dias = None
                    col_pref_dia = None
                    col_pref_turno = None

                    for col in df.columns:
                        c_norm = normalizar_chave(str(col))
                        if "e-mail" in c_norm or "email" in c_norm: col_email = col
                        if "nao pode trabalhar" in c_norm: col_folgas = col
                        if "ferias agendada" in c_norm: col_ferias_ini = col
                        if "quantos dias" in c_norm: col_ferias_dias = col
                        if "preferencia" in c_norm and "dia" in c_norm: col_pref_dia = col
                        if "deseja fazer turnos" in c_norm: col_pref_turno = col

                    if not col_email:
                        st.error("Coluna de Email não encontrada.")
                    else:
                        logs = []
                        total_salvos = 0
                        ts_agora = get_br_time().strftime('%Y-%m-%d %H:%M:%S')

                        progress_bar = st.progress(0)
                        total_rows = len(df)

                        for index, row in df.iterrows():
                            progress_bar.progress((index + 1) / total_rows)

                            email_raw = str(row[col_email]).strip().lower()
                            id_analista = mapa_email_id.get(email_raw)

                            log = {"Email": email_raw, "Analista": "OK" if id_analista else "N/A", "Detalhes": ""}

                            if not id_analista:
                                logs.append(log)
                                continue

                            # A. Preferencias (Aqui estava o erro!)
                            if col_pref_turno and pd.notna(row[col_pref_turno]):
                                val = str(row[col_pref_turno]).lower()
                                p = "Tanto faz"
                                if "10" in val or "integral" in val: p = "Integral"
                                elif "5" in val: p = "Curto"
                                
                                # CORREÇÃO: Usar run_query
                                database.run_query(conn, "UPDATE analistas SET pref_turno = ? WHERE id = ?", (p, id_analista))

                            if col_pref_dia and pd.notna(row[col_pref_dia]):
                                val = str(row[col_pref_dia]).lower()
                                p = "Tanto faz"
                                if "sabado" in val or "sábado" in val: p = "Sabado"
                                elif "domingo" in val: p = "Domingo"
                                
                                # CORREÇÃO: Usar run_query
                                database.run_query(conn, "UPDATE analistas SET pref_dia = ? WHERE id = ?", (p, id_analista))

                            datas_para_salvar = set()

                            # B. Folgas
                            if col_folgas and pd.notna(row[col_folgas]):
                                raw_text = str(row[col_folgas])
                                matches = re.findall(r'(\d{1,2})[/-](\d{1,2})', raw_text)
                                for d, m in matches:
                                    try:
                                        dia, mes = int(d), int(m)
                                        if 1 <= mes <= 12 and 1 <= dia <= 31:
                                            ano = datetime.now().year
                                            # Se for Dezembro e a folga for Jan, assume proximo ano
                                            if datetime.now().month == 12 and mes == 1: ano += 1
                                            datas_para_salvar.add(datetime(ano, mes, dia).strftime('%Y-%m-%d'))
                                    except: pass

                            # C. Ferias
                            if col_ferias_ini and col_ferias_dias and pd.notna(row[col_ferias_ini]) and pd.notna(row[col_ferias_dias]):
                                try:
                                    val_ini = row[col_ferias_ini]
                                    dt_ini = None
                                    if isinstance(val_ini, datetime):
                                        dt_ini = val_ini
                                    else:
                                        str_val = str(val_ini).strip()
                                        if re.search(r'\d', str_val):
                                            # Tenta varios formatos
                                            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                                                try: dt_ini = datetime.strptime(str_val, fmt); break
                                                except: pass

                                    if dt_ini:
                                        dur_match = re.search(r'\d+', str(row[col_ferias_dias]))
                                        if dur_match:
                                            duracao = int(dur_match.group(0))
                                            for i in range(duracao):
                                                dt_f = dt_ini + timedelta(days=i)
                                                datas_para_salvar.add(dt_f.strftime('%Y-%m-%d'))
                                except: pass

                            count_linha = 0
                            for dt_str in datas_para_salvar:
                                # CORREÇÃO: Usar run_query
                                database.run_query(conn, """
                                    INSERT INTO indisponibilidades (id_analista, data, data_importacao) 
                                    VALUES (?, ?, ?) 
                                    ON CONFLICT(id_analista, data) DO NOTHING
                                """, (id_analista, dt_str, ts_agora))
                                count_linha += 1 # No Postgres, rowcount as vezes é impreciso em batch, mas ok aqui

                            if count_linha > 0:
                                total_salvos += count_linha
                                log["Detalhes"] = f"+{count_linha} datas."

                            logs.append(log)

                        conn.commit()
                        st.success(f"Concluido! Registros processados.")
                        st.dataframe(pd.DataFrame(logs))
                
                except Exception as e:
                    st.error(f"Erro no processamento: {e}")
                finally:
                    conn.close()

# --- 3. Visualizar ---
st.divider()
st.header("Banco de Dados")
if st.button("Limpar registros antigos (Manter apenas os mais recentes)"):
    conn = database.get_db_connection()
    try:
        # Query complexa que deleta duplicados mantendo o ultimo import
        # Simplificação: Apagar tudo antigo
        # CORREÇÃO: Usar run_query
        database.run_query(conn, "DELETE FROM indisponibilidades WHERE id NOT IN (SELECT MAX(id) FROM indisponibilidades GROUP BY id_analista, data)")
        conn.commit()
        st.success("Limpeza realizada.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao limpar: {e}")
    finally:
        conn.close()

try:
    conn = database.get_db_connection()
    # Postgres usa TO_CHAR, SQLite usa strftime. Pandas read_sql nao resolve isso.
    # Vamos trazer a data bruta e formatar no Pandas
    query = """
            SELECT a.nome AS Analista, \
                   i.data as Data_Folga, 
                   i.data_importacao
            FROM indisponibilidades i \
                     JOIN analistas a ON i.id_analista = a.id \
            ORDER BY i.data_importacao DESC, a.nome \
            """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        # Formata datas no Python para evitar briga SQL
        df['Data_Folga'] = pd.to_datetime(df['Data_Folga']).dt.strftime('%d/%m/%Y')
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Banco vazio.")
except:
    pass

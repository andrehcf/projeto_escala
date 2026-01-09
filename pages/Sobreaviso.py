import streamlit as st
import pandas as pd
import database
from datetime import datetime
import time # Para alertas visuais

st.set_page_config(page_title="Sobreaviso", page_icon="⚠️")

st.title("Gerenciar Sobreaviso")
st.markdown("""
Cadastre quem estará de sobreaviso.  
**Nota:** Esta tela é independente do cadastro de analistas. Os nomes digitados/importados aqui aparecerão exatamente como escritos na escala.
""")

# --- Inicializa DB ---
database.init_all_db_tables()

# ==============================================================================
# 1. CADASTRO MANUAL
# ==============================================================================
with st.expander("📝 Cadastrar Manualmente", expanded=True):
    with st.form("form_sobreaviso", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            nome_input = st.text_input("Nome do Responsável*", 
                                     placeholder="Ex: João Silva", 
                                     help="Digite o nome como deve aparecer na escala.")
        
        with col2:
            c_in, c_fim = st.columns(2)
            with c_in:
                data_inicio = st.date_input("Data Início", value=datetime.today())
            with c_fim:
                data_fim = st.date_input("Data Fim", value=datetime.today())

        submitted = st.form_submit_button("Salvar Sobreaviso")

        if submitted:
            if not nome_input:
                st.warning("Por favor, digite um nome.")
            elif data_fim < data_inicio:
                st.error("A data final não pode ser anterior à data inicial.")
            else:
                conn = database.get_db_connection()
                try:
                    # CORREÇÃO: Usar run_query
                    database.run_query(conn, """
                        INSERT INTO sobreaviso (nome_analista, data_inicio, data_fim) 
                        VALUES (?, ?, ?)
                    """, (nome_input.strip(), data_inicio, data_fim))
                    
                    conn.commit()
                    st.toast(f"Sobreaviso de '{nome_input}' salvo!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
                finally:
                    conn.close()

# ==============================================================================
# 2. IMPORTAÇÃO VIA ARQUIVO (Excel/CSV)
# ==============================================================================
st.divider()
st.subheader("📂 Importar em Massa")
st.info("O arquivo deve conter as colunas: **'Nome'**, **'Inicio'** e **'Fim'**.")

uploaded_file = st.file_uploader("Arraste seu arquivo Excel ou CSV", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        df_import = None
        # --- Tratamento de CSV ---
        if uploaded_file.name.endswith('.csv'):
            try:
                df_import = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df_import = pd.read_csv(uploaded_file, encoding='latin1', sep=None, engine='python')
        else:
            df_import = pd.read_excel(uploaded_file)
        
        if df_import is not None:
            # Normaliza colunas
            df_import.columns = df_import.columns.str.strip().str.lower()
            
            col_nome = next((c for c in df_import.columns if 'nome' in c or 'analista' in c), None)
            col_inicio = next((c for c in df_import.columns if 'inicio' in c or 'start' in c), None)
            col_fim = next((c for c in df_import.columns if 'fim' in c or 'end' in c), None)

            if not col_nome or not col_inicio or not col_fim:
                st.error(f"Colunas obrigatórias não identificadas. Encontrado: {list(df_import.columns)}")
            else:
                st.write("Prévia dos dados:")
                st.dataframe(df_import[[col_nome, col_inicio, col_fim]].head())

                if st.button("Confirmar Importação", type="primary"):
                    conn = database.get_db_connection()
                    count = 0
                    try:
                        for _, row in df_import.iterrows():
                            nome = str(row[col_nome]).strip()
                            try:
                                # Tenta converter datas flexíveis
                                dt_ini = pd.to_datetime(row[col_inicio], dayfirst=True).date()
                                dt_fim = pd.to_datetime(row[col_fim], dayfirst=True).date()
                                
                                if nome and str(nome).lower() != 'nan':
                                    # CORREÇÃO: Usar run_query
                                    database.run_query(conn, """
                                        INSERT INTO sobreaviso (nome_analista, data_inicio, data_fim) 
                                        VALUES (?, ?, ?)
                                    """, (nome, dt_ini, dt_fim))
                                    count += 1
                            except:
                                continue

                        conn.commit()
                        st.toast(f"{count} registros importados!", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro na importação: {e}")
                    finally:
                        conn.close()

    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")

# ==============================================================================
# 3. LISTA DE REGISTROS ATIVOS
# ==============================================================================
st.divider()
st.subheader("📋 Registros Ativos")

conn = database.get_db_connection()
try:
    # Leitura (SELECT) continua normal com pandas
    df_sobreaviso = pd.read_sql_query("""
        SELECT id, nome_analista, data_inicio, data_fim 
        FROM sobreaviso 
        ORDER BY data_inicio DESC
    """, conn)
    
    if df_sobreaviso.empty:
        st.info("Nenhum registro encontrado.")
    else:
        st.dataframe(
            df_sobreaviso, 
            column_config={
                "id": None,
                "nome_analista": "Nome",
                "data_inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
                "data_fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY")
            },
            hide_index=True,
            use_container_width=True
        )

        with st.expander("🗑️ Excluir Registro"):
            lista_opcoes = df_sobreaviso.apply(
                lambda x: f"{x['id']} - {x['nome_analista']} ({pd.to_datetime(x['data_inicio']).strftime('%d/%m')} até {pd.to_datetime(x['data_fim']).strftime('%d/%m')})", 
                axis=1
            )
            selecionado = st.selectbox("Selecione para excluir:", options=lista_opcoes)
            
            if st.button("Apagar Selecionado", type="secondary"):
                id_del = selecionado.split(" - ")[0]
                conn = database.get_db_connection() # Reabre conexão limpa
                try:
                    # CORREÇÃO: Usar run_query
                    database.run_query(conn, "DELETE FROM sobreaviso WHERE id = ?", (id_del,))
                    conn.commit()
                    st.toast("Registro apagado.", icon="🗑️")
                    time.sleep(1)
                    st.rerun()
                finally:
                    conn.close()

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
finally:
    if conn: conn.close()

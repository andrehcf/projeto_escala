import streamlit as st
import pandas as pd
import database
from datetime import datetime

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
            # Texto livre para garantir independência
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
                    conn.execute("""
                                 INSERT INTO sobreaviso (nome_analista, data_inicio, data_fim)
                                 VALUES (?, ?, ?)
                                 """, (nome_input.strip(), data_inicio, data_fim))
                    conn.commit()
                    st.success(f"Sobreaviso de '{nome_input}' salvo!")
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
        # --- CORREÇÃO: Tratamento robusto de CSV ---
        if uploaded_file.name.endswith('.csv'):
            try:
                # Tenta ler padrão UTF-8 (Padrão Web/Linux)
                df_import = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                # Se falhar, tenta Latin-1 (Padrão Excel/Brasil)
                uploaded_file.seek(0)  # Reseta o ponteiro do arquivo
                # sep=None e engine='python' detecta se é virgula ou ponto-e-virgula
                df_import = pd.read_csv(uploaded_file, encoding='latin1', sep=None, engine='python')
        else:
            df_import = pd.read_excel(uploaded_file)
        # -------------------------------------------

        if df_import is not None:
            # Normaliza colunas para evitar erros de caixa alta/baixa
            df_import.columns = df_import.columns.str.strip().str.lower()

            # Mapeia as colunas esperadas
            col_nome = next((c for c in df_import.columns if 'nome' in c or 'analista' in c), None)
            col_inicio = next((c for c in df_import.columns if 'inicio' in c or 'start' in c), None)
            col_fim = next((c for c in df_import.columns if 'fim' in c or 'end' in c), None)

            if not col_nome or not col_inicio or not col_fim:
                st.error(
                    f"Não foi possível identificar as colunas. O arquivo deve ter: Nome, Inicio, Fim. (Encontrado: {list(df_import.columns)})")
            else:
                st.write("Prévia dos dados identificados:")
                st.dataframe(df_import[[col_nome, col_inicio, col_fim]].head())

                if st.button("Confirmar Importação", type="primary"):
                    conn = database.get_db_connection()
                    count = 0
                    try:
                        for _, row in df_import.iterrows():
                            nome = str(row[col_nome]).strip()
                            # Tenta converter datas
                            try:
                                dt_ini = pd.to_datetime(row[col_inicio], dayfirst=True).date()
                                dt_fim = pd.to_datetime(row[col_fim], dayfirst=True).date()

                                if nome and str(nome).lower() != 'nan':
                                    conn.execute("""
                                                 INSERT INTO sobreaviso (nome_analista, data_inicio, data_fim)
                                                 VALUES (?, ?, ?)
                                                 """, (nome, dt_ini, dt_fim))
                                    count += 1
                            except Exception as e_date:
                                st.warning(f"Erro na linha de '{nome}': Data inválida ({e_date})")
                                continue

                        conn.commit()
                        st.success(f"{count} registros importados com sucesso!")
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
    df_sobreaviso = pd.read_sql_query("""
                                      SELECT id, nome_analista, data_inicio, data_fim
                                      FROM sobreaviso
                                      ORDER BY data_inicio DESC
                                      """, conn)

    if df_sobreaviso.empty:
        st.info("Nenhum registro encontrado.")
    else:
        # Tabela Visual
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

        # Botão de Excluir
        with st.expander("🗑️ Excluir Registro"):
            lista_opcoes = df_sobreaviso.apply(
                lambda
                    x: f"{x['id']} - {x['nome_analista']} ({pd.to_datetime(x['data_inicio']).strftime('%d/%m')} até {pd.to_datetime(x['data_fim']).strftime('%d/%m')})",
                axis=1
            )
            selecionado = st.selectbox("Selecione para excluir:", options=lista_opcoes)

            if st.button("Apagar Selecionado", type="secondary"):
                id_del = selecionado.split(" - ")[0]
                conn.execute("DELETE FROM sobreaviso WHERE id = ?", (id_del,))
                conn.commit()
                st.success("Registro apagado.")
                st.rerun()

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
finally:
    conn.close()
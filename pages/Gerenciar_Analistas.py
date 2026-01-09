import streamlit as st
import pandas as pd
from datetime import datetime
import database

st.title("Gerenciar Analistas")

def carregar_analistas():
    database.init_all_db_tables()
    conn = database.get_db_connection()
    try:
        query = "SELECT id, nome, email, nivel, data_admissao, ativo, skill_cplug, skill_dd FROM analistas ORDER BY nome"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar analistas: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# --- 1. Cadastro Manual ---
with st.expander("Cadastrar Manualmente"):
    with st.form(key="novo_analista", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome Completo*", help="Obrigatorio")
            email = st.text_input("Email*", help="Obrigatorio")
        with c2:
            nivel = st.selectbox("Nivel*", ["Junior", "Pleno", "Senior", "Especialista"])
            data_adm = st.date_input("Admissão*", value=datetime.today())

        st.caption("Skills")
        sk1, sk2 = st.columns(2)
        with sk1: s_cp = st.checkbox("Cplug")
        with sk2: s_dd = st.checkbox("DD")

        if st.form_submit_button("Salvar"):
            if not nome or not email:
                st.warning("Preencha Nome e Email.")
            else:
                conn = database.get_db_connection()
                try:
                    # CORREÇÃO: Passar bool(var) em vez de 1/0
                    # O Postgres exige True/False, não 1/0
                    database.run_query(conn, """
                        INSERT INTO analistas (nome, email, nivel, data_admissao, ativo, skill_cplug, skill_dd)
                        VALUES (?, ?, ?, ?, TRUE, ?, ?) 
                        ON CONFLICT(email) DO UPDATE SET nome=excluded.nome, nivel=excluded.nivel
                    """, (nome.strip(), email.strip().lower(), nivel, data_adm.strftime('%Y-%m-%d'),
                          bool(s_cp), bool(s_dd))) # <--- AQUI MUDOU DE '1 if ...' PARA 'bool(...)'
                    
                    conn.commit()
                    st.success(f"Analista {nome} salvo!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
                finally:
                    conn.close()

# --- 2. Importar CSV ---
st.divider()
st.header("Importar Analistas via CSV")
st.info("Colunas esperadas: 'Analista', 'Email', 'Nivel'.")

uploaded_file = st.file_uploader("Escolha o CSV", type=["csv", "xlsx"], key="csv_analistas")

if 'df_preview_analistas' not in st.session_state:
    st.session_state.df_preview_analistas = None

if uploaded_file is not None:
    with st.spinner("Lendo arquivo..."):
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                try:
                    df = pd.read_csv(uploaded_file, sep=None, engine='python')
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=';')
            
            df.columns = df.columns.str.strip().str.lower()
            st.session_state.df_preview_analistas = df
        except Exception as e:
            st.error(f"Erro ao ler: {e}")
            st.session_state.df_preview_analistas = None

    if st.session_state.df_preview_analistas is not None:
        st.success("Arquivo lido! Confira a prévia:")
        st.dataframe(st.session_state.df_preview_analistas.head(3))

        if st.button("Confirmar Importação", type="primary"):
            df = st.session_state.df_preview_analistas
            
            rename_map = {}
            for c in df.columns:
                if "analista" in c or "nome" in c: rename_map[c] = "nome"
                elif "email" in c: rename_map[c] = "email"
                elif "nivel" in c or "nível" in c: rename_map[c] = "nivel"
            
            df = df.rename(columns=rename_map)

            colunas_obrigatorias = ["nome", "email"]
            faltantes = [c for c in colunas_obrigatorias if c not in df.columns]

            if faltantes:
                st.error(f"Colunas obrigatórias não encontradas: {faltantes}")
            else:
                conn = database.get_db_connection()
                count = 0
                erros_log = []
                prog_bar = st.progress(0)
                total = len(df)
                
                for idx, row in df.iterrows():
                    prog_bar.progress((idx + 1) / total)
                    try:
                        nm = str(row['nome']).strip()
                        em = str(row['email']).strip().lower()
                        nv = str(row['nivel']).strip().capitalize() if 'nivel' in df.columns else "Junior"
                        
                        if not nm or not em or em == 'nan': continue

                        # Skills - CORREÇÃO PARA BOOLEAN
                        s_cp = False # Inicia como False
                        s_dd = False # Inicia como False
                        for c in df.columns:
                            val_str = str(row[c]).lower()
                            if "cplug" in c and val_str in ['1', 'sim', 'true', 's']: s_cp = True
                            if "dd" in c and val_str in ['1', 'sim', 'true', 's']: s_dd = True

                        database.run_query(conn, """
                            INSERT INTO analistas (nome, email, nivel, data_admissao, ativo, skill_cplug, skill_dd)
                            VALUES (?, ?, ?, ?, TRUE, ?, ?) 
                            ON CONFLICT(email) DO UPDATE SET nome=excluded.nome, nivel=excluded.nivel
                        """, (nm, em, nv, datetime.now().strftime('%Y-%m-%d'), s_cp, s_dd)) # Passando True/False direto
                        
                        count += 1
                    except Exception as e:
                        erros_log.append(f"Linha {idx}: {e}")
                
                conn.commit()
                conn.close()
                
                if count > 0:
                    st.toast(f"{count} analistas importados!", icon="✅")
                    st.success(f"Sucesso! {count} registros importados.")
                else:
                    st.warning("Nenhum registro importado.")
                
                if erros_log:
                    with st.expander("Ver erros"): st.write(erros_log)
                        
                st.cache_data.clear()
                import time
                time.sleep(2)
                st.rerun()

# --- 3. Lista de Analistas ---
st.divider()
st.header("Equipe Cadastrada")
try:
    df_analistas = carregar_analistas()
    if df_analistas.empty:
        st.info("Nenhum analista cadastrado.")
    else:
        df_editada = st.data_editor(
            df_analistas,
            use_container_width=True,
            hide_index=True,
            disabled=["id", "data_admissao"],
            column_config={
                "id": None,
                "ativo": st.column_config.CheckboxColumn("Ativo?"),
                "skill_cplug": st.column_config.CheckboxColumn("Cplug"),
                "skill_dd": st.column_config.CheckboxColumn("DD"),
                "nivel": st.column_config.SelectboxColumn("Nível", options=["Junior", "Pleno", "Senior", "Especialista"])
            },
            key="editor_analistas"
        )

        if st.button("💾 Salvar Alterações na Tabela", type="primary"):
            conn = database.get_db_connection()
            try:
                for i, row in df_editada.iterrows():
                    # CORREÇÃO: Usar bool() no UPDATE também
                    database.run_query(conn, """
                        UPDATE analistas
                        SET nome=?, email=?, nivel=?, ativo=?, skill_cplug=?, skill_dd=?
                        WHERE id = ?
                    """, (
                        row['nome'], row['email'], row['nivel'],
                        bool(row['ativo']),       # <--- bool()
                        bool(row['skill_cplug']), # <--- bool()
                        bool(row['skill_dd']),    # <--- bool()
                        row['id']
                    ))
                conn.commit()
                st.toast("Alterações salvas!", icon="💾")
                st.cache_data.clear()
                import time
                time.sleep(1)
                st.rerun()
            finally:
                conn.close()

        # Exclusao
        st.markdown("---")
        with st.expander("Zona de Perigo: Excluir Analista"):
            opcoes_del = df_analistas['nome'].tolist()
            nome_del = st.selectbox("Selecione para excluir:", [""] + opcoes_del)
            if nome_del:
                if st.button(f"Excluir '{nome_del}'", type="secondary"):
                    conn = database.get_db_connection()
                    try:
                        id_res = pd.read_sql_query(f"SELECT id FROM analistas WHERE nome = '{nome_del}'", conn)
                        if not id_res.empty:
                            id_del = int(id_res.iloc[0]['id'])
                            database.run_query(conn, "DELETE FROM indisponibilidades WHERE id_analista = ?", (id_del,))
                            database.run_query(conn, "DELETE FROM escala_salva WHERE nome_analista = ?", (nome_del,))
                            database.run_query(conn, "DELETE FROM sobreaviso WHERE nome_analista = ?", (nome_del,))
                            database.run_query(conn, "DELETE FROM analistas WHERE id = ?", (id_del,))
                            conn.commit()
                            st.success("Analista excluído.")
                            st.cache_data.clear()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
                    finally:
                        conn.close()
except Exception as e:
    st.error(f"Erro ao carregar lista: {e}")

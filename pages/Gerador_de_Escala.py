import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import holidays
import random
import io
from openpyxl.worksheet.datavalidation import DataValidation

# --- NOSSOS MODULOS ---
import database
import utils
import engine

st.set_page_config(layout="wide", page_title="Gerador de Escala")
st.title("Gerador de Escala (Matriz)")

# --- Carregar Dados ---
df_analistas, df_indisp = utils.carregar_dados_locais()
REGRAS_STAFF = utils.load_staff_rules_from_db()
HORAS_TURNO = utils.load_shift_hours_from_db()
# -------------------------------------------

# --- Carregar Ciclos Salvos ---
try:
    conn = database.get_db_connection()
    df_ciclos = pd.read_sql_query("SELECT id, nome_ciclo FROM ciclos ORDER BY data_inicio DESC", conn)
    ciclos_dict = dict(zip(df_ciclos['id'], df_ciclos['nome_ciclo']))
    conn.close()
except Exception as e:
    st.error(f"Erro ao carregar ciclos: {e}")
    ciclos_dict = {}

# --- Interface Principal ---
if df_analistas.empty:
    st.error("Nenhum analista cadastrado.")
    st.info("Por favor, acesse a pagina 'Gerenciar Analistas' no menu ao lado para comecar.")
elif not ciclos_dict:
    st.error("Nenhum ciclo de escala foi criado.")
    st.info("Por favor, acesse a pagina 'Gerador de Ciclo' no menu ao lado para criar um ciclo primeiro.")
else:
    st.header("1. Selecione o Ciclo da Escala")

    id_ciclo_selecionado = st.selectbox(
        "Selecione o Ciclo para gerar a escala",
        options=ciclos_dict.keys(),
        format_func=lambda x: ciclos_dict[x],
        key="select_ciclo"
    )

    # Gerencia o estado da escala
    if 'ciclo_anterior' not in st.session_state: st.session_state.ciclo_anterior = -1
    if 'df_analistas_editada' not in st.session_state: st.session_state.df_analistas_editada = None
    if 'df_rodape_editada' not in st.session_state: st.session_state.df_rodape_editada = None

    if st.session_state.ciclo_anterior != id_ciclo_selecionado:
        st.session_state.ciclo_anterior = id_ciclo_selecionado
        st.session_state.df_analistas_editada = None
        st.session_state.df_rodape_editada = None

    if st.session_state.df_analistas_editada is None:
        conn = database.get_db_connection()

        # Carrega escala salva (se houver)
        df_historico = pd.read_sql_query(
            f"SELECT nome_analista, nome_coluna_dia, turno FROM escala_salva WHERE id_ciclo = {id_ciclo_selecionado}",
            conn)

        # --- CORREÇÃO DO ERRO SQL AQUI ---
        # Mudamos "AND ativo = 1" para "AND ativo" (Postgres compatible)
        df_dias_ciclo = pd.read_sql_query(
            f"SELECT nome_coluna, data_dia FROM ciclo_dias WHERE id_ciclo = {id_ciclo_selecionado} AND ativo ORDER BY data_dia ASC",
            conn)
        # ---------------------------------

        conn.close()

        dias_para_coluna_str = df_dias_ciclo['nome_coluna'].tolist()
        mapa_coluna_data = dict(zip(df_dias_ciclo['nome_coluna'], pd.to_datetime(df_dias_ciclo['data_dia']).dt.date))

        df_escala_pronta = None

        if not df_historico.empty:
            st.success(f"Escala salva encontrada para o ciclo '{ciclos_dict[id_ciclo_selecionado]}'. Carregando do historico.")
            df_escala_pronta = df_historico.pivot(
                index='nome_analista',
                columns='nome_coluna_dia',
                values='turno'
            )
            df_escala_pronta = df_escala_pronta.reindex(columns=dias_para_coluna_str)

        else:
            st.info("Nenhuma escala salva encontrada para este ciclo. Clique abaixo para gerar uma nova proposta.")
            if st.button("Gerar Proposta de Escala", type="primary"):
                
                with st.spinner(f"Gerando matriz da escala para '{ciclos_dict[id_ciclo_selecionado]}'..."):
                    lista_analistas = df_analistas["nome"].tolist()
                    df_proposta = pd.DataFrame(index=lista_analistas, columns=dias_para_coluna_str)
                    df_proposta = df_proposta.fillna("FOLGA")

                    if not df_indisp.empty:
                        df_indisp['data_obj'] = pd.to_datetime(df_indisp['data']).dt.date
                        mapa_id_nome = dict(zip(df_analistas['id'], df_analistas['nome']))
                        for idx, indisponivel in df_indisp.iterrows():
                            analista_nome = mapa_id_nome.get(indisponivel['id_analista'])
                            data_indisp = indisponivel['data_obj']
                            if analista_nome in df_proposta.index:
                                for col_str in dias_para_coluna_str:
                                    if data_indisp.strftime('%d/%m') in col_str:
                                        df_proposta.loc[analista_nome, col_str] = "Ferias"
                                        break

                    df_escala_pronta, logs = engine.executar_logica_de_alocacao(
                        df_proposta.copy(),
                        df_analistas,
                        dias_para_coluna_str,
                        REGRAS_STAFF,
                        utils.REGRAS_QUALIDADE
                    )

                    with st.expander("Ver Logs da Geracao", expanded=False):
                        st.code("\n".join(logs), language=None)
                st.success("Proposta de escala gerada!")

        if df_escala_pronta is not None:
            mapa_experiencia = dict(zip(df_analistas['nome'], df_analistas['nivel']))
            niveis_experientes = utils.REGRAS_QUALIDADE["niveis_experientes"]
            mentor_row = []

            for coluna in df_escala_pronta.columns:
                turno_do_dia = df_escala_pronta[coluna]
                mentor_encontrado = None
                analista_integral_list = turno_do_dia[turno_do_dia == "Integral"].index.tolist()
                if analista_integral_list:
                    nome_integral = analista_integral_list[0]
                    if mapa_experiencia.get(nome_integral) in niveis_experientes:
                        mentor_encontrado = nome_integral
                if not mentor_encontrado:
                    trabalhando_manha = turno_do_dia[turno_do_dia == "Manha"].index.tolist()
                    trabalhando_noite = turno_do_dia[turno_do_dia == "Noite"].index.tolist()
                    candidatos = trabalhando_manha + trabalhando_noite
                    candidatos_experientes = [nome for nome in candidatos if
                                              mapa_experiencia.get(nome) in niveis_experientes]
                    if candidatos_experientes:
                        random.shuffle(candidatos_experientes)
                        mentor_encontrado = candidatos_experientes[0]
                mentor_row.append(mentor_encontrado if mentor_encontrado else "(Nao Encontrado)")
            df_escala_pronta.loc["MENTOR"] = mentor_row

            conn = database.get_db_connection()
            df_sobreaviso = pd.read_sql_query("SELECT * FROM sobreaviso", conn)
            conn.close()
            if not df_sobreaviso.empty:
                df_sobreaviso['data_inicio'] = pd.to_datetime(df_sobreaviso['data_inicio']).dt.date
                df_sobreaviso['data_fim'] = pd.to_datetime(df_sobreaviso['data_fim']).dt.date

            sobreaviso_row = []
            for coluna in df_escala_pronta.columns:
                dia_atual = mapa_coluna_data.get(coluna)
                analista_sobreaviso = "(Vazio)"
                if dia_atual and not df_sobreaviso.empty:
                    match = df_sobreaviso[
                        (df_sobreaviso['data_inicio'] <= dia_atual) &
                        (df_sobreaviso['data_fim'] >= dia_atual)
                        ]
                    if not match.empty:
                        analista_sobreaviso = match.iloc[0]['nome_analista']
                sobreaviso_row.append(analista_sobreaviso)
            df_escala_pronta.loc["SOBREAVISO"] = sobreaviso_row

            linhas_analistas = sorted([nome for nome in df_escala_pronta.index if nome not in ["MENTOR", "SOBREAVISO"]])
            linhas_ordenadas = linhas_analistas + ["MENTOR", "SOBREAVISO"]
            df_escala_pronta = df_escala_pronta.reindex(index=linhas_ordenadas)

            st.session_state.df_analistas_editada = df_escala_pronta.drop(index=["MENTOR", "SOBREAVISO"], errors='ignore')
            st.session_state.df_rodape_editada = df_escala_pronta.loc[["MENTOR", "SOBREAVISO"]]

    # --- Secao 2: Analise e Ajuste ---
    if st.session_state.df_analistas_editada is not None:
        st.header("2. Analise e Ajuste a Escala")
        st.info("Voce pode clicar duas vezes em uma celula para editar.")

        opcoes_escala = ["FOLGA", "Manha", "Noite", "Integral", "Ferias"]
        config_colunas = {col: st.column_config.SelectboxColumn(col, options=opcoes_escala, default="FOLGA") for col in st.session_state.df_analistas_editada.columns}

        df_editada_analistas = st.data_editor(
            st.session_state.df_analistas_editada,
            column_config=config_colunas,
            use_container_width=True,
            height=600,
            key="escala_editor_analistas"
        )

        df_editada_rodape = st.data_editor(
            st.session_state.df_rodape_editada,
            use_container_width=True,
            key="escala_editor_rodape"
        )

        # --- Secao 3. Validacao e Contagem ---
        st.header("3. Validacao e Contagem")
        st.subheader("Vagas Preenchidas por Dia")
        contagem_dia = df_editada_analistas.apply(lambda col: col.value_counts()).reindex(["Manha", "Noite", "Integral"]).fillna(0).astype(int)
        st.dataframe(contagem_dia, use_container_width=True)

        st.divider()
        st.subheader("Carga Horaria por Analista")
        contagem_analista = df_editada_analistas.apply(lambda row: row.value_counts(), axis=1).fillna(0)
        for t in ["Manha", "Noite", "Integral"]: 
            if t not in contagem_analista.columns: contagem_analista[t] = 0

        contagem_analista['Horas_Decimal'] = (
                (contagem_analista['Manha'] * HORAS_TURNO["Manha"]) +
                (contagem_analista['Noite'] * HORAS_TURNO["Noite"]) +
                (contagem_analista['Integral'] * HORAS_TURNO["Integral"])
        )

        def format_hours(val):
            hours = int(val); minutes = int(round((val - hours) * 60))
            return f"{hours:02d}:{minutes:02d}"

        st.dataframe(
            contagem_analista[["Manha", "Noite", "Integral", "Horas_Decimal"]].astype(float)
            .style.applymap(lambda v: 'background-color: #ff4b4b' if v > 30 else '', subset=['Horas_Decimal'])
            .format({'Horas_Decimal': format_hours, 'Manha': '{:.0f}', 'Noite': '{:.0f}', 'Integral': '{:.0f}'}),
            use_container_width=True
        )

        # --- Secao 4: Salvar ---
        st.header("4. Salvar Escala (Excel e Historico)")
        col1_save, col2_save = st.columns(2)
        df_final_para_salvar = pd.concat([df_editada_analistas, df_editada_rodape])

        with col1_save:
            if st.button("Salvar no Historico", type="primary"):
                try:
                    conn = database.get_db_connection()
                    cursor = conn.cursor()

                    # Limpa anterior
                    cursor.execute(f"DELETE FROM escala_salva WHERE id_ciclo = {id_ciclo_selecionado}")

                    # --- CORREÇÃO DO SALVAMENTO (Index Name) ---
                    df_final_para_salvar.index.name = 'nome_analista_temp'
                    df_para_salvar = df_final_para_salvar.reset_index().melt(
                        id_vars='nome_analista_temp',
                        var_name='nome_coluna_dia',
                        value_name='turno'
                    ).rename(columns={'nome_analista_temp': 'nome_analista'})
                    # ------------------------------------------

                    df_para_salvar['id_ciclo'] = id_ciclo_selecionado
                    df_para_salvar['data_salvamento'] = datetime.now()

                    # Insert multi para performance no Postgres
                    df_para_salvar.to_sql('escala_salva', conn, if_exists='append', index=False, method='multi', chunksize=500)
                    
                    conn.commit()
                    st.success("Escala salva com sucesso no historico!")

                    del st.session_state.df_analistas_editada
                    del st.session_state.df_rodape_editada
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao salvar no historico: {e}")
                finally:
                    if conn: conn.close()

        with col2_save:
            df_excel = utils.to_excel(df_final_para_salvar)
            st.download_button(
                label="Baixar Escala como Excel",
                data=df_excel,
                file_name=f"escala_{ciclos_dict.get(id_ciclo_selecionado, 'ciclo')}.xlsx".replace('/', '-'),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

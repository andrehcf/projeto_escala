import random
import utils


def executar_logica_de_alocacao(df_proposta, df_analistas, colunas_datas, regras_staff, regras_qualidade):
    log_messages = []
    log_messages.append("--- Iniciando Alocacao (v12 - Com Preferencias) ---")

    # Carrega dados
    HORAS_TURNO = utils.load_shift_hours_from_db()
    MAX_HORAS = utils.load_max_hours_limit()

    lista_analistas = df_analistas['nome'].tolist()

    # Mapas de Preferencia
    mapa_pref_dia = dict(zip(df_analistas['nome'], df_analistas['pref_dia']))  # Sabado, Domingo, Tanto faz
    mapa_pref_turno = dict(zip(df_analistas['nome'], df_analistas['pref_turno']))  # Integral, Curto, Tanto faz

    # Contadores
    contagem_turnos = {nome: 0 for nome in lista_analistas}
    contagem_horas = {nome: 0.0 for nome in lista_analistas}

    mapa_domingo_anterior = {}
    coluna_domingo_anterior = None
    for col in colunas_datas:
        if "Dom" in col:
            coluna_domingo_anterior = col
        elif "Sab" in col and coluna_domingo_anterior:
            mapa_domingo_anterior[col] = coluna_domingo_anterior
            coluna_domingo_anterior = None

    for coluna_dia in colunas_datas:
        if "Dom" in coluna_dia:
            tipo_dia = "Domingo"
        elif "Sab" in coluna_dia:
            tipo_dia = "Sabado"
        else:
            tipo_dia = "Feriado"

        regras_do_dia = regras_staff.get(tipo_dia, {})

        # Ordena turnos: Integral primeiro (mais dificil de preencher), depois os curtos
        turnos_ordenados = sorted(regras_do_dia.keys(), key=lambda t: 0 if t == "Integral" else 1)

        for turno in turnos_ordenados:
            vagas_total = regras_do_dia[turno]
            horas_deste = HORAS_TURNO.get(turno, 0)

            if vagas_total == 0: continue

            log_messages.append(f"Processando: {coluna_dia} - {turno}")

            candidatos = []
            for nome in lista_analistas:
                # Filtro 1: Disponibilidade e Limite de Horas
                if df_proposta.loc[nome, coluna_dia] == "FOLGA":
                    if (contagem_horas[nome] + horas_deste) <= MAX_HORAS:
                        candidatos.append(nome)

            if not candidatos:
                log_messages.append(f"  -> ALERTA: Sem candidatos.")
                continue

            random.shuffle(candidatos)

            # CALCULO DE CUSTO (A Magica acontece aqui)
            custo_alocacao = {}
            for nome in candidatos:
                # 1. Balanceamento (Peso Maximo)
                custo = contagem_turnos[nome] * 100

                # 2. Preferencia de Dia
                pref_d = mapa_pref_dia.get(nome, "Tanto faz")
                if pref_d != "Tanto faz":
                    if pref_d != tipo_dia:
                        custo += 50  # Penalidade: Queria Sabado, mas hoje e Domingo

                # 3. Preferencia de Turno
                pref_t = mapa_pref_turno.get(nome, "Tanto faz")
                if pref_t != "Tanto faz":
                    if pref_t == "Integral" and turno != "Integral": custo += 50  # Queria Integral, mas turno e curto
                    if pref_t == "Curto" and turno == "Integral": custo += 50  # Queria Curto, mas turno e Integral

                # 4. Regra de Descanso (Dom/Sab)
                if tipo_dia == "Sabado" and "Sab" in coluna_dia and coluna_dia in mapa_domingo_anterior:
                    col_domingo = mapa_domingo_anterior[coluna_dia]
                    if df_proposta.loc[nome, col_domingo] != "FOLGA":
                        custo += 200  # Penalidade ALTA pra evitar trabalhar fds inteiro

                custo_alocacao[nome] = custo

            candidatos.sort(key=lambda nome: custo_alocacao[nome])

            # Aloca (Top X mais baratos)
            selecionados = candidatos[:vagas_total]

            for nome in selecionados:
                df_proposta.loc[nome, coluna_dia] = turno
                contagem_turnos[nome] += 1
                contagem_horas[nome] += horas_deste

    log_messages.append("--- Concluido ---")
    return df_proposta, log_messages
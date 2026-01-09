import sqlite3
import streamlit as st
import os
from datetime import datetime

# Tenta importar psycopg2 para PostgreSQL (só funciona se instalado via requirements.txt)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

DB_NAME = 'escala.db'

def get_db_connection():
    # Verifica se existem segredos de configuração (Sinal que estamos na nuvem)
    if "POSTGRES_URL" in st.secrets:
        # CONEXÃO POSTGRESQL (NUVEM)
        conn = psycopg2.connect(st.secrets["POSTGRES_URL"])
        return conn
    else:
        # CONEXÃO SQLITE (LOCAL)
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn

# --- Funcao Auxiliar para Executar Queries Compatíveis ---
def run_query(conn, sql, params=()):
    """
    Função wrapper para lidar com diferenças entre SQLite (?) e Postgres (%s)
    """
    is_postgres = "POSTGRES_URL" in st.secrets
    
    # 1. Ajusta o SQL para o dialeto correto
    if is_postgres:
        # Troca placeholder
        sql = sql.replace('?', '%s')
        
        # Ajustes de Tipagem do Postgres
        sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        
        # CORREÇÃO DO ERRO: Troca DATETIME por TIMESTAMP globalmente
        sql = sql.replace('DATETIME', 'TIMESTAMP') 
        
        # Ajuste opcional para data atual
        sql = sql.replace('DEFAULT CURRENT_TIMESTAMP', 'DEFAULT NOW()')
    
    # 2. Executa
    try:
        if is_postgres:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = conn.cursor()
            
        cursor.execute(sql, params)
        return cursor
    except Exception as e:
        # Loga o erro para facilitar debug no Streamlit Cloud
        print(f"Erro ao executar SQL: {sql}") 
        raise e

def init_all_db_tables():
    conn = get_db_connection()
    try:
        # --- TABELAS ---
        # Analistas
        run_query(conn, '''
            CREATE TABLE IF NOT EXISTS analistas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE, 
                email TEXT UNIQUE,
                nivel TEXT NOT NULL,
                data_admissao DATE NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT TRUE,
                skill_cplug BOOLEAN NOT NULL DEFAULT FALSE,
                skill_dd BOOLEAN NOT NULL DEFAULT FALSE,
                pref_dia TEXT DEFAULT 'Tanto faz',
                pref_turno TEXT DEFAULT 'Tanto faz'
            );
        ''')
        
        # Indisponibilidades
        run_query(conn, '''
            CREATE TABLE IF NOT EXISTS indisponibilidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_analista INTEGER NOT NULL, 
                data DATE NOT NULL,
                data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_analista) REFERENCES analistas(id),
                UNIQUE(id_analista, data)
            );
        ''')
        
        # Ciclos
        run_query(conn, 'CREATE TABLE IF NOT EXISTS ciclos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_ciclo TEXT UNIQUE, data_inicio DATE, data_fim DATE);')
        
        # Ciclo Dias
        run_query(conn, '''
            CREATE TABLE IF NOT EXISTS ciclo_dias (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                id_ciclo INTEGER, 
                nome_coluna TEXT, 
                data_dia DATE, 
                ativo BOOLEAN DEFAULT TRUE,
                FOREIGN KEY(id_ciclo) REFERENCES ciclos(id)
            );
        ''')
        
        # Escala Salva (O ERRO ESTAVA AQUI, no DATETIME)
        run_query(conn, 'CREATE TABLE IF NOT EXISTS escala_salva (id INTEGER PRIMARY KEY AUTOINCREMENT, id_ciclo INTEGER, nome_analista TEXT, nome_coluna_dia TEXT, turno TEXT, data_salvamento DATETIME, UNIQUE(id_ciclo, nome_analista, nome_coluna_dia));')
        
        # Sobreaviso
        run_query(conn, 'CREATE TABLE IF NOT EXISTS sobreaviso (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_analista TEXT, data_inicio DATE, data_fim DATE);')
        
        # Regras e Configs
        run_query(conn, 'CREATE TABLE IF NOT EXISTS regras_staff (id INTEGER PRIMARY KEY AUTOINCREMENT, dia_tipo TEXT, turno TEXT, quantidade INTEGER, UNIQUE(dia_tipo, turno));')
        run_query(conn, 'CREATE TABLE IF NOT EXISTS configuracao_turnos (id INTEGER PRIMARY KEY AUTOINCREMENT, turno TEXT UNIQUE, horas REAL);')
        run_query(conn, 'CREATE TABLE IF NOT EXISTS configuracao_limites (id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE, valor REAL);')
        
        # Feriados
        run_query(conn, '''
            CREATE TABLE IF NOT EXISTS feriados_anuais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_iso DATE UNIQUE,
                nome_feriado TEXT,
                usar_na_escala BOOLEAN DEFAULT TRUE
            );
        ''')

        conn.commit()
    except Exception as e:
        st.error(f"Erro ao inicializar DB: {e}")
    finally:
        conn.close()

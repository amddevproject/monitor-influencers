from playwright.sync_api import Playwright, sync_playwright, Error as PlaywrightError
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import tempfile
import os
import requests
import json
import time
import bcrypt



# ==============================================
# CONFIGURAÇÃO INICIAL DO APP
# ==============================================
st.set_page_config(layout="wide", page_title="Agência Referência TikTok")

# ==============================================
# CSS para Estilização
# ==============================================
st.markdown(
    """
<style>
    /* Estilo geral */
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #333333;
        background-color: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 5%;
        padding-right: 5%;
    }
    h1, h2, h3, h4 {
        color: #1a1a1a;
        font-weight: 600;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: bold;
        transition: all 0.3s ease;
        border: none;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stButton > button:hover {
        background-color: #45a049;
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
    }
    /* Estilo para as colunas de KPIs */
    .st-emotion-cache-1uj251k {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True
)

# ...existing code...
def convert_to_int(text):
    """Converte texto do TikTok (ex: '1.2M') para inteiro."""
    text = text.replace(',', '').replace('.', '')
    if 'K' in text:
        return int(float(text.replace('K', '')) * 1000)
    elif 'M' in text:
        return int(float(text.replace('M', '')) * 1000000)
    elif 'B' in text:
        return int(float(text.replace('B', '')) * 1000000000)
    else:
        try:
            return int(text)
        except:
            return 0

def estimate_earnings(views):
    """Estimativa simples de ganhos baseada em visualizações."""
# Ajuste conforme sua lógica
    return views * 0.01
# ...existing code...

# ==============================================
# BANCO DE DADOS
# ==============================================

# O `st.cache_resource` garante que a conexão com o banco de dados seja criada
# apenas uma única vez, mesmo que o script do Streamlit seja re-executado.
@st.cache_resource
def get_db_connection():
    """
    Cria e retorna a conexão com o banco de dados 'influencers.db'.
    Esta função é cacheada para evitar múltiplas conexões.
    """
    try:
        conn = sqlite3.connect("influencers.db", check_same_thread=False)
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

def init_db(conn):
    
#    Hashing das senhas antes de inserir
    admin_senha_hashed = hash_password('dev')
    dev_senha_hashed = hash_password('dev@123')

    cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)",
                    ('admin', admin_senha_hashed, 'criador'))
    cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)",
                    ('dev', dev_senha_hashed, 'criador'))
    conn.commit()
    
    
    """
    Inicializa as tabelas do banco de dados se elas não existirem.
    
    Args:
        conn (sqlite3.Connection): O objeto de conexão com o banco de dados.
    """
    if conn is None:
        return
    
    try:
        cursor = conn.cursor()

        # Cria a tabela de usuários
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            senha TEXT,
            tipo TEXT
        )
        """)

        # Cria a tabela de histórico de métricas
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            influencer TEXT,
            tipo TEXT,
            valor INTEGER,
            data TEXT,
            metodo TEXT,
            ganhos REAL,
            live_curtidas INTEGER,
            live_visualizacoes INTEGER
        )
        """)

        # Cria a tabela para produtos de live
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos_live (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            influencer TEXT,
            nome_produto TEXT,
            valor_estimado REAL,
            data TEXT
        )
        """)

        # Adiciona colunas se não existirem (já está no seu código, mantivemos)
        try:
            cursor.execute("ALTER TABLE historico ADD COLUMN ganhos REAL")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE historico ADD COLUMN live_curtidas INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE historico ADD COLUMN live_visualizacoes INTEGER")
        except sqlite3.OperationalError:
            pass

        # Adiciona ou atualiza usuários de login (também mantivemos)
        cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)",
                        ('admin', 'alfa@01admin', 'criador'))
        cursor.execute("INSERT OR IGNORE INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)",
                        ('dev', 'dev@123', 'criador'))

        conn.commit()

    except Exception as e:
        st.error(f"Erro ao inicializar banco de dados: {str(e)}")


# Obtém a conexão cacheada e inicializa o banco de dados
conn = get_db_connection()
if conn:
    #init_db(conn)
    cursor = conn.cursor()

# ==============================================
# CONFIGURAÇÃO DO PLAYWRIGHT E NAVEGADOR 
# ==============================================
# Use st.cache_resource para inicializar o Playwright e o navegador apenas uma vez
# Isso garante que a função será executada somente na primeira vez que o script rodar.
@st.cache_resource
def setup_playwright_and_browser():
    """Inicializa e retorna o Playwright e o navegador para uso no scraping."""
    try:
        p = sync_playwright().start()
        # O navegador é iniciado em modo headless (sem interface gráfica) para maior eficiência.
        browser = p.chromium.launch(headless=True)
        return p, browser
    except Exception as e:
        st.error(f"Erro ao inicializar o Playwright: {e}")
        return None, None

# Chame a função uma vez no início do script para configurar o navegador
# A variável 'browser_instance' será usada em toda a aplicação.
playwright_instance, browser_instance = setup_playwright_and_browser()

def get_tiktok_data_from_scraping(username):
    """
    Realiza o scraping dos dados de um perfil do TikTok usando o Playwright.
    
    Args:
        username (str): O nome de usuário do TikTok a ser buscado.

    Returns:
        dict: Um dicionário com o número de seguidores, curtidas e visualizações,
              ou None em caso de erro.
    """
    if not browser_instance:
        st.error("Navegador não está disponível. Por favor, recarregue a página.")
        return None

    try:
        # Cria um novo contexto de navegação para cada busca, garantindo isolamento.
        context = browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        )
        page = context.new_page()

        st.info(f"Conectando ao TikTok para buscar dados de @{username}...")
        page.goto(f"https://www.tiktok.com/@{username}", timeout=120000)

        # Localiza os elementos que contêm o número de seguidores e curtidas.
        followers_elem = page.locator("xpath=//strong[@data-e2e='followers-count']")
        likes_elem = page.locator("xpath=//strong[@data-e2e='likes-count']")

        # Espera que os elementos estejam visíveis na página.
        followers_elem.wait_for(state="visible")
        likes_elem.wait_for(state="visible")

        # Extrai o texto e converte para número inteiro.
        followers_num = convert_to_int(followers_elem.inner_text())
        likes_num = convert_to_int(likes_elem.inner_text())
        
        # Atribui o número de curtidas às visualizações para estimativa.
        # Nota: Como discutido anteriormente, esta é uma estimativa.
        views_num = likes_num

        # Fecha a página e o contexto para liberar recursos.
        page.close()
        context.close()

        return {
            'seguidores': followers_num,
            'curtidas': likes_num,
            'visualizacoes': views_num
        }

    except TimeoutError:
        st.error("Erro: O tempo limite para carregar a página ou encontrar elementos foi excedido. O influencer pode não existir ou a conexão está lenta.")
        return None
    except PlaywrightError as e:
        st.error(f"Erro do Playwright. Verifique a página do influencer. Erro: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Erro inesperado no scraping: {str(e)}")
        return None

# ...existing code...
#conn, cursor = init_db()

def estimate_earnings(views):
    """Estimativa simples de ganhos baseada em visualizações."""
    # Ajuste conforme sua lógica
    return views * 0.01

# ==============================================
# FUNÇÕES DO APLICATIVO
# ==============================================
def hash_password(password):
    """
    Cria um hash da senha usando bcrypt.
    
    Args:
        password (str): A senha em texto simples.
        
    Returns:
        bytes: O hash da senha.
    """
    # A senha precisa ser codificada em bytes para usar o bcrypt
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed


def verificar_login(usuario, senha):
    """
    Verifica se o login e senha estão corretos usando a senha com hash.
    
    Args:
        usuario (str): O nome de usuário.
        senha (str): A senha em texto simples fornecida pelo usuário.
        
    Returns:
        tuple or None: O registro do usuário se o login for bem-sucedido,
                       ou None caso contrário.
    """
    try:
        # Busca o usuário pelo nome de usuário
        cursor.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,))
        user_record = cursor.fetchone()

        if user_record:
            # Pega a senha com hash armazenada no banco de dados
            db_senha_hashed = user_record[2]
            
            # Compara a senha fornecida (em texto simples) com a senha com hash do banco
            if bcrypt.checkpw(senha.encode('utf-8'), db_senha_hashed):
                return user_record  # Login bem-sucedido
        
        return None  # Login falhou
    except Exception as e:
        st.error(f"Erro ao verificar login: {str(e)}")
        return None


def adicionar_registro(usuario, influencer, tipo, valor, metodo, live_curtidas=0, live_visualizacoes=0):
    """
    Adiciona um registro de métricas de influencer ao banco de dados.
    
    Args:
        usuario (str): O usuário logado que está adicionando o registro.
        influencer (str): O nome do influencer.
        tipo (str): O tipo de métrica (e.g., 'seguidores').
        valor (int): O valor da métrica.
        metodo (str): O método de coleta dos dados.
        live_curtidas (int): Número de curtidas em lives (opcional).
        live_visualizacoes (int): Número de visualizações em lives (opcional).
    
    Returns:
        bool: True se o registro foi adicionado com sucesso, False caso contrário.
    """
    try:
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Assume que estimate_earnings está definida em outra parte do seu código
        ganhos_estimados = estimate_earnings(valor)
        
        cursor.execute("""
        INSERT INTO historico (usuario, influencer, tipo, valor, data, metodo, ganhos, live_curtidas, live_visualizacoes) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (usuario, influencer, tipo, valor, data, metodo, ganhos_estimados, live_curtidas, live_visualizacoes))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar registro: {str(e)}")
        return False


def check_monthly_live_scrape(influencer, usuario):
    """
    Verifica se um scraping de live já foi realizado para o influencer neste mês.
    
    Args:
        influencer (str): O nome do influencer.
        usuario (str): O nome do usuário.
        
    Returns:
        bool: True se um novo scraping pode ser feito, False caso contrário.
    """
    cursor.execute("""
    SELECT data FROM historico
    WHERE influencer = ? AND usuario = ? AND live_visualizacoes > 0
    ORDER BY data DESC LIMIT 1
    """, (influencer, usuario))
    last_scrape = cursor.fetchone()

    if last_scrape:
        last_date = datetime.strptime(last_scrape[0], "%Y-%m-%d %H:%M:%S")
        if last_date.month == datetime.now().month and last_date.year == datetime.now().year:
            return False
    return True


def adicionar_produto_live(influencer, nome_produto, valor_estimado):
    """
    Adiciona um registro de produto de live ao banco de dados.
    
    Args:
        influencer (str): O nome do influencer.
        nome_produto (str): O nome do produto.
        valor_estimado (float): O valor estimado do produto.
        
    Returns:
        bool: True se o registro foi adicionado com sucesso, False caso contrário.
    """
    try:
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO produtos_live (influencer, nome_produto, valor_estimado, data)
        VALUES (?, ?, ?, ?)
        """, (influencer, nome_produto, valor_estimado, data))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar produto: {str(e)}")
        return False


def get_produtos_ganhados(influencers, data_inicio, data_fim):
    """
    Busca no banco de dados os produtos ganhos por influencers em um período.
    
    Args:
        influencers (list): Uma lista de nomes de influencers.
        data_inicio (datetime): Data de início da busca.
        data_fim (datetime): Data de fim da busca.
        
    Returns:
        pd.DataFrame: Um DataFrame do Pandas com os produtos encontrados.
    """
    try:
        query = """
        SELECT influencer, nome_produto, valor_estimado, data
        FROM produtos_live
        WHERE influencer IN ({}) AND data >= ? AND data <= ?
        """.format(','.join(['?'] * len(influencers)))

        params = influencers + [data_inicio.strftime("%Y-%m-%d 00:00:00"), data_fim.strftime("%Y-%m-%d 23:59:59")]
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar produtos: {str(e)}")
        return pd.DataFrame()


def exportar_excel(df, filename="relatorio.xlsx"):
    """
    Cria um botão de download para exportar um DataFrame para um arquivo Excel.
    
    Args:
        df (pd.DataFrame): O DataFrame do Pandas a ser exportado.
        filename (str): O nome do arquivo a ser salvo.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            df.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            st.download_button(
                "📊 Exportar para Excel",
                f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        os.unlink(tmp_path)
    except Exception as e:
        st.error(f"Erro ao exportar arquivo: {str(e)}")

# ==============================================
# CONFIGURAÇÃO INICIAL E CONEXÃO COM O BANCO
# ==============================================
# Define o layout da página
st.set_page_config(layout="wide", page_title="Gerenciamento de Influencers")

# Conecta ao banco de dados SQLite
conn = sqlite3.connect('tiktok_data.db')
cursor = conn.cursor()

# Inicializa o estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
# ==============================================
# FUNÇÕES DO APLICATIVO
# ==============================================

def hash_password(password):
    """
    Cria um hash da senha usando bcrypt.
    
    Args:
        password (str): A senha em texto simples.
        
    Returns:
        bytes: O hash da senha.
    """
    # A senha precisa ser codificada em bytes para usar o bcrypt
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed_password):
    """
    Verifica se a senha em texto puro corresponde ao hash.
    
    Args:
        password (str): A senha em texto puro fornecida pelo usuário.
        hashed_password (bytes): O hash da senha armazenado no banco de dados.
        
    Returns:
        bool: True se a senha for válida, False caso contrário.
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def init_db():
    """Inicializa as tabelas do banco de dados, se não existirem, e insere usuários padrão."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        usuario TEXT PRIMARY KEY,
        senha BLOB NOT NULL,
        tipo TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        influencer TEXT,
        tipo TEXT,
        valor REAL,
        data TIMESTAMP,
        metodo TEXT,
        ganhos REAL,
        live_curtidas INTEGER,
        live_visualizacoes INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos_live (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        influencer TEXT,
        nome_produto TEXT,
        valor_estimado REAL,
        data TIMESTAMP
    )
    """)
    
    # Adiciona usuários padrão se ainda não existirem, com senhas hasheadas
    admin_senha_hashed = hash_password('alfa@01admin')
    dev_senha_hashed = hash_password('dev@123')
    
    # Verifica se os usuários já existem para evitar duplicatas
    cursor.execute("SELECT usuario FROM usuarios WHERE usuario = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)", 
                       ('admin', admin_senha_hashed, 'criador'))
    
    cursor.execute("SELECT usuario FROM usuarios WHERE usuario = 'dev'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (usuario, senha, tipo) VALUES (?, ?, ?)", 
                       ('dev', dev_senha_hashed, 'criador'))
                       
    conn.commit()

# ==============================================
# INTERFACE DO STREAMLIT
# ==============================================

def login_page():
    """Exibe a tela de login."""
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Usuário")
    password = st.sidebar.text_input("Senha", type="password")
    
    if st.sidebar.button("Entrar"):
        cursor.execute("SELECT senha FROM usuarios WHERE usuario = ?", (username,))
        result = cursor.fetchone()
        
        if result and check_password(password, result[0]):
            st.success(f"Bem-vindo, {username}!")
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")

def main_app():
    """Exibe o conteúdo principal da aplicação."""
    st.title(f"Bem-vindo, {st.session_state['username']}!")
    st.write("Aqui seria o conteúdo principal da sua aplicação.")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.rerun()

# ==============================================
# PONTO DE ENTRADA DO APLICATIVO
# ==============================================

if __name__ == '__main__':
    # Inicializa o banco de dados antes de tudo
    init_db() 
    
    # Verifica o estado da sessão para decidir qual página exibir
    if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
        login_page()
    else:
        main_app()

# ==============================================
# FUNÇÕES DO APLICATIVO
# ==============================================

def hash_password(password):
    """Cria um hash seguro para a senha usando bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verificar_login(usuario, senha):
    """Verifica o login e senha contra o hash armazenado no banco de dados."""
    try:
        cursor.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,))
        user_record = cursor.fetchone()
        if user_record and bcrypt.checkpw(senha.encode('utf-8'), user_record[1]):
            return user_record
        return None
    except Exception as e:
        st.error(f"Erro ao verificar login: {str(e)}")
        return None

def adicionar_registro(usuario, influencer, tipo, valor, metodo, live_curtidas=0, live_visualizacoes=0):
    """Adiciona um novo registro de métrica ao banco de dados."""
    try:
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # A função estimate_earnings deve ser definida em outro lugar do código
        ganhos_estimados = estimate_earnings(valor) if tipo == 'visualizacoes' else 0
        
        cursor.execute("""
        INSERT INTO historico (usuario, influencer, tipo, valor, data, metodo, ganhos, live_curtidas, live_visualizacoes) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (usuario, influencer, tipo, valor, data, metodo, ganhos_estimados, live_curtidas, live_visualizacoes))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar registro: {str(e)}")
        return False

def check_monthly_live_scrape(influencer, usuario):
    """Verifica se uma busca de live já foi feita neste mês para o influencer."""
    cursor.execute("""
    SELECT data FROM historico
    WHERE influencer = ? AND usuario = ? AND live_visualizacoes > 0
    ORDER BY data DESC LIMIT 1
    """, (influencer, usuario))
    last_scrape = cursor.fetchone()
    if last_scrape:
        last_date = datetime.strptime(last_scrape[0], "%Y-%m-%d %H:%M:%S")
        if last_date.month == datetime.now().month and last_date.year == datetime.now().year:
            return False
    return True

def adicionar_produto_live(influencer, nome_produto, valor_estimado):
    """Adiciona um registro de produto ganho em live ao banco de dados."""
    try:
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO produtos_live (influencer, nome_produto, valor_estimado, data)
        VALUES (?, ?, ?, ?)
        """, (influencer, nome_produto, valor_estimado, data))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar produto: {str(e)}")
        return False

def get_produtos_ganhados(influencers, data_inicio, data_fim):
    """Busca produtos ganhos no banco de dados por influencer e período."""
    try:
        query = """
        SELECT influencer, nome_produto, valor_estimado, data
        FROM produtos_live
        WHERE influencer IN ({}) AND data >= ? AND data <= ?
        """.format(','.join(['?'] * len(influencers)))
        params = influencers + [data_inicio.strftime("%Y-%m-%d 00:00:00"), data_fim.strftime("%Y-%m-%d 23:59:59")]
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar produtos: {str(e)}")
        return pd.DataFrame()

def exportar_excel(df, filename="relatorio.xlsx"):
    """Cria um botão de download para exportar um DataFrame para um arquivo Excel."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            df.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            st.download_button(
                "📊 Exportar para Excel",
                f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        os.unlink(tmp_path)
    except Exception as e:
        st.error(f"Erro ao exportar arquivo: {str(e)}")

# Função mock para o scraping, substituída pelo Google Search para este exemplo
def get_tiktok_data_from_scraping(influencer):
    """
    Função mock que simula a obtenção de dados de um influencer.
    Em um aplicativo real, isso seria a lógica de scraping.
    """
    try:
        # Usando Google Search para simular a busca de dados do influencer
        search_query = f"TikTok stats for {influencer} followers likes views"
        results = search(queries=[search_query])
        
        # Analisando os resultados para uma simulação simples
        search_snippet = results[0].results[0].snippet if results and results[0].results else ""
        
        # Regex para extrair números
        import re
        followers_match = re.search(r"(\d+(\.\d+)?)[MK] followers", search_snippet)
        likes_match = re.search(r"(\d+(\.\d+)?)[MK] likes", search_snippet)
        views_match = re.search(r"(\d+(\.\d+)?)[MK] views", search_snippet)
        
        followers = float(followers_match.group(1)) * 1000000 if followers_match else 0
        likes = float(likes_match.group(1)) * 1000000 if likes_match else 0
        views = float(views_match.group(1)) * 1000000 if views_match else 0
        
        if followers > 0:
            return {
                'seguidores': int(followers),
                'curtidas': int(likes),
                'visualizacoes': int(views)
            }
        else:
            return None
    except Exception as e:
        st.error(f"Erro ao simular busca de dados: {str(e)}")
        return None

def estimate_earnings(views):
    """Calcula ganhos estimados com base nas visualizações."""
    if views <= 10000:
        return views * 0.0001
    elif views <= 100000:
        return views * 0.0002
    else:
        return views * 0.0003

# ==============================================
# INTERFACES DO USUÁRIO
# ==============================================
def login_section():
    """Interface para a tela de login."""
    st.title("Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Acesse"):
        if not usuario or not senha:
            st.warning("Por gentileza, preencha todos os campos.")
            return

        usuario_db = verificar_login(usuario, senha)
        if usuario_db:
            st.session_state.logged_in = True
            st.session_state.usuario = usuario
            st.session_state.tipo_usuario = usuario_db[2]  # Índice 2 para a coluna 'tipo'
            st.success("Login realizado com sucesso!")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

def main_app():
    """Interface principal do aplicativo após o login."""
    st.title(f"Bem-vindo, {st.session_state.usuario}!")
    st.subheader("Gerenciamento de Carreira de Tiktokers")

    # --- Seção 1: Buscar e Adicionar Influencer ---
    st.header("1. Buscar e Adicionar Influencer")
    influencer = st.text_input("Nome do influencer (sem @)", placeholder="ex: simoneses")
    if st.button("Buscar Dados e Salvar"):
        if not influencer:
            st.warning("Por favor, digite o nome do influencer.")
        else:
            with st.spinner(f"Buscando dados de @{influencer}..."):
                dados = get_tiktok_data_from_scraping(influencer)
                if dados:
                    live_data = {'live_curtidas': 0, 'live_visualizacoes': 0}
                    # Otimiza a verificação e a adição dos registros
                    metricas = {
                        'seguidores': dados['seguidores'],
                        'curtidas': dados['curtidas'],
                        'visualizacoes': dados['visualizacoes'],
                        'ganhos': estimate_earnings(dados['visualizacoes'])
                    }
                    
                    salvo_com_sucesso = True
                    for tipo, valor in metricas.items():
                        if not adicionar_registro(st.session_state.usuario, f"@{influencer}", tipo, valor, 'Scraping'):
                            salvo_com_sucesso = False
                            break
                    
                    if salvo_com_sucesso:
                        st.success(f"Dados de @{influencer} salvos com sucesso!")
                        st.write(f"**Seguidores:** {dados['seguidores']:,}")
                        st.write(f"**Curtidas:** {dados['curtidas']:,}")
                        st.write(f"**Visualizações:** {dados['visualizacoes']:,}")
                        st.write(f"**Ganhos Estimados (R$):** R$ {metricas['ganhos']:,.2f}")
                        if live_data.get('live_visualizacoes', 0) > 0:
                            st.write(f"**Live Curtidas:** {live_data.get('live_curtidas', 'N/A')}")
                            st.write(f"**Live Visualizações:** {live_data.get('live_visualizacoes', 'N/A')}")
                    else:
                        st.error("Erro ao salvar os dados no banco.")
                else:
                    st.error("Não foi possível obter os dados do influencer. Verifique o nome ou tente novamente.")

    # --- Seção 2: Análise do Histórico de Influencers ---
    st.header("2. Análise do Histórico de Influencers")
    influencers_disponiveis = pd.read_sql_query(
        "SELECT DISTINCT influencer FROM historico WHERE usuario = ?", conn, params=[st.session_state.usuario]
    )['influencer'].tolist()

    if not influencers_disponiveis:
        st.info("Nenhum influencer encontrado no histórico. Use a seção acima para adicionar um.")
    else:
        col_filtros1, col_filtros2 = st.columns([2, 1])
        with col_filtros1:
            influencers_selecionados = st.multiselect("Selecione os Influencers para Análise:", influencers_disponiveis)
        with col_filtros2:
            escala_unidade = st.selectbox("Escala de Visualização dos Gráficos",
                                            options=["Unidades", "Milhares (K)", "Dez Milhares (10K)", "Cem Milhares (100K)"])

        col_data_inicio, col_data_fim = st.columns(2)
        with col_data_inicio:
            data_inicio = st.date_input("Data de Início", datetime.now() - timedelta(days=30))
        with col_data_fim:
            data_fim = st.date_input("Data de Fim", datetime.now())

        if st.button("Gerar Análise"):
            if not influencers_selecionados:
                st.warning("Por favor, selecione ao menos um influencer.")
            else:
                query = f"""
                SELECT influencer, tipo, valor, data, ganhos, live_curtidas, live_visualizacoes
                FROM historico
                WHERE usuario = ? AND data >= ? AND data <= ? AND influencer IN ({','.join(['?'] * len(influencers_selecionados))})
                """
                params = [st.session_state.usuario, data_inicio.strftime("%Y-%m-%d 00:00:00"), data_fim.strftime("%Y-%m-%d 23:59:59")] + influencers_selecionados
                df = pd.read_sql_query(query, conn, params=params)

                if not df.empty:
                    df['data'] = pd.to_datetime(df['data'])
                    df = df.sort_values(by=['influencer', 'data'])
                    
                    # Refatoração da escala de visualização
                    escala_dict = {
                        "Unidades": 1,
                        "Milhares (K)": 1000,
                        "Dez Milhares (10K)": 10000,
                        "Cem Milhares (100K)": 100000
                    }
                    escala = escala_dict.get(escala_unidade, 1)
                    
                    df['valor_escala'] = df['valor'] / escala
                    df['ganhos_escala'] = df['ganhos'] / escala
                    
                    st.subheader("Resumo do Crescimento no Período")
                    crescimento_df = pd.DataFrame()

                    for influencer_sel in influencers_selecionados:
                        temp_df = df[df['influencer'] == influencer_sel]
                        if not temp_df.empty:
                            growth_metrics = {}
                            for tipo in ['seguidores', 'curtidas', 'visualizacoes', 'ganhos']:
                                df_tipo = temp_df[temp_df['tipo'] == tipo]
                                if not df_tipo.empty:
                                    start_value = df_tipo['valor'].iloc[0]
                                    end_value = df_tipo['valor'].iloc[-1]
                                    crescimento = end_value - start_value
                                    crescimento_percentual = (crescimento / start_value * 100) if start_value != 0 else 0
                                    growth_metrics[tipo] = crescimento
                                    growth_metrics[f'{tipo}_percentual'] = crescimento_percentual
                            
                            row = {'influencer': influencer_sel, **growth_metrics}
                            crescimento_df = pd.concat([crescimento_df, pd.DataFrame([row])], ignore_index=True)

                    if not crescimento_df.empty:
                        for index, row in crescimento_df.iterrows():
                            st.write(f"### {row['influencer']}")
                            cols = st.columns(4)
                            with cols[0]:
                                st.metric("Novos Seguidores", f"{row['seguidores']:,}", f"{row['seguidores_percentual']:.2f}%")
                            with cols[1]:
                                st.metric("Novas Curtidas", f"{row['curtidas']:,}", f"{row['curtidas_percentual']:.2f}%")
                            with cols[2]:
                                st.metric("Novas Visualizações", f"{row['visualizacoes']:,}", f"{row['visualizacoes_percentual']:.2f}%")
                            with cols[3]:
                                st.metric("Ganhos Estimados (R$)", f"R$ {row['ganhos']:,.2f}", f"{row['ganhos_percentual']:.2f}%")

                    # Gráficos de Evolução
                    st.subheader("Evolução das Métricas")
                    df_evolucao = df[df['tipo'].isin(['seguidores', 'curtidas', 'visualizacoes'])]
                    fig_evolucao = px.line(df_evolucao, x='data', y='valor_escala', color='influencer',
                                           line_dash='tipo', title="Evolução de Seguidores, Curtidas e Visualizações")
                    st.plotly_chart(fig_evolucao, use_container_width=True)
                    
                    # Gráfico de Ganhos Estimados
                    st.subheader("Evolução de Ganhos Estimados (R$)")
                    df_ganhos = df[df['tipo'] == 'ganhos']
                    fig_ganhos = px.line(df_ganhos, x='data', y='valor_escala', color='influencer',
                                         title="Evolução de Ganhos Estimados")
                    st.plotly_chart(fig_ganhos, use_container_width=True)

                    # Gráfico de Taxa de Engajamento
                    st.subheader("Taxa de Engajamento por Influencer")
                    df_pivot = df.pivot_table(index='influencer', columns='tipo', values='valor', aggfunc='mean').reset_index()
                    if 'curtidas' in df_pivot.columns and 'seguidores' in df_pivot.columns:
                        df_pivot['taxa_engajamento_absoluta'] = (df_pivot['curtidas'] / df_pivot['seguidores']).fillna(0)
                        fig_engajamento = px.bar(df_pivot.sort_values(by='taxa_engajamento_absoluta', ascending=False),
                                                 x='influencer', y='taxa_engajamento_absoluta',
                                                 title="Taxa de Engajamento Média (Valor Absoluto)")
                        st.plotly_chart(fig_engajamento, use_container_width=True)
                    else:
                        st.info("Para visualizar a taxa de engajamento, certifique-se de que o histórico inclui dados de 'seguidores' e 'curtidas'.")
                    
                    exportar_excel(df, filename=f"relatorio_tiktok_{data_inicio}_{data_fim}.xlsx")
                else:
                    st.warning("Nenhum dado encontrado para os filtros selecionados.")

    # --- Seção 3: Gerenciamento de Produtos Ganhados em Live ---
    st.header("3. Gerenciamento de Produtos Ganhados em Live")
    if not influencers_disponiveis:
        st.info("Nenhum influencer encontrado no histórico. Adicione um na seção 1 para gerenciar produtos.")
    else:
        tab1, tab2 = st.tabs(["Adicionar Produto", "Consultar Produtos"])
        with tab1:
            st.subheader("Adicionar Produto Manualmente")
            influencer_produto = st.selectbox("Selecione o Influencer", influencers_disponiveis)
            nome_produto = st.text_input("Nome do Produto")
            valor_estimado = st.number_input("Valor Estimado (R$)", min_value=0.0, format="%.2f")
            if st.button("Adicionar Produto Ganhado"):
                if not nome_produto or valor_estimado <= 0:
                    st.warning("Por favor, preencha o nome do produto e o valor estimado.")
                else:
                    if adicionar_produto_live(influencer_produto, nome_produto, valor_estimado):
                        st.success(f"Produto '{nome_produto}' adicionado com sucesso para {influencer_produto}!")
                    else:
                        st.error("Falha ao adicionar o produto.")

        with tab2:
            st.subheader("Consultar Produtos Ganhados")
            influencers_consulta_prod = st.multiselect(
                "Selecione os Influencers para a Consulta de Produtos:",
                influencers_disponiveis
            )
            col_data_inicio_prod, col_data_fim_prod = st.columns(2)
            with col_data_inicio_prod:
                data_inicio_prod = st.date_input("Data de Início da Consulta", datetime.now() - timedelta(days=30))
            with col_data_fim_prod:
                data_fim_prod = st.date_input("Data de Fim da Consulta", datetime.now())

            if st.button("Buscar Produtos Ganhados"):
                if not influencers_consulta_prod:
                    st.warning("Selecione pelo menos um influencer para a consulta.")
                else:
                    df_produtos = get_produtos_ganhados(influencers_consulta_prod, data_inicio_prod, data_fim_prod)
                    if not df_produtos.empty:
                        df_produtos['data'] = pd.to_datetime(df_produtos['data']).dt.strftime('%Y-%m-%d %H:%M:%S')
                        st.dataframe(df_produtos, use_container_width=True)
                        exportar_excel(df_produtos, filename="produtos_ganhados.xlsx")
                    else:
                        st.info("Nenhum produto encontrado para os influencers e período selecionados.")

    st.sidebar.button("Sair", on_click=lambda: st.session_state.clear(), key="logout_sidebar")

# ==============================================
# FLUXO PRINCIPAL DO APLICATIVO
# ==============================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

init_db()

if not st.session_state.logged_in:
    login_section()
else:
    main_app()

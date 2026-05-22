import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import uuid

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO BLINDADA
# ==========================================
st.set_page_config(page_title="Forest CRM", layout="wide")

@st.cache_resource
def init_connection():
    creds_dict = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds_dict)
    # Busca pelo ID EXATO da planilha (ignora problemas de atalho/pasta)
    sheet_id = st.secrets["spreadsheet_id"]
    return client.open_by_key(sheet_id)

try:
    conn = init_connection()
    ws_leads = conn.worksheet("DB_Leads")
    ws_timeline = conn.worksheet("DB_Timeline")
except Exception as e:
    st.error(f"Erro ao conectar com o banco de dados: {e}")
    st.stop()

# ==========================================
# 2. FUNÇÕES DE ARQUITETURA
# ==========================================
def get_leads_data():
    data = ws_leads.get_all_records()
    if not data:
        # Se a planilha estiver vazia, cria um DF vazio com as colunas corretas
        cols = ["ID_Lead", "Nome", "Contato", "Condominio", "Origem", "CPF_CNPJ", "Status_atual", "TS_Criacao", "TS_EmContato", "TS_Assinatura", "TS_Fechado", "TS_Perdido", "Fase_Perda", "Motivo_Perda", "Status_Cadastro", "Unidade"]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(data)

def gerar_id():
    return f"L-{str(uuid.uuid4())[:6].upper()}"

def update_lead_status(lead_id, novo_status, row_index, df_leads, fase_atual):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    col_status = df_leads.columns.get_loc('Status_atual') + 1 
    ws_leads.update_cell(row_index, col_status, novo_status)
    
    mapa_ts = {
        "Em Contato": "TS_EmContato",
        "Assinatura": "TS_Assinatura",
        "Negócio Fechado": "TS_Fechado",
        "Perdido": "TS_Perdido"
    }
    
    if novo_status in mapa_ts:
        col_ts = df_leads.columns.get_loc(mapa_ts[novo_status]) + 1
        ws_leads.update_cell(row_index, col_ts, agora)
    
    if novo_status == "Perdido":
        col_fase_perda = df_leads.columns.get_loc("Fase_Perda") + 1
        ws_leads.update_cell(row_index, col_fase_perda, fase_atual)

# ==========================================
# 3. FRONT-END
# ==========================================
st.sidebar.title("Forest CRM 🌲")
menu = st.sidebar.radio("Navegação", ["Kanban Comercial", "Novo Lead", "Fila de Cadastro"])

df_leads = get_leads_data()

# --- TELA 1: NOVO LEAD ---
if menu == "Novo Lead":
    st.header("Captura de Novo Lead")
    with st.form("form_novo_lead"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome *")
        contato = col2.text_input("Telefone *")
        
        col3, col4 = st.columns(2)
        condominio = col3.text_input("Condomínio *")
        unidade = col4.text_input("Unidade")
        
        origem = st.selectbox("Origem", ["Indicação", "Prospecção", "Campanha SEO"])
        cpf_cnpj = st.text_input("CPF/CNPJ (Opcional nesta fase)")
        
        submit = st.form_submit_button("Criar Lead")
        
        if submit:
            if not nome or not contato or not condominio:
                st.error("Preencha os campos obrigatórios (*).")
            else:
                novo_id = gerar_id()
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 16 colunas na ordem EXATA do CSV atualizado
                nova_linha = [novo_id, nome, contato, condominio, origem, cpf_cnpj, "Aberto", agora, "", "", "", "", "", "", "", unidade]
                ws_leads.append_row(nova_linha)
                st.success(f"Lead {nome} criado com sucesso! (ID: {novo_id})")

# --- TELA 2: KANBAN ---
elif menu == "Kanban Comercial":
    st.header("Funil de Negociação")
    
    if df_leads.empty:
        st.info("O funil está vazio. Cadastre o primeiro lead na aba 'Novo Lead'.")
    else:
        fases = ["Aberto", "Em Contato", "Assinatura"]
        cols = st.columns(len(fases))
        
        for i, fase in enumerate(fases):
            with cols[i]:
                st.subheader(fase)
                leads_fase = df_leads[df_leads['Status_atual'] == fase]
                
                for index, lead in leads_fase.iterrows():
                    with st.expander(f"{lead['Nome']} | {lead['Condominio']} {lead['Unidade']}"):
                        st.caption(f"ID: {lead['ID_Lead']} | Origem: {lead['Origem']}")
                        st.write(f"📞 {lead['Contato']}")
                        
                        pode_avancar = True
                        if fase == "Assinatura" and not lead['CPF_CNPJ']:
                            st.warning("⚠️ CPF/CNPJ necessário para fechamento.")
                            pode_avancar = False
                            novo_cpf = st.text_input("Inserir CPF/CNPJ", key=f"cpf_{lead['ID_Lead']}")
                            if st.button("Salvar CPF", key=f"btn_{lead['ID_Lead']}"):
                                col_cpf = df_leads.columns.get_loc('CPF_CNPJ') + 1
                                ws_leads.update_cell(index + 2, col_cpf, novo_cpf)
                                st.rerun()

                        if pode_avancar:
                            novo_status = st.selectbox(
                                "Mover para:", 
                                ["", "Aberto", "Em Contato", "Assinatura", "Negócio Fechado", "Perdido"], 
                                key=f"status_{lead['ID_Lead']}"
                            )
                            
                            if novo_status == "Perdido":
                                motivo = st.text_input("Motivo da Perda (Obrigatório)", key=f"motivo_{lead['ID_Lead']}")
                                if st.button("Confirmar Perda", key=f"confirm_{lead['ID_Lead']}"):
                                    if motivo:
                                        update_lead_status(lead['ID_Lead'], "Perdido", index + 2, df_leads, fase)
                                        col_motivo = df_leads.columns.get_loc('Motivo_Perda') + 1
                                        ws_leads.update_cell(index + 2, col_motivo, motivo)
                                        st.success("Lead arquivado.")
                                        st.rerun()
                                    else:
                                        st.error("Escreva o motivo.")
                            
                            elif novo_status and novo_status != fase:
                                update_lead_status(lead['ID_Lead'], novo_status, index + 2, df_leads, fase)
                                st.rerun()

# --- TELA 3: FILA DE CADASTRO ---
elif menu == "Fila de Cadastro":
    st.header("Pendentes de Cadastro no Sistema Legado")
    
    if df_leads.empty:
        st.info("Nenhum lead no sistema.")
    else:
        pendentes = df_leads[(df_leads['Status_atual'] == 'Negócio Fechado') & (df_leads['Status_Cadastro'] != 'Concluído')]
        
        if pendentes.empty:
            st.info("Nenhum lead pendente de cadastro.")
        else:
            for index, lead in pendentes.iterrows():
                with st.container(border=True):
                    st.subheader(f"{lead['Nome']} - {lead['Condominio']} {lead['Unidade']}")
                    st.code(f"Nome: {lead['Nome']}\nTelefone: {lead['Contato']}\nCPF/CNPJ: {lead['CPF_CNPJ']}\nCondomínio: {lead['Condominio']}\nUnidade: {lead['Unidade']}")
                    
                    if st.button("Marcar como Cadastrado", key=f"cad_{lead['ID_Lead']}"):
                        col_status_cad = df_leads.columns.get_loc('Status_Cadastro') + 1
                        ws_leads.update_cell(index + 2, col_status_cad, "Concluído")
                        st.rerun()

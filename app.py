import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import uuid
import json

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO COM O BANCO
# ==========================================
st.set_page_config(page_title="Forest CRM", layout="wide")

# Conexão com Google Sheets usando Streamlit Secrets
@st.cache_resource
def init_connection():
    # O conteúdo do seu arquivo JSON deve ser colado no st.secrets do Streamlit
    creds_dict = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds_dict)
    return client.open("CRM Forest") # Nome exato da sua planilha

conn = init_connection()
ws_leads = conn.worksheet("DB_Leads")
ws_timeline = conn.worksheet("DB_Timeline")

# ==========================================
# 2. FUNÇÕES DE ARQUITETURA DE DADOS
# ==========================================
def get_leads_data():
    data = ws_leads.get_all_records()
    return pd.DataFrame(data)

def gerar_id():
    return f"L-{str(uuid.uuid4())[:6].upper()}"

def update_lead_status(lead_id, novo_status, row_index, df_leads, fase_atual):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Atualiza o Status na planilha (Coluna G, considerando ordem alfabética do seu input)
    # Ajuste o número da coluna (ex: col=7) de acordo com a posição exata de Status_atual na sua planilha
    col_status = df_leads.columns.get_loc('Status_atual') + 1 
    ws_leads.update_cell(row_index, col_status, novo_status)
    
    # Mapeamento dinâmico de Timestamps
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
# 3. INTERFACE E ROTEAMENTO (FRONT-END)
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
        condominio = st.text_input("Condomínio *")
        origem = st.selectbox("Origem", ["Indicação", "Prospecção", "Campanha SEO"])
        cpf_cnpj = st.text_input("CPF/CNPJ (Opcional nesta fase)")
        
        submit = st.form_submit_button("Criar Lead")
        
        if submit:
            if not nome or not contato or not condominio:
                st.error("Preencha os campos obrigatórios (*).")
            else:
                novo_id = gerar_id()
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # A ordem dos dados DEVE ser exatamente a das colunas da sua DB_Leads
                nova_linha = [novo_id, nome, contato, condominio, origem, cpf_cnpj, "Aberto", agora, "", "", "", "", "", "", ""]
                ws_leads.append_row(nova_linha)
                st.success(f"Lead {nome} criado com sucesso! (ID: {novo_id})")

# --- TELA 2: KANBAN ---
elif menu == "Kanban Comercial":
    st.header("Funil de Negociação")
    st.button("🔄 Atualizar Dados")
    
    fases = ["Aberto", "Em Contato", "Assinatura"]
    cols = st.columns(len(fases))
    
    for i, fase in enumerate(fases):
        with cols[i]:
            st.subheader(fase)
            leads_fase = df_leads[df_leads['Status_atual'] == fase]
            
            for index, lead in leads_fase.iterrows():
                with st.expander(f"{lead['Nome']} | {lead['Condominio']}"):
                    st.caption(f"ID: {lead['ID_Lead']} | Origem: {lead['Origem']}")
                    st.write(f"📞 {lead['Contato']}")
                    
                    # Trava Anti-Fricção: Bloqueia avanço pra assinatura/fechamento se não tiver CPF
                    pode_avancar = True
                    if fase == "Assinatura" and not lead['CPF_CNPJ']:
                        st.warning("⚠️ CPF/CNPJ necessário para fechamento.")
                        pode_avancar = False
                        novo_cpf = st.text_input("Inserir CPF/CNPJ", key=f"cpf_{lead['ID_Lead']}")
                        if st.button("Salvar CPF", key=f"btn_{lead['ID_Lead']}"):
                            col_cpf = df_leads.columns.get_loc('CPF_CNPJ') + 1
                            ws_leads.update_cell(index + 2, col_cpf, novo_cpf) # +2 por causa do cabeçalho
                            st.rerun()

                    # Dropdown para mover status
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
                                    # Linha real da planilha é o index do dataframe + 2 (1 do header + 1 por ser index 0)
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
    
    # Filtra: Negócio Fechado E (Status_Cadastro vazio ou diferente de 'Concluído')
    pendentes = df_leads[(df_leads['Status_atual'] == 'Negócio Fechado') & (df_leads['Status_Cadastro'] != 'Concluído')]
    
    if pendentes.empty:
        st.info("Nenhum lead pendente de cadastro.")
    else:
        for index, lead in pendentes.iterrows():
            with st.container(border=True):
                st.subheader(f"{lead['Nome']} - {lead['Condominio']}")
                st.code(f"Nome: {lead['Nome']}\nTelefone: {lead['Contato']}\nCPF/CNPJ: {lead['CPF_CNPJ']}\nCondomínio: {lead['Condominio']}")
                
                if st.button(f"Marcar como Cadastrado", key=f"cad_{lead['ID_Lead']}"):
                    col_status_cad = df_leads.columns.get_loc('Status_Cadastro') + 1
                    ws_leads.update_cell(index + 2, col_status_cad, "Concluído")
                    st.rerun()

import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import uuid
import re

# ==========================================
# 1. CONFIGURAÇÃO E CONEXÃO BLINDADA
# ==========================================
st.set_page_config(page_title="Forest CRM", layout="wide")

def init_connection():
    creds_dict = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds_dict)
    sheet_id = "1Wgzdmr94dnBo2HqadmUWXWyodcsA7pTIJRbIvvvbiWE" 
    return client.open_by_key(sheet_id)

try:
    conn = init_connection()
    ws_leads = conn.worksheet("DB_Leads")
    ws_timeline = conn.worksheet("DB_Timeline")
    ws_notas = conn.worksheet("DB_Comentarios")
except Exception as e:
    st.error(f"🚨 ERRO DE CONEXÃO: Verifique se a aba DB_Comentarios foi criada. Erro técnico: {type(e).__name__} - {e}")
    st.stop()

# ==========================================
# 2. MOTOR DE DADOS E FORMATAÇÃO
# ==========================================
def get_leads_data():
    data = ws_leads.get_all_records()
    if not data:
        cols = ["ID_Lead", "Nome", "Contato", "Condominio", "Cidade", "Origem", "CPF_CNPJ", "Status_atual", "TS_Criacao", "TS_EmContato", "TS_Fechamento", "TS_Concluido", "TS_Perdido", "Fase_Perda", "Motivo_Perda", "Status_Cadastro"]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(data)

def get_notas_data():
    data = ws_notas.get_all_records()
    if not data:
        return pd.DataFrame(columns=["DataHora", "ID_Lead", "Nota"])
    return pd.DataFrame(data)

def gerar_id():
    return f"L-{str(uuid.uuid4())[:6].upper()}"

def formatar_telefone(telefone):
    n = re.sub(r'\D', '', telefone)
    if len(n) == 11: return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    if len(n) == 10: return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    return telefone

def formatar_cpf_cnpj(doc):
    if not doc: return ""
    n = re.sub(r'\D', '', doc)
    if len(n) == 11: return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
    if len(n) == 14: return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    return doc

def calc_dias(ts_str):
    if not ts_str or ts_str == "": return 0
    try:
        data_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - data_ts).days
    except:
        return 0

def registrar_timeline(lead_id, nome, fase_anterior, nova_fase):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws_timeline.append_row([agora, lead_id, nome, fase_anterior, nova_fase])

def update_lead_status(lead_id, nome, novo_status, row_index, df_leads, fase_atual):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    col_status = df_leads.columns.get_loc('Status_atual') + 1 
    ws_leads.update_cell(row_index, col_status, novo_status)
    
    mapa_ts = {
        "Em Contato": "TS_EmContato",
        "Fechamento": "TS_Fechamento",
        "Concluído": "TS_Concluido",
        "Perdido": "TS_Perdido"
    }
    
    if novo_status in mapa_ts:
        col_ts = df_leads.columns.get_loc(mapa_ts[novo_status]) + 1
        ws_leads.update_cell(row_index, col_ts, agora)
    
    if novo_status == "Perdido":
        col_fase_perda = df_leads.columns.get_loc("Fase_Perda") + 1
        ws_leads.update_cell(row_index, col_fase_perda, fase_atual)
        
    registrar_timeline(lead_id, nome, fase_atual, novo_status)

# ==========================================
# 3. INTERFACE (FRONT-END)
# ==========================================
st.sidebar.title("Forest CRM 🌲")
menu = st.sidebar.radio("Navegação", ["Kanban Comercial", "Novo Lead", "Fila de Cadastro", "Relatórios & Auditoria"])

df_leads = get_leads_data()
df_notas = get_notas_data()

# --- TELA 1: NOVO LEAD ---
if menu == "Novo Lead":
    st.header("Captura de Novo Lead")
    with st.form("form_novo_lead"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome *")
        contato = col2.text_input("Telefone (Apenas números) *")
        
        col3, col4 = st.columns(2)
        condominio = col3.text_input("Condomínio (Opcional)")
        cidade = col4.text_input("Cidade (Opcional)")
        
        col5, col6 = st.columns(2)
        origem = col5.selectbox("Origem", ["Indicação", "Prospecção", "Campanha SEO"])
        cpf_cnpj = col6.text_input("CPF/CNPJ (Apenas números - Opcional)")
        
        submit = st.form_submit_button("Criar Lead")
        
        if submit:
            if not nome or not contato:
                st.error("Nome e Telefone são obrigatórios.")
            else:
                novo_id = gerar_id()
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tel_formatado = formatar_telefone(contato)
                doc_formatado = formatar_cpf_cnpj(cpf_cnpj)
                
                nova_linha = [novo_id, nome, tel_formatado, condominio, cidade, origem, doc_formatado, "Em Aberto", agora, "", "", "", "", "", ""]
                ws_leads.append_row(nova_linha)
                registrar_timeline(novo_id, nome, "Criação", "Em Aberto")
                st.success(f"Lead {nome} criado com sucesso! (ID: {novo_id})")

# --- TELA 2: KANBAN ---
elif menu == "Kanban Comercial":
    st.header("Funil de Negociação")
    
    if df_leads.empty:
        st.info("O funil está vazio. Cadastre o primeiro lead.")
    else:
        # MÉTRICAS DE TOPO
        ativos = len(df_leads[~df_leads['Status_atual'].isin(['Concluído', 'Perdido'])])
        concluidos = len(df_leads[df_leads['Status_atual'] == 'Concluído'])
        st.markdown(f"**Métricas Atuais:** 🎯 {ativos} Leads Ativos | 🏆 {concluidos} Negócios Concluídos")
        st.divider()

        # BUSCA RÁPIDA
        termo_busca = st.text_input("🔍 Buscar Lead (Nome ou Telefone):", "").strip().lower()
        if termo_busca:
            df_leads = df_leads[df_leads['Nome'].str.lower().str.contains(termo_busca) | df_leads['Contato'].str.contains(termo_busca)]

        fases = ["Em Aberto", "Em Contato", "Fechamento", "Concluído", "Perdido"]
        cols = st.columns(len(fases))
        
        for i, fase in enumerate(fases):
            with cols[i]:
                st.subheader(fase)
                leads_fase = df_leads[df_leads['Status_atual'] == fase]
                
                for index, lead in leads_fase.iterrows():
                    local_info = lead['Condominio'] if lead['Condominio'] else (lead['Cidade'] if lead['Cidade'] else "Sem Local")
                    
                    with st.expander(f"{lead['Nome']} | {local_info}"):
                        
                        # CÁLCULO DE TEMPO
                        dias_total = calc_dias(lead['TS_Criacao'])
                        ts_fase_atual = lead.get(f'TS_{fase.replace(" ", "")}', lead['TS_Criacao'] if fase == "Em Aberto" else "")
                        if fase == "Fechamento": ts_fase_atual = lead['TS_Fechamento']
                        elif fase == "Concluído": ts_fase_atual = lead['TS_Concluido']
                        elif fase == "Perdido": ts_fase_atual = lead['TS_Perdido']
                        
                        dias_fase = calc_dias(ts_fase_atual)
                        
                        st.caption(f"ID: {lead['ID_Lead']} | Origem: {lead['Origem']}")
                        st.write(f"📞 {lead['Contato']}")
                        if lead['Cidade']: st.write(f"📍 Cidade: {lead['Cidade']}")
                        if lead['CPF_CNPJ']: st.write(f"🪪 Doc: {lead['CPF_CNPJ']}")
                        st.markdown(f"⏳ **{dias_total} dias** no funil | 📍 **{dias_fase} dias** nesta etapa")
                        
                        # --- ABAS INTERNAS DO CARD ---
                        tab_status, tab_editar, tab_notas = st.tabs(["Mover Etapa", "✏️ Editar", "💬 Notas"])
                        
                        with tab_status:
                            if fase not in ["Concluído", "Perdido"]:
                                novo_status = st.selectbox(
                                    "Mover para:", 
                                    ["", "Em Aberto", "Em Contato", "Fechamento", "Concluído", "Perdido"], 
                                    key=f"status_{lead['ID_Lead']}"
                                )
                                
                                if novo_status == "Perdido":
                                    motivo = st.text_input("Motivo da Perda (Obrigatório)", key=f"motivo_{lead['ID_Lead']}")
                                    if st.button("Confirmar Perda", key=f"confirm_{lead['ID_Lead']}"):
                                        if motivo:
                                            update_lead_status(lead['ID_Lead'], lead['Nome'], "Perdido", index + 2, df_leads, fase)
                                            col_motivo = df_leads.columns.get_loc('Motivo_Perda') + 1
                                            ws_leads.update_cell(index + 2, col_motivo, motivo)
                                            st.success("Lead arquivado.")
                                            st.rerun()
                                        else:
                                            st.error("Escreva o motivo.")
                                
                                elif novo_status and novo_status != fase:
                                    update_lead_status(lead['ID_Lead'], lead['Nome'], novo_status, index + 2, df_leads, fase)
                                    st.rerun()
                            else:
                                st.info("Leads finalizados não podem mudar de etapa por aqui.")

                        with tab_editar:
                            up_nome = st.text_input("Nome", value=lead['Nome'], key=f"u_nome_{lead['ID_Lead']}")
                            up_contato = st.text_input("Telefone", value=lead['Contato'], key=f"u_tel_{lead['ID_Lead']}")
                            up_cond = st.text_input("Condomínio", value=lead['Condominio'], key=f"u_cond_{lead['ID_Lead']}")
                            up_cid = st.text_input("Cidade", value=lead['Cidade'], key=f"u_cid_{lead['ID_Lead']}")
                            up_doc = st.text_input("CPF/CNPJ", value=lead['CPF_CNPJ'], key=f"u_doc_{lead['ID_Lead']}")
                            
                            if st.button("Salvar Alterações", key=f"save_btn_{lead['ID_Lead']}"):
                                r_idx = index + 2
                                ws_leads.update_cell(r_idx, df_leads.columns.get_loc('Nome') + 1, up_nome)
                                ws_leads.update_cell(r_idx, df_leads.columns.get_loc('Contato') + 1, formatar_telefone(up_contato))
                                ws_leads.update_cell(r_idx, df_leads.columns.get_loc('Condominio') + 1, up_cond)
                                ws_leads.update_cell(r_idx, df_leads.columns.get_loc('Cidade') + 1, up_cid)
                                ws_leads.update_cell(r_idx, df_leads.columns.get_loc('CPF_CNPJ') + 1, formatar_cpf_cnpj(up_doc))
                                st.success("Dados salvos!")
                                st.rerun()
                                
                        with tab_notas:
                            notas_do_lead = df_notas[df_notas['ID_Lead'] == lead['ID_Lead']]
                            if not notas_do_lead.empty:
                                for _, nota in notas_do_lead.iterrows():
                                    st.caption(f"🕒 {nota['DataHora']}")
                                    st.write(f"💬 {nota['Nota']}")
                                    st.divider()
                            else:
                                st.write("Nenhuma anotação ainda.")
                                
                            nova_nota = st.text_area("Nova anotação:", key=f"txt_nota_{lead['ID_Lead']}")
                            if st.button("Salvar Nota", key=f"btn_nota_{lead['ID_Lead']}"):
                                if nova_nota:
                                    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    ws_notas.append_row([agora, lead['ID_Lead'], nova_nota])
                                    st.success("Nota salva!")
                                    st.rerun()

# --- TELA 3: FILA DE CADASTRO ---
elif menu == "Fila de Cadastro":
    st.header("Pendentes de Cadastro")
    if df_leads.empty:
        st.info("Nenhum lead no sistema.")
    else:
        pendentes = df_leads[(df_leads['Status_atual'] == 'Concluído') & (df_leads['Status_Cadastro'] != 'Concluído')]
        if pendentes.empty:
            st.info("Nenhum lead pendente de cadastro.")
        else:
            for index, lead in pendentes.iterrows():
                with st.container(border=True):
                    st.subheader(f"{lead['Nome']}")
                    st.code(f"Nome: {lead['Nome']}\nTelefone: {lead['Contato']}\nCPF/CNPJ: {lead['CPF_CNPJ']}\nCondomínio: {lead['Condominio']}\nCidade: {lead['Cidade']}")
                    if st.button("Marcar como Cadastrado", key=f"cad_{lead['ID_Lead']}"):
                        col_status_cad = df_leads.columns.get_loc('Status_Cadastro') + 1
                        ws_leads.update_cell(index + 2, col_status_cad, "Concluído")
                        st.rerun()

# --- TELA 4: RELATÓRIOS E AUDITORIA ---
elif menu == "Relatórios & Auditoria":
    st.header("Inteligência e Histórico")
    
    if df_leads.empty:
        st.info("Dados insuficientes para gerar relatórios.")
    else:
        st.subheader("Panorama de Perdas")
        perdas = df_leads[df_leads['Status_atual'] == 'Perdido']
        if not perdas.empty:
            st.dataframe(perdas[['Nome', 'Condominio', 'Cidade', 'Fase_Perda', 'Motivo_Perda']], use_container_width=True)
        else:
            st.write("Nenhuma perda registrada.")
            
        st.divider()
        st.subheader("Auditoria de Timeline (Últimas Movimentações)")
        try:
            data_timeline = ws_timeline.get_all_records()
            if data_timeline:
                df_time = pd.DataFrame(data_timeline)
                st.dataframe(df_time.iloc[::-1], use_container_width=True) 
            else:
                st.write("Timeline vazia.")
        except:
            st.write("Erro ao carregar a aba DB_Timeline. Verifique se os cabeçalhos existem.")

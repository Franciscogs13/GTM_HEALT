import streamlit as st
import json
import pandas as pd
import plotly.express as px
from io import BytesIO
from gtm_api import GTMService
from google_auth_oauthlib.flow import Flow
import datetime

st.set_page_config(
    page_title="GTM Health Dashboard",
    page_icon="🩺",
    layout="wide"
)

# --- Funções Auxiliares ---
def to_excel(df_summary, df_inventory):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df_summary.to_excel(writer, index=False, sheet_name='Resumo da Versão')
    df_inventory.to_excel(writer, index=False, sheet_name='Detalhes')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- CONFIGURAÇÃO OAUTH WEB ---
try:
    # Lê a string do secrets.toml e converte para dicionário (JSON)
    client_config = json.loads(st.secrets["google_oauth"]["client_secrets"])
except Exception as e:
    st.error("⚠️ Erro ao ler .streamlit/secrets.toml. Certifique-se de que o arquivo existe e contém a chave 'client_secrets'.")
    st.stop()

scopes = ['https://www.googleapis.com/auth/tagmanager.readonly']
redirect_uri = "https://gtm-health-check.streamlit.app"

def get_flow():
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=redirect_uri
    )

@st.cache_resource
def get_oauth_cache():
    # Cache global compartilhado entre abas/sessões para manter o PKCE
    return {}

# --- CAPTURA O RETORNO DO LOGIN ---
if 'code' in st.query_params:
    try:
        flow = get_flow()
        state = st.query_params.get('state')
        
        # Restaura o code_verifier usando o cache global para contornar a perda de sessão em nova aba
        cache = get_oauth_cache()
        if state and state in cache:
            flow.code_verifier = cache.pop(state)
            
        flow.fetch_token(code=st.query_params['code'])
        st.session_state.credentials = flow.credentials
        
        # Limpa os parâmetros da URL
        st.query_params.clear()
        if 'auth_url' in st.session_state:
            del st.session_state['auth_url']
                
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao processar o login: {e}")

# --- UI Sidebar ---
st.sidebar.title("Configurações OAuth")
st.sidebar.markdown("Autentique-se com sua conta Google para acessar o GTM.")

# Se o usuário NÃO está logado
if 'credentials' not in st.session_state:
    st.info("👈 Siga as instruções na barra lateral para começar.")
    st.markdown("""
    ### Bem-vindo ao GTM Health Dashboard
    Esta ferramenta permite realizar auditorias técnicas em seus contêineres do Google Tag Manager.
    
    **Primeiros Passos:**
    1. Certifique-se de que o arquivo `.streamlit/secrets.toml` está configurado.
    2. Clique em "Autenticar com Google" no menu lateral.
    3. Uma janela do navegador se abrirá para você conceder acesso.
    """)
    
    # Gera o link seguro do Google garantindo persistência do state (PKCE)
    if 'auth_url' not in st.session_state:
        flow = get_flow()
        auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
        st.session_state['auth_url'] = auth_url
        
        if hasattr(flow, 'code_verifier'):
            # Salva no cache global usando o state como chave
            get_oauth_cache()[state] = flow.code_verifier
            
    st.sidebar.link_button("🔐 Autenticar com Google", st.session_state['auth_url'])

# Se o usuário ESTÁ logado
else:
    st.sidebar.success("✅ Conectado com sucesso!")
    if st.sidebar.button("Sair (Logout)"):
        del st.session_state['credentials']
        if 'accounts' in st.session_state:
            del st.session_state['accounts']
        st.rerun()
        
    # Instancia GTMService com as credenciais salvas
    gtm = GTMService(credentials=st.session_state.credentials)
    
    # Recupera as contas da sessão ou busca novamente se não existirem
    if 'accounts' not in st.session_state:
        try:
            st.session_state.accounts = gtm.get_accounts()
        except Exception as e:
            st.sidebar.error(f"Erro ao buscar contas: {e}")
            st.session_state.accounts = []

    accounts = st.session_state.accounts

    if not accounts:
        st.sidebar.warning("Nenhuma conta GTM encontrada para este usuário.")
    else:
        # Seleção de Conta
        account_options = {acc['name']: acc['accountId'] for acc in accounts}
        selected_account_name = st.sidebar.selectbox("Selecione a Conta", options=list(account_options.keys()))
        
        if selected_account_name:
            account_id = account_options[selected_account_name]
            account_path = f"accounts/{account_id}"
            
            # Busca Contêineres
            containers = gtm.get_containers(account_path)
            container_options = {cont['name']: cont['containerId'] for cont in containers}
            
            selected_container_name = st.sidebar.selectbox("Selecione o Contêiner", options=list(container_options.keys()))
            
            if selected_container_name:
                container_id = container_options[selected_container_name]
                container_path = f"{account_path}/containers/{container_id}"
                
                num_versions_history = st.sidebar.slider(
                    "Histórico de Versões", 
                    min_value=3, 
                    max_value=50, 
                    value=5, 
                    step=1, 
                    help="Quantas versões analisar no gráfico. Valores altos podem deixar o carregamento mais lento."
                )
                
                if st.sidebar.button("Auditar Contêiner"):
                    st.session_state.auditing_container = container_id
                    
                if st.session_state.get('auditing_container') == container_id:
                    with st.spinner("Buscando dados da última versão publicada..."):
                        try:
                            # Busca a versão Live
                            live_version = gtm.get_latest_published_version(container_path)
                            
                            # Extração de dados da versão
                            version_name = live_version.get('name', 'N/A')
                            version_id = live_version.get('containerVersionId', 'N/A')
                            
                            tags = live_version.get('tag', [])
                            triggers = live_version.get('trigger', [])
                            variables = live_version.get('variable', [])
                            
                            num_tags = len(tags)
                            num_triggers = len(triggers)
                            num_variables = len(variables)
                            
                            script_size_kb = gtm.calculate_script_size(live_version)
                            complexity_ms = gtm.calculate_complexity(num_tags, num_variables)
                            
                            # Identificar tags sem acionador (órfãs)
                            orphan_tags = sum(1 for tag in tags if not tag.get('firingTriggerId'))
                            
                            # --- Renderização do Dashboard Principal ---
                            st.title(f"Dashboard de Saúde: {selected_container_name}")
                            st.markdown(f"**Versão:** {version_name} (ID: {version_id})")
                            
                            st.markdown("### KPIs Principais")
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Tags", num_tags)
                            col2.metric("Triggers", num_triggers)
                            col3.metric("Variables", num_variables)
                            col4.metric("Complexidade Est. (ms)", f"{complexity_ms:.1f}")
                            
                            # --- Alertas Inteligentes ---
                            st.markdown("### Status do Contêiner")
                            if script_size_kb > 200:
                                st.error(f"🔴 **Alerta de Tamanho:** O contêiner tem {script_size_kb:.2f} KB. Acima do recomendado (200 KB).")
                            elif script_size_kb > 150:
                                st.warning(f"🟡 **Aviso de Tamanho:** O contêiner tem {script_size_kb:.2f} KB. Próximo do limite de alerta.")
                            else:
                                st.success(f"🟢 **Tamanho Saudável:** O contêiner tem {script_size_kb:.2f} KB.")
                                
                            if orphan_tags > 0:
                                st.warning(f"🟡 **Aviso de Tags Órfãs:** Encontradas {orphan_tags} tags sem acionadores vinculados.")
                            else:
                                st.success("🟢 Nenhuma tag órfã encontrada.")

                            st.markdown("---")
                            
                            # --- Gráficos ---
                            col_chart1, col_chart2 = st.columns(2)
                            
                            with col_chart1:
                                st.markdown("#### Composição do Contêiner")
                                pie_data = pd.DataFrame({
                                    'Elemento': ['Tags', 'Triggers', 'Variáveis'],
                                    'Quantidade': [num_tags, num_triggers, num_variables]
                                })
                                fig_pie = px.pie(pie_data, values='Quantidade', names='Elemento', hole=0.4)
                                st.plotly_chart(fig_pie, use_container_width=True)
                                
                            with col_chart2:
                                st.markdown(f"#### Histórico de Performance (Últimas {num_versions_history} Versões)")
                                versions_history = gtm.get_versions(container_path)
                                if versions_history:
                                    last_versions = sorted(versions_history, key=lambda x: int(x.get('containerVersionId', 0)), reverse=True)[:num_versions_history]
                                    
                                    hist_data = []
                                    for v in last_versions:
                                        v_id = v.get('containerVersionId', 'N/A')
                                        try:
                                            v_path = v.get('path')
                                            full_v = gtm.service.accounts().containers().versions().get(path=v_path).execute()
                                            v_size = gtm.calculate_script_size(full_v)
                                        except Exception:
                                            v_size = 0
                                            
                                        hist_data.append({'Versão': f"v{v_id}", 'Tamanho (KB)': v_size})
                                        
                                    df_hist = pd.DataFrame(hist_data)
                                    df_hist = df_hist.iloc[::-1]
                                    
                                    fig_bar = px.bar(df_hist, x='Versão', y='Tamanho (KB)', text='Tamanho (KB)')
                                    fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                                    st.plotly_chart(fig_bar, use_container_width=True)
                                else:
                                    st.info("Não há histórico de versões suficiente para exibir.")

                            # --- Tabelas de Dados ---
                            st.markdown("### Dados da Versão")
                            
                            st.markdown("#### Resumo da Versão")
                            agora = datetime.datetime.now()
                            data_coleta = agora.strftime("%d/%m/%Y")
                            hora_coleta = agora.strftime("%H:%M")
                            
                            inventory_summary = [{
                                'Data da Coleta': data_coleta,
                                'Hora da Coleta': hora_coleta,
                                'Versão GTM': version_id,
                                'Tempo de execução (ms)': round(complexity_ms, 2),
                                'Script Size (KB)': round(script_size_kb, 2),
                                'Qtd Tags': num_tags,
                                'Qtd triggers': num_triggers,
                                'Qtd variaveis': num_variables
                            }]
                            df_summary = pd.DataFrame(inventory_summary)
                            st.dataframe(df_summary, use_container_width=True, hide_index=True)

                            st.markdown("#### Inventário de Elementos")
                            inventory = gtm.extract_inventory(live_version)
                            df_inventory = pd.DataFrame(inventory)
                            st.dataframe(df_inventory, use_container_width=True, hide_index=True)
                            
                            # Botões de Exportação
                            st.markdown("#### Exportar Dados")
                            col_btn1, col_btn2 = st.columns([1, 1])
                            
                            with col_btn1:
                                csv_summary = df_summary.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    label="Baixar Resumo (CSV)",
                                    data=csv_summary,
                                    file_name=f"gtm_resumo_v{version_id}.csv",
                                    mime="text/csv",
                                )
                                
                            with col_btn2:
                                try:
                                    excel_data = to_excel(df_summary, df_inventory)
                                    st.download_button(
                                        label="Baixar Planilha Completa (Excel)",
                                        data=excel_data,
                                        file_name=f"gtm_planilha_v{version_id}.xlsx",
                                        mime="application/vnd.ms-excel",
                                    )
                                except ImportError:
                                    st.warning("Biblioteca 'xlsxwriter' não instalada para exportação. Instale-a com 'pip install xlsxwriter'.")

                        except Exception as e:
                            st.error(f"Erro ao processar auditoria: {e}")
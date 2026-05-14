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
    if st.sidebar.button("🚪 Sair (Logout)"):
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
                
                # Histórico de Versões buscado para Selectbox e Comparativo
                if 'versions_history_cache' not in st.session_state:
                    st.session_state.versions_history_cache = {}
                    
                cache_key = container_path
                if cache_key in st.session_state.versions_history_cache:
                    versions_history = st.session_state.versions_history_cache[cache_key]
                else:
                    versions_history = gtm.get_versions(container_path)
                    st.session_state.versions_history_cache[cache_key] = versions_history
                
                selected_version_path = None
                if versions_history:
                    sorted_versions_desc = sorted(versions_history, key=lambda x: int(x.get('containerVersionId', 0)), reverse=True)
                    version_options = {f"v{v.get('containerVersionId')} - {v.get('name', 'Sem nome')}": v.get('path') for v in sorted_versions_desc}
                    selected_version_name = st.sidebar.selectbox("Versão para Auditoria", options=list(version_options.keys()))
                    if selected_version_name:
                        selected_version_path = version_options[selected_version_name]
                        
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
                    with st.spinner("Buscando dados da versão selecionada..."):
                        try:
                            # Busca a versão selecionada pelo usuário
                            if selected_version_path:
                                live_version = gtm.service.accounts().containers().versions().get(path=selected_version_path).execute()
                            else:
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
                            orphan_tags_list = [{'Nome da Tag': tag.get('name', 'N/A'), 'Tipo': tag.get('type', 'N/A')} for tag in tags if not tag.get('firingTriggerId') or len(tag.get('firingTriggerId')) == 0]
                            orphan_tags = len(orphan_tags_list)
                            
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
                                with st.expander("Ver Tags Órfãs"):
                                    st.dataframe(pd.DataFrame(orphan_tags_list), use_container_width=True, hide_index=True)
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
                                if 'versions_size_cache' not in st.session_state:
                                    st.session_state.versions_size_cache = {}
                                
                                if versions_history:
                                    sorted_all_versions = sorted(versions_history, key=lambda x: int(x.get('containerVersionId', 0)), reverse=True)
                                    last_versions = sorted_all_versions[:num_versions_history]
                                    
                                    hist_data = []
                                    for v in last_versions:
                                        v_id = v.get('containerVersionId', 'N/A')
                                        
                                        if v_id in st.session_state.versions_size_cache:
                                            v_size = st.session_state.versions_size_cache[v_id]
                                        else:
                                            try:
                                                v_path = v.get('path')
                                                full_v = gtm.service.accounts().containers().versions().get(path=v_path).execute()
                                                v_size = gtm.calculate_script_size(full_v)
                                                st.session_state.versions_size_cache[v_id] = v_size
                                            except Exception:
                                                v_size = None
                                                
                                        if v_size is not None:
                                            hist_data.append({'Versão': f"v{v_id}", 'Tamanho (KB)': v_size})
                                        
                                    df_hist = pd.DataFrame(hist_data)
                                    if not df_hist.empty:
                                        df_hist = df_hist.iloc[::-1]
                                        
                                        fig_bar = px.bar(df_hist, x='Versão', y='Tamanho (KB)', text='Tamanho (KB)')
                                        fig_bar.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                                        st.plotly_chart(fig_bar, use_container_width=True)
                                    else:
                                        st.info("Não foi possível carregar os dados de tamanho para estas versões.")
                                else:
                                    st.info("Não há histórico de versões suficiente para exibir.")

                            st.markdown("---")

                            # --- Comparativo de Versões (Live vs Live-1) ---
                            sorted_versions = sorted(versions_history, key=lambda x: int(x.get('containerVersionId', 0)), reverse=True) if versions_history else []
                            live_v_id_int = int(version_id) if str(version_id).isdigit() else 0
                            prev_v_header = next((v for v in sorted_versions if int(v.get('containerVersionId', 0)) < live_v_id_int), None)
                            
                            if prev_v_header:
                                prev_v_id = prev_v_header.get('containerVersionId')
                                st.markdown(f"### Mudanças Recentes (Versão Escolhida {version_id} vs Versão Anterior {prev_v_id})")
                                with st.spinner(f"Buscando versão anterior (v{prev_v_id}) para comparativo..."):
                                    try:
                                        # Verifica cache para a versão anterior completa
                                        if 'full_version_cache' not in st.session_state:
                                            st.session_state.full_version_cache = {}
                                            
                                        if prev_v_id in st.session_state.full_version_cache:
                                            prev_full_v = st.session_state.full_version_cache[prev_v_id]
                                        else:
                                            prev_v_path = prev_v_header.get('path')
                                            prev_full_v = gtm.service.accounts().containers().versions().get(path=prev_v_path).execute()
                                            st.session_state.full_version_cache[prev_v_id] = prev_full_v
                                        
                                        def compare_elements(live_elements, prev_elements, id_key):
                                            live_dict = {e.get(id_key): e for e in live_elements}
                                            prev_dict = {e.get(id_key): e for e in prev_elements}
                                            
                                            added = []
                                            removed = []
                                            changed = []
                                            
                                            for eid, e in live_dict.items():
                                                if eid not in prev_dict:
                                                    added.append({'Elemento': e.get('name', eid)})
                                                else:
                                                    # Ignora chaves internas que mudam entre versões mas não representam alteração funcional
                                                    ignore_keys = ['fingerprint', 'path', 'workspaceId', 'containerVersionId']
                                                    e_clean = {k: v for k, v in e.items() if k not in ignore_keys}
                                                    prev_e_clean = {k: v for k, v in prev_dict[eid].items() if k not in ignore_keys}
                                                    
                                                    if e_clean != prev_e_clean:
                                                        element_name = e.get('name', eid)
                                                        
                                                        all_keys = set(e_clean.keys()).union(prev_e_clean.keys())
                                                        for k in all_keys:
                                                            val_atual = e_clean.get(k)
                                                            val_anterior = prev_e_clean.get(k)
                                                            if val_atual != val_anterior:
                                                                if k == 'parameter':
                                                                    # Comparação inteligente dos parâmetros (que são listas de dicionários)
                                                                    params_atuais = {p.get('key'): p.get('value') for p in (val_atual or []) if 'key' in p}
                                                                    params_anteriores = {p.get('key'): p.get('value') for p in (val_anterior or []) if 'key' in p}
                                                                    all_p_keys = set(params_atuais.keys()).union(params_anteriores.keys())
                                                                    for pk in all_p_keys:
                                                                        p_atu = params_atuais.get(pk)
                                                                        p_ant = params_anteriores.get(pk)
                                                                        if p_atu != p_ant:
                                                                            changed.append({
                                                                                'Elemento': element_name,
                                                                                'Campo Alterado': f"Parâmetro: {pk}",
                                                                                'Valor Anterior (v. Anterior)': str(p_ant) if p_ant is not None else "(Não existia)",
                                                                                'Valor Atual (v. Atual)': str(p_atu) if p_atu is not None else "(Removido)"
                                                                            })
                                                                elif k == 'firingTriggerId':
                                                                    changed.append({
                                                                        'Elemento': element_name,
                                                                        'Campo Alterado': "Acionadores de disparo",
                                                                        'Valor Anterior (v. Anterior)': ", ".join(val_anterior) if val_anterior else "Nenhum",
                                                                        'Valor Atual (v. Atual)': ", ".join(val_atual) if val_atual else "Nenhum"
                                                                    })
                                                                elif k == 'blockingTriggerId':
                                                                    changed.append({
                                                                        'Elemento': element_name,
                                                                        'Campo Alterado': "Acionadores de bloqueio (Exceções)",
                                                                        'Valor Anterior (v. Anterior)': ", ".join(val_anterior) if val_anterior else "Nenhum",
                                                                        'Valor Atual (v. Atual)': ", ".join(val_atual) if val_atual else "Nenhum"
                                                                    })
                                                                elif k == 'paused':
                                                                    status_ant = 'Pausado' if val_anterior else 'Ativo'
                                                                    status_atu = 'Pausado' if val_atual else 'Ativo'
                                                                    changed.append({
                                                                        'Elemento': element_name,
                                                                        'Campo Alterado': "Status",
                                                                        'Valor Anterior (v. Anterior)': status_ant,
                                                                        'Valor Atual (v. Atual)': status_atu
                                                                    })
                                                                elif k == 'name':
                                                                    changed.append({
                                                                        'Elemento': val_anterior,
                                                                        'Campo Alterado': "Nome",
                                                                        'Valor Anterior (v. Anterior)': val_anterior,
                                                                        'Valor Atual (v. Atual)': val_atual
                                                                    })
                                                                else:
                                                                    if k not in ['tagManagerUrl', 'accountId', 'containerId']:
                                                                        changed.append({
                                                                            'Elemento': element_name,
                                                                            'Campo Alterado': f"Propriedade: {k}",
                                                                            'Valor Anterior (v. Anterior)': str(val_anterior),
                                                                            'Valor Atual (v. Atual)': str(val_atual)
                                                                        })
                                                        
                                            for eid, e in prev_dict.items():
                                                if eid not in live_dict:
                                                    removed.append({'Elemento': e.get('name', eid)})
                                                    
                                            return added, removed, changed

                                        added_tags, rem_tags, mod_tags = compare_elements(tags, prev_full_v.get('tag', []), 'tagId')
                                        added_trig, rem_trig, mod_trig = compare_elements(triggers, prev_full_v.get('trigger', []), 'triggerId')
                                        added_var, rem_var, mod_var = compare_elements(variables, prev_full_v.get('variable', []), 'variableId')
                                        
                                        tab1, tab2, tab3 = st.tabs(["Tags", "Acionadores", "Variáveis"])
                                        
                                        def render_diff_table(added, removed, changed):
                                            if not added and not removed and not changed:
                                                st.info("Nenhuma mudança detectada entre estas versões.")
                                                return
                                            
                                            st.markdown("🟢 **Adicionados**")
                                            st.dataframe(pd.DataFrame(added) if added else pd.DataFrame([{'Elemento': '-'}]), use_container_width=True, hide_index=True)
                                            
                                            st.markdown("🔴 **Removidos**")
                                            st.dataframe(pd.DataFrame(removed) if removed else pd.DataFrame([{'Elemento': '-'}]), use_container_width=True, hide_index=True)
                                            
                                            st.markdown("🟡 **Alterados**")
                                            st.dataframe(pd.DataFrame(changed) if changed else pd.DataFrame([{'Elemento': '-'}]), use_container_width=True, hide_index=True)

                                        with tab1:
                                            render_diff_table(added_tags, rem_tags, mod_tags)
                                        with tab2:
                                            render_diff_table(added_trig, rem_trig, mod_trig)
                                        with tab3:
                                            render_diff_table(added_var, rem_var, mod_var)
                                            
                                    except Exception as e:
                                        st.error(f"Não foi possível carregar o comparativo de versões: {e}")
                            else:
                                st.info("Não há versão publicada anterior para comparar.")

                            # --- Tabelas de Dados ---
                            st.markdown("### Dados da Versão")
                            
                            st.markdown("#### Resumo da Versão")
                            fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
                            agora = datetime.datetime.now(fuso_br)
                            data_coleta = agora.strftime("%d/%m/%Y")
                            hora_coleta = agora.strftime("%H:%M:%S")
                            
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
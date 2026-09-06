import json
from googleapiclient.discovery import build

class GTMService:
    def __init__(self, credentials):
        # a gente já recebe a credencial pronta do auth lá no app principal
        self.service = build('tagmanager', 'v2', credentials=credentials)

    def get_accounts(self):
        # puxa todas as contas que o usuário tem acesso
        try:
            results = self.service.accounts().list().execute()
            return results.get('account', [])
        except Exception as e:
            raise Exception(f"Erro ao buscar contas: {e}")

    def get_containers(self, account_path):
        # varre os containers de uma conta que a gente passar no account_path
        try:
            results = self.service.accounts().containers().list(parent=account_path).execute()
            return results.get('container', [])
        except Exception as e:
            raise Exception(f"Erro ao buscar contêineres: {e}")

    def get_versions(self, container_path):
        # pega o histórico de versões pra gente usar na comparação
        try:
            results = self.service.accounts().containers().version_headers().list(parent=container_path).execute()
            return results.get('containerVersionHeader', [])
        except Exception as e:
            raise Exception(f"Erro ao buscar versões: {e}")

    def get_latest_published_version(self, container_path):
        # busca a última versão que tá no ar de fato (live)
        try:
            results = self.service.accounts().containers().versions().live(parent=container_path).execute()
            return results
        except Exception as e:
            raise Exception(f"Erro ao buscar a versão publicada atual: {e}")

    def calculate_script_size(self, version_data):
        # a gente converte pra string json pra conseguir estimar o tamanho do script em kb
        # não é 100% exato com o que carrega no site da pessoa, mas dá uma ótima base
        json_data = json.dumps(version_data)
        size_bytes = len(json_data.encode('utf-8'))
        return size_bytes / 1024  # Retorna em KB

    def calculate_complexity(self, num_tags, num_variables):
        # calculo de padaria pra estimar peso de execução (ms). tags pesam um pouco mais que as vars
        return (num_tags * 1.5) + (num_variables * 0.5)

    def extract_inventory(self, version_data):
        # varre a versão inteira pra separar tudo organizadinho nas tabelas
        tags = version_data.get('tag', [])
        triggers = version_data.get('trigger', [])
        variables = version_data.get('variable', [])
        
        # dicionário pra traduzir os tipos esquisitos do gtm pra nomes de verdade
        type_mapping = {
            'html': 'HTML Personalizado',
            'jsm': 'JavaScript Personalizado',
            'v': 'Variável de Camada de Dados (Data Layer)',
            'gaawa': 'Google Analytics: Configuração GA4',
            'gaawe': 'Google Analytics: Evento GA4',
            'ua': 'Google Analytics: Universal Analytics',
            'smm': 'Tabela de Consulta (Lookup Table)',
            'remm': 'Tabela de RegEx (Regex Table)',
            'gas': 'Google Ads: Conversões',
            'sp': 'Google Ads: Remarketing',
            'awct': 'Google Ads: Conversões',
            'pageview': 'Exibição de Página',
            'customEvent': 'Evento Personalizado',
            'click': 'Clique',
            'linkClick': 'Clique em Link'
        }
        
        # mapeia os triggers pelo id pra ficar mais fácil de achar o nome depois
        triggers_map = {t['triggerId']: t['name'] for t in triggers}
        
        inventory = []
        
        for tag in tags:
            tag_name = tag.get('name', 'N/A')
            tag_type = tag.get('type', 'N/A')
            mapped_type = type_mapping.get(tag_type, tag_type)
            
            # verifica se a tag tá sem nenhum acionador configurado (aquelas tags perdidas no container)
            firing_triggers_ids = tag.get('firingTriggerId', [])
            firing_triggers_names = [triggers_map.get(tid, tid) for tid in firing_triggers_ids]
            
            inventory.append({
                'Element Type': 'Tag',
                'Name': tag_name,
                'Tipo': mapped_type,
                'Associated Triggers': ', '.join(firing_triggers_names) if firing_triggers_names else 'Nenhum (Órfã)',
                'Status': 'Pausada' if tag.get('paused') else 'Ativa'
            })
            
        for trigger in triggers:
            trigger_type = trigger.get('type', 'N/A')
            mapped_type = type_mapping.get(trigger_type, trigger_type)
            
            inventory.append({
                'Element Type': 'Trigger',
                'Name': trigger.get('name', 'N/A'),
                'Tipo': mapped_type,
                'Associated Triggers': 'N/A',
                'Status': 'Ativa'
            })
            
        for variable in variables:
            variable_type = variable.get('type', 'N/A')
            mapped_type = type_mapping.get(variable_type, variable_type)
            
            inventory.append({
                'Element Type': 'Variable',
                'Name': variable.get('name', 'N/A'),
                'Tipo': mapped_type,
                'Associated Triggers': 'N/A',
                'Status': 'Ativa'
            })
            
        return inventory
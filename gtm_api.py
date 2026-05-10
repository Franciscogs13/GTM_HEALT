import json
from googleapiclient.discovery import build

class GTMService:
    def __init__(self, credentials):
        """
        Inicializa o serviço GTM recebendo a credencial já validada pelo Streamlit na arquitetura Web.
        :param credentials: Objeto de credenciais do Google Auth.
        """
        self.service = build('tagmanager', 'v2', credentials=credentials)

    def get_accounts(self):
        """Lista todas as contas GTM acessíveis."""
        try:
            results = self.service.accounts().list().execute()
            return results.get('account', [])
        except Exception as e:
            raise Exception(f"Erro ao buscar contas: {e}")

    def get_containers(self, account_path):
        """
        Lista todos os contêineres de uma conta específica.
        :param account_path: O caminho da conta (ex: 'accounts/12345').
        """
        try:
            results = self.service.accounts().containers().list(parent=account_path).execute()
            return results.get('container', [])
        except Exception as e:
            raise Exception(f"Erro ao buscar contêineres: {e}")

    def get_versions(self, container_path):
        """
        Lista o histórico de versões de um contêiner.
        :param container_path: O caminho do contêiner (ex: 'accounts/123/containers/456').
        """
        try:
            results = self.service.accounts().containers().version_headers().list(parent=container_path).execute()
            return results.get('containerVersionHeader', [])
        except Exception as e:
            raise Exception(f"Erro ao buscar versões: {e}")

    def get_latest_published_version(self, container_path):
        """
        Obtém os detalhes da versão publicada mais recente.
        """
        try:
            results = self.service.accounts().containers().versions().live(parent=container_path).execute()
            return results
        except Exception as e:
            raise Exception(f"Erro ao buscar a versão publicada atual: {e}")

    def calculate_script_size(self, version_data):
        """
        Estima o tamanho do script da versão em KB.
        Faz um dump JSON da estrutura da versão para calcular os bytes.
        """
        json_data = json.dumps(version_data)
        size_bytes = len(json_data.encode('utf-8'))
        return size_bytes / 1024  # Retorna em KB

    def calculate_complexity(self, num_tags, num_variables):
        """
        Estima a complexidade de tempo de execução (em ms) baseado numa heurística.
        """
        return (num_tags * 1.5) + (num_variables * 0.5)

    def extract_inventory(self, version_data):
        """
        Extrai tags, triggers e variáveis de uma versão e retorna um inventário consolidado.
        """
        tags = version_data.get('tag', [])
        triggers = version_data.get('trigger', [])
        variables = version_data.get('variable', [])
        
        # Mapeamento para facilitar busca
        triggers_map = {t['triggerId']: t['name'] for t in triggers}
        
        inventory = []
        
        for tag in tags:
            tag_name = tag.get('name', 'N/A')
            tag_type = tag.get('type', 'N/A')
            
            # Algumas tags podem não ter firingTriggerId (Tags órfãs)
            firing_triggers_ids = tag.get('firingTriggerId', [])
            firing_triggers_names = [triggers_map.get(tid, tid) for tid in firing_triggers_ids]
            
            inventory.append({
                'Element Type': 'Tag',
                'Name': tag_name,
                'Associated Triggers': ', '.join(firing_triggers_names) if firing_triggers_names else 'Nenhum (Órfã)',
                'Status': 'Pausada' if tag.get('paused') else 'Ativa'
            })
            
        for trigger in triggers:
            inventory.append({
                'Element Type': 'Trigger',
                'Name': trigger.get('name', 'N/A'),
                'Associated Triggers': 'N/A',
                'Status': 'Ativa'
            })
            
        for variable in variables:
            inventory.append({
                'Element Type': 'Variable',
                'Name': variable.get('name', 'N/A'),
                'Associated Triggers': 'N/A',
                'Status': 'Ativa'
            })
            
        return inventory
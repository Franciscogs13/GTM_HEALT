# GTM Health Dashboard 🩺

Um dashboard interativo desenvolvido em Python com Streamlit para realizar auditorias técnicas e monitorar a saúde de contêineres do Google Tag Manager (GTM). Ideal para analistas de dados e engenheiros que precisam garantir a performance de rastreamento sem comprometer a velocidade do site.

## 🚀 Funcionalidades

- **Métricas de Performance:** Cálculo estimado do peso do script (KB) e da complexidade de execução (ms) baseada em heurística técnica.
- **Inventário Completo:** Extração detalhada de Tags, Triggers e Variáveis da última versão publicada (Live).
- **Análise de Qualidade:** Identificação automática de "Tags Órfãs" (tags sem acionadores vinculados).
- **Visualização de Dados:** Gráficos interativos de composição do contêiner e histórico de crescimento. Inclui um controle deslizante (Slider) para escolher quantas versões passadas analisar (de 3 a 50).
- **Interface Adaptativa:** Design com identidade visual corporativa (Laranja e Azul-petróleo) que suporta perfeitamente a alternância entre os Modos Claro e Escuro, garantindo alto contraste e acessibilidade.
- **Exportação Profissional:** Download do inventário tratado em formatos CSV ou Excel (.xlsx) para relatórios rápidos.

## 📋 Pré-requisitos e Autenticação (OAuth 2.0)

Diferente de uma Service Account, utilizamos o fluxo **OAuth 2.0** para que você possa acessar todas as contas GTM vinculadas ao seu e-mail corporativo forma centralizada.

### Passo 1: Configuração no Google Cloud Console
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie ou selecione o projeto `Auditoria-GTM`.
3. Em **APIs e Serviços > Biblioteca**, ative a **Google Tag Manager API**.
4. Vá em **Tela de consentimento OAuth**:
   - Escolha o tipo **Externo** (ou Interno, se estiver em um ambiente Google Workspace).
   - Preencha as informações básicas do app.
   - Em **Usuários de teste**, adicione o seu e-mail (essencial enquanto o app estiver em desenvolvimento).

### Passo 2: Criar Credenciais e Configurar Segredos
1. Vá em **APIs e Serviços > Credenciais**.
2. Clique em **+ Criar Credenciais > ID do cliente OAuth**.
3. Em **Tipo de aplicativo**, selecione **Aplicativo da Web** (Web Application). Em URIs de redirecionamento autorizados, adicione a URL da sua aplicação (ex: `http://localhost:8501` para rodar localmente ou a URL do Streamlit Cloud).
4. Baixe o arquivo JSON gerado.
5. **Importante:** Crie uma pasta chamada `.streamlit` na raiz do seu projeto e dentro dela crie um arquivo chamado `secrets.toml`.
6. Copie todo o conteúdo do JSON baixado, transforme em uma string (removendo as quebras de linha se necessário) e cole no `secrets.toml` seguindo o formato exigido pelo Streamlit:

```toml
[google_oauth]
client_secrets = '{"web":{"client_id":"...","project_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_secret":"...","redirect_uris":["http://localhost:8501"]}}'
```
## 🛠️ Instalação e Execução

### 1. Preparar o Ambiente
Certifique-se de estar na pasta do projeto e instale as dependências necessárias:

```bash
pip install streamlit pandas plotly xlsxwriter google-api-python-client google-auth-oauthlib
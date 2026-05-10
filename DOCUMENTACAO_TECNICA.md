# Documentação Técnica: GTM Health Dashboard

## 1. Visão Geral do Projeto
O **GTM Health Dashboard** é uma aplicação web interativa focada em auditoria técnica, controle de qualidade e gestão de saúde de contêineres do Google Tag Manager (GTM). Ela foi desenhada para resolver o problema de visibilidade técnica em estruturas complexas, permitindo que analistas e gestores visualizem de forma rápida o estado de seus ambientes e evitem degradação de performance nos sites monitorados.

---

## 2. Funcionalidades Principais

* **Autenticação Segura (OAuth 2.0):** Acesso validado pelo ecossistema seguro do Google. A aplicação não armazena senhas, utilizando chaves temporárias aprovadas pelo próprio usuário (Token OAuth).
* **Navegação Hierárquica:** Permite selecionar contas corporativas e detalhar os contêineres que estão vinculados a elas de forma dinâmica.
* **Auditoria da Versão Live:** Faz o mapeamento da última versão ativamente publicada em produção, garantindo que o painel mostre o que de fato está rodando no site hoje.
* **Cálculo de Performance Heurística:**
  * **Tamanho do Script (KB):** Avalia e simula o "peso" do contêiner. Emite alertas visuais caso o contêiner ultrapasse os 200 KB (melhor prática).
  * **Tempo de Execução (ms):** Simulação matemática do nível de complexidade das Tags e Variáveis para dar um direcional da carga de processamento na máquina do usuário.
* **Detecção de Anomalias:** O sistema varre automaticamente a estrutura em busca de **Tags Órfãs** (tags configuradas sem acionadores/triggers), apontando ineficiências e lixos digitais (*technical debt*).
* **Histórico e Tendências:** Gráficos que mapeiam como o contêiner cresceu ao longo do tempo. Inclui um **Controle Deslizante (Slider) Dinâmico** que permite ao analista escolher entre rapidez (analisar as últimas 5 versões) ou profundidade (analisar até as últimas 50 versões).
* **Exportação Completa e Organizada:** Exporta para Excel ou CSV dois cenários em um clique:
  * O resumo executivo de métricas gerais do ambiente.
  * O inventário detalhado de todas as Tags, Triggers e Variáveis isoladas para cruzamento de dados.

---

## 3. Arquitetura e Stack Tecnológico (Bibliotecas Usadas)

A aplicação foi construída integralmente em **Python**, prezando por alta velocidade de desenvolvimento, fácil manutenção e poder massivo na análise dos dados em back-end.

### 🖥️ Interface e Front-End
* **[Streamlit](https://streamlit.io/):** Framework de código aberto principal da aplicação. Responsável por traduzir a lógica de Python diretamente para uma aplicação Web moderna, ágil e visual. Ele gerencia o estado da sessão de navegação, a responsividade de tela, as barras de rolagem, alertas de notificação e o layout geral do projeto sem necessitar criar arquivos complexos de HTML/CSS/JS.

### 🔌 Integração e Autenticação (Google APIs)
* **[google-api-python-client](https://github.com/googleapis/google-api-python-client):** Biblioteca oficial do Google Cloud. Utilizada em nosso módulo de backend (`gtm_api.py`) para consumir a API v2 do GTM. É ela quem faz o trabalho duro de buscar as informações JSON da nuvem de acordo com as requisições do usuário.
* **[google-auth-oauthlib](https://google-auth-oauthlib.readthedocs.io/):** Biblioteca que gerencia o fluxo completo de consentimento do usuário. Na nossa arquitetura focada em nuvem (Web App), a biblioteca cuida do protocolo de segurança **PKCE** (Proof Key for Code Exchange), gerando e mantendo os códigos validadores criptográficos nativamente dentro do estado de sessão segura do Streamlit para evitar falhas ou interceptações de login em deploys na nuvem.

### 📊 Tratamento e Organização de Dados
* **[Pandas](https://pandas.pydata.org/):** Principal biblioteca de análise e manipulação de dados do mundo Python. Foi utilizada para modelar o enorme dicionário JSON bruto do Google em Tabelas Relacionais organizadas. É a biblioteca matriz das exportações e que constrói a base que alimenta as visualizações.
* **[XlsxWriter](https://xlsxwriter.readthedocs.io/):** Um motor para gerar os arquivos exportáveis via Excel. É utilizado por debaixo dos panos pelo *Pandas* para converter nossas tabelas de memória em arquivos `.xlsx` confiáveis.

### 📈 Gráficos e Visualização de Negócios
* **[Plotly (plotly.express)](https://plotly.com/python/):** Biblioteca gráfica extremamente moderna e interativa. Utilizada para desenhar os gráficos de "Pizza" de divisão de componentes e os gráficos em "Barras" de histórico de versões. Escolhida por possuir interatividade com o ponteiro do mouse (hover nativo) em tela, de forma superior ao comum Matplotlib.

---

## 4. Segurança da Informação

- Nenhuma credencial pessoal é guardada ou armazenada (*hardcoded*).
- Os segredos da aplicação são gerenciados usando o padrão **Streamlit Secrets** (`.streamlit/secrets.toml`), que permite isolar dados vitais em variáveis de ambiente protegidas em deploys na nuvem (como Heroku ou Streamlit Cloud).
- O fluxo de autenticação foi protegido contra perda de sessão mantendo rigor no uso do PKCE e do parâmetro `state`.
- Foi inserido o arquivo `.gitignore` que instrui o repositório (`Git`) a jamais enviar chaves API, a pasta `.streamlit/`, arquivos de teste ou ambientes virtuais para servidores públicos.

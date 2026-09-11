# VIGIL OSINT Workbench

Uma workbench local-first para investigações OSINT defensivas, verificação de identidade pública, análise de contas falsas/impersonação, threat intelligence e detecção de comportamento coordenado.

> **Escopo:** apenas fontes públicas e investigações legítimas. O projeto não inclui invasão, credential stuffing, bypass de autenticação, doxxing, coleta de dados vazados, engenharia social ofensiva ou automação de assédio.

## O que o projeto entrega

- **Cases**: cada investigação possui objetivo, alvo, escopo e trilha de auditoria.
- **Entity graph**: pessoas públicas/contas, organizações, domínios, URLs, infraestrutura, documentos, mídia e claims viram entidades ligadas por relações explicáveis.
- **Evidence ledger**: toda descoberta carrega fonte, horário, coletor, hash e confiança.
- **Correlation engine**: correla sinais independentes e nunca trata coincidência de username como prova de identidade.
- **Fake / impersonation analysis**: sinais de imitação de marca, reutilização de identidade visual, links compartilhados e inconsistências.
- **Influence-operation analysis**: detecção de coordenação, clusters de narrativas e sincronização temporal em datasets públicos importados. Não executa psyops.
- **Passive infrastructure OSINT**: domínio, DNS, certificados, archives e threat-intel sem exploração.
- **Plug-in collectors**: integra ferramentas consolidadas como Maigret, Sherlock, OWASP Amass, Subfinder e APIs opcionais.
- **Exports**: JSON, CSV e GraphML.

## Arquitetura

```text
apps/web  -> React + Vite + Cytoscape
    |
    v
apps/api  -> FastAPI
    |
    +-> SQLite evidence store
    +-> correlation/scoring engine
    +-> collectors (adapters)
    +-> external CLI/API tools
```

## Quick start

### Docker

```bash
cp .env.example .env
docker compose up --build
```

- UI: http://localhost:5173
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs

### Desenvolvimento

API:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

## Coletores

O núcleo funciona mesmo sem ferramentas externas. Quando instaladas, as integrações são detectadas automaticamente.

| Área | Integração | Uso |
|---|---|---|
| username | Maigret | descoberta e parsing de perfis públicos |
| username | Sherlock | verificação rápida de handles públicos |
| domínio | OWASP Amass | asset discovery/passive mapping |
| domínio | Subfinder | enumeração passiva de subdomínios |
| organização | theHarvester | integração opcional, limitada a investigações organizacionais autorizadas |
| threat intel | VirusTotal / Shodan / Censys / urlscan | enriquecimento por API quando houver chave |
| archives | Wayback Machine | histórico público |
| metadata | ExifTool | metadados de arquivos fornecidos ao caso |

Veja [docs/TOOLS.md](docs/TOOLS.md).

## Princípio de correlação

Uma aresta forte exige **múltiplos sinais independentes**. O engine combina evidências como:

- handle normalizado;
- URL externa compartilhada;
- domínio em bio;
- hash perceptual de mídia reutilizada;
- nomes/display names similares;
- relações observadas por mais de uma fonte;
- proximidade temporal e padrões de publicação em datasets importados.

Cada relação guarda a explicação e as evidências que contribuíram para o score.

## Estrutura

```
apps/
  api/
  web/
docs/
  ARCHITECTURE.md
  METHODOLOGY.md
  TOOLS.md
```

## Uso responsável

O projeto foi desenhado para:

- brand protection e impersonation;
- investigação de contas públicas;
- checagem de desinformação;
- CTI e threat research;
- segurança corporativa;
- due diligence baseada em fontes públicas;
- investigação acadêmica/jornalística responsável.

Não use para vigiar pessoas privadas, localizar endereço residencial, coletar credenciais, perseguir indivíduos ou contornar controles de acesso.

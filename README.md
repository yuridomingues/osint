# VIGIL OSINT Workbench

VIGIL é uma workbench local-first para investigações OSINT defensivas e baseadas em fontes públicas. O objetivo é centralizar coleta, normalização, correlação, análise e evidências em um único case, com grafo explicável e proveniência.

> **Escopo:** fontes públicas, brand protection, CTI, verificação, pesquisa e investigações legítimas. O projeto não implementa invasão, credential stuffing, bypass de autenticação, doxxing, bancos de credenciais vazadas, engenharia social ofensiva, stalking ou automação de psyops/assédio.

## Estado atual

### Funcional

- **Cases** com alvo, objetivo, tipo e confirmação de escopo.
- **Entity-link graph** interativo em Cytoscape.js.
- **Evidence ledger** com fonte, coletor, horário, reliability e hash SHA-256 em imports.
- **Correlação conservadora de contas públicas**: semelhança de username/nome isoladamente não vira identidade.
- **Import direto do Sherlock** por CSV.
- **Import direto do Maigret** por JSON/NDJSON.
- **Schema genérico de observações públicas** para integrar outras ferramentas.
- **Fake / impersonation scoring** multi-sinal e explicável.
- **Coordinated-behavior analysis** em datasets de posts públicos, com janela temporal e ressalva explícita entre indicador e prova.
- **OSINT passivo de domínio** por Certificate Transparency (crt.sh), RDAP e Internet Archive.
- **Exports JSON e GraphML**.
- **Docker Compose** para API + interface.
- **CI** com testes da API e build do frontend.

### Roadmap de adapters

O VIGIL não reimplementa ferramentas maduras quando um adapter é melhor. As próximas integrações prioritárias são:

- SpiderFoot;
- OWASP Amass e Subfinder para asset discovery passivo de organizações/domínios autorizados;
- ExifTool para arquivos fornecidos ao case;
- OpenCTI / STIX 2.1;
- MISP;
- urlscan.io;
- VirusTotal;
- Shodan / Censys para contexto de infraestrutura organizacional;
- theHarvester em escopo organizacional.

Veja [docs/TOOLS.md](docs/TOOLS.md).

## Arquitetura

```text
apps/web  -> React + Vite + Cytoscape
    |
    v
apps/api  -> FastAPI
    |
    +-> SQLite evidence store
    +-> passive public-source collectors
    +-> normalization adapters
    +-> correlation/scoring engine
    +-> coordinated-behavior analysis
    +-> JSON / GraphML export
```

Detalhes em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

Testes:

```bash
make test
```

## Fluxo de investigação

1. Crie um **case** e registre o objetivo.
2. Para domínio/organização, execute a coleta passiva integrada.
3. Para contas públicas, importe observações ou exports do Sherlock/Maigret.
4. Para desinformação/operações de influência, importe um dataset de posts públicos e analise comportamento coordenado.
5. Revise o **grafo**, sempre abrindo a entidade e sua confiança.
6. Confira o **evidence ledger** antes de aceitar qualquer relação.
7. Revise **findings** e hipóteses alternativas.
8. Exporte JSON/GraphML para análise ou relatório.

## Princípio de correlação

O engine separa **observação** de **avaliação**.

Sinais fracos:

- username parecido;
- display name parecido;
- texto de bio semelhante.

Sinais mais fortes:

- domínio externo compartilhado;
- mídia pública reutilizada;
- evidências independentes convergentes;
- relação observada em múltiplas fontes;
- sincronização temporal mensurável em datasets públicos.

Uma relação de identidade não deve ser inferida apenas porque dois perfis têm nomes parecidos.

## "Psyops" no VIGIL

O VIGIL não executa campanhas de influência. O módulo relacionado a esse tema é defensivo: procura **indicadores de comportamento coordenado**, como conteúdo público idêntico publicado por várias contas numa janela temporal curta.

Isso pode ajudar em:

- desinformação;
- campanhas coordenadas;
- sockpuppet/fake-account triage;
- brand impersonation;
- threat intelligence.

Um cluster detectado é um **lead para revisão humana**, não prova de autoria comum, intenção maliciosa ou atribuição a um ator.

## Estrutura

```text
apps/
  api/
    app/
    tests/
  web/
    src/
docs/
  ARCHITECTURE.md
  IMPORT_SCHEMA.md
  METHODOLOGY.md
  TOOLS.md
.github/
  workflows/
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

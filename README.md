<div align="center">

# 🏥 JARVIS CNES

**Sistema Auxiliar de Cadastramento do CNES/DATASUS — Porto Velho/RO**

Preencha as fichas do cadastro, gere o extrato em PDF e envie automaticamente à GECAV o arquivo **`.BCK`** — o formato oficial de exportação do SCNES — pronto para importação.

```
JARVIS CNES · Cadastro Nacional de Estabelecimentos de Saúde
Sistema Auxiliar do Cadastro CNES
```

[📦 Produção](https://jarvis-cnes.vercel.app) · [📋 Guia de validação no SCNES](VALIDACAO_BCK_SCNES.md) · [🧪 Testes](#testes)

</div>

---

## 📑 Índice

1. [Visão geral](#-visão-geral)
2. [Funcionalidades](#-funcionalidades)
3. [Identidade visual e logos](#-identidade-visual-e-logos)
4. [Estrutura do projeto](#-estrutura-do-projeto)
5. [Como rodar localmente](#-como-rodar-localmente)
6. [Configuração (variáveis de ambiente)](#-configuração-variáveis-de-ambiente)
7. [O formato .BCK — anatomia completa](#-o-formato-bck--anatomia-completa)
8. [Fluxo de envio e segurança](#-fluxo-de-envio-e-segurança)
9. [As fichas do cadastro](#-as-fichas-do-cadastro)
10. [Geração do PDF (extrato)](#-geração-do-pdf-extrato)
11. [Deploy no Vercel](#-deploy-no-vercel)
12. [Testes automatizados](#-testes-automatizados)
13. [Validação no SCNES de teste](#-validação-no-scnes-de-teste)
14. [Troubleshooting](#-troubleshooting)
15. [Limitações e divergências conhecidas](#-limitações-e-divergências-conhecidas)
16. [Segurança](#-segurança)
17. [Roadmap](#-roadmap)

---

## 🚀 Visão geral

O **JARVIS CNES** é um sistema web auxiliar criado para a **SEMUSA — Secretaria Municipal de Saúde de Porto Velho/RO** (Departamento de Regulação, Avaliação e Controle — **DRAC**). Ele digitaliza o preenchimento das fichas do **Cadastro Nacional de Estabelecimentos de Saúde (CNES)**, do DATASUS.

O fluxo ponta a ponta:

```
Formulário web (fichas 1–21)  →  Gera .BCK em oculto (formato oficial SCNES)
                              →  Gera extrato em PDF (com logos)
                              →  Envia TUDO por e-mail SOMENTE para a GECAV
                              →  GECAV importa o .BCK no SCNES (CNES/DATASUS)
```

**Ponto central da solução**: o JARVIS reproduz o formato `.BCK` de exportação do SCNES 4.8.40 — validado **byte a byte** contra exportações reais (68 tabelas, schemas e serialização idênticos). O cadastro pode ser feito **sem CNES preenchido**: o objetivo é justamente gerar a numeração CNES de estabelecimentos novos na importação.

---

## ✨ Funcionalidades

### 📋 Cadastro completo (fichas CNES)
- **Ficha 1 — Identificação**: operação (inclusão/alteração/exclusão), CNES, tipo de estabelecimento, CNPJ/CPF, razão social, endereço, CEP, telefone, e-mail, RT/diretor, alvará
- **Ficha 2 — Caracterização**: esfera administrativa, ensino/pesquisa, hierarquia, fluxo de clientela, convênio, turno, dias e horários de funcionamento, tipos de atendimento
- **Ficha 4 — Comissões**: 14 comissões (ética médica, controle de infecção hospitalar, CIPA, etc.)
- **Ficha 6 — Instalações físicas**: consultórios, triagem, repouso, clínicas, cirurgia, pré-parto, parto, leitos RN (sub-abas por bloco: UE / Ambulatorial / CC / CO)
- **Ficha 7 — Serviços de apoio**: SAME, farmácia, central de esterilização, lactário, lavanderia, ambulância, necrotério etc.
- **Resíduos**: biológicos, químicos, radioativos, comuns
- **Ficha 8 — Serviços especializados (CBO)**: 22 serviços (SAMU, regulação, pré-natal, saúde bucal, psicossocial, cardiovascular, diagnóstico por imagem, oncologia, UTI, etc.) com suas classificações oficiais
- **Ficha 13–17 — Equipamentos**: diagnóstico/imagem, infraestrutura, ópticos, métodos gráficos, manutenção de vida, odontológicos, audiologia
- **Ficha 19 — Leitos**: 7 grupos de especialidades (cirúrgicos, obstétricos, pediátricos, clínicos, outras, hospital-dia, complementares/UTI)
- **Fichas 20/21 — Profissionais**: vínculo com tabela CBO completa (87 ocupações), conselho, carga horária, especializações
- **Declaração**: modelo oficial de declaração para pessoa jurídica/física com preenchimento inline

### ✅ Validações inteligentes
- **CPF** e **CNPJ** com dígitos verificadores (formatação automática)
- Campos obrigatórios por ficha com alerta antes do envio

### 📄 Extrato em PDF
- Gerado com **ReportLab** (A4), cabeçalho com as 3 logos, tabelas estilizadas com o padrão visual do sistema
- Resumo de todas as fichas preenchidas + declaração
- Suporte a **anexos** (PDF, imagens) enviados junto

### 📦 Geração do `.BCK` (SCNES)
- Reproduz o **formato oficial de exportação** do SCNES 4.8.40 (container + 68 tabelas + TXT de transmissão)
- Validado **byte a byte** contra exportação real do município (2.082 estabelecimentos)
- Nome no padrão de transmissão: `CNES0RO110020<data><hora><ano><versão>.bck`
- **Sempre gerado**, mesmo sem CNES preenchido (estabelecimento novo)

### ✉️ Envio automático para a GECAV
- SMTP Gmail (587/TLS), senha de app
- Destinatário **fixo e único**: `gecav.semusa@portovelho.ro.gov.br` — sem Cc/Bcc
- Anexos: `.BCK` (padrão CNES) + `extrato_cnes.pdf` (+ anexos opcionais do usuário)
- **Rate limit** anti-spam (intervalo mínimo + teto por hora)

---

## 🎨 Identidade visual e logos

O sistema usa **3 logos** posicionados no cabeçalho — tanto na interface web quanto no PDF gerado:

| Logo | Arquivo | Posição (web) | Posição (PDF) |
|---|---|---|---|
| Prefeitura de Porto Velho | `logo_prefeitura.png` | esquerda do cabeçalho | esquerda |
| JARVIS CNES | `logo_jarvis.png` | centro do cabeçalho | centro |
| CNES | `logo_cnes.png` | direita do cabeçalho | direita |

### 🖼️ Na interface web
```
┌─────────────────────────────────────────────────────────────┐
│ [Prefeitura]        [JARVIS CNES]          [CNES]           │
│                   Sistema Auxiliar do                       │
│                   Cadastro CNES                             │
└─────────────────────────────────────────────────────────────┘
```
Cada logo é servido por rota própria (`/logo-prefeitura`, `/logo-jarvis`, `/logo-cnes`) e tem `onerror` com fallback: se o arquivo não existir, o `<img>` é ocultado sem quebrar o layout.

### 📄 No PDF (extrato)
O cabeçalho do PDF monta uma tabela de 3 colunas (`esquerda | centro | direita`) com as logos em 80×60 px. Se a logo do JARVIS não existir, o centro é substituído pelo texto **"JARVIS CNES"** em azul institucional (`#003057`) — o documento nunca sai sem identidade.

### 🔧 Como trocar
Basta substituir o arquivo na raiz do projeto mantendo o nome:
- Formatos aceitos: `.png`, `.jpg`, `.jpeg` (o código procura nessa ordem)
- **Sem logotipo?** Basta apagar os arquivos — a interface e o PDF funcionam normalmente (fallback automático)

---

## 📁 Estrutura do projeto

```
├── app.py                    # Aplicação completa (Flask) — ~4.580 linhas
│   │                           #   form web + PDF + e-mail + gerador .BCK
│   ├── Validação CPF/CNPJ
│   ├── Tabelas CBO / equipamentos / leitos / serviços (dados oficiais)
│   ├── Geração PDF (ReportLab)
│   ├── Envio de e-mail (SMTP Gmail) — .BCK oculto + PDF
│   ├── Núcleo .BCK: schemas das 68 tabelas + serialização DATAPACKET
│   │                   + container (zlib) + TXT de transmissão
│   └── Rotas Flask: /, /logo-*, /gerar-pdf, /enviar-email
├── test_bck.py               # Testes pytest (6 testes: 3 byte a byte + 3 fluxo)
├── requirements.txt          # flask, reportlab, waitress
├── .env.example              # ⚠️ exemplo de config (ver seção Segurança)
├── .gitignore                # .env, logs, dados sensíveis (analise_bck/)
├── VALIDACAO_BCK_SCNES.md    # Guia: como importar o .BCK no SCNES de teste
├── logo_prefeitura.png       # Logotipo — esquerda
├── logo_jarvis.png           # Logotipo — centro
└── logo_cnes.png             # Logotipo — direita
```

**Arquitetura**: monólito em um único `app.py` (Flask) — formulário HTML embutido, lógica de negócio, PDF, e-mail e gerador de `.BCK` no mesmo processo. O servidor de produção usa **Waitress** (WSGI) em `127.0.0.1:5000`, com fallback para o dev server do Flask **sem debug** (nunca expõe o debugger na rede).

**Stack**: Python 3.12 · Flask · ReportLab · Waitress · zlib/struct (BCK) · smtplib (e-mail)

---

## 🏃 Como rodar localmente

```bash
# 1. Dependências
python -m pip install -r requirements.txt

# 2. Configuração (opcional — o app funciona com defaults)
#    copie .env.example para .env e preencha (veja seção Configuração)

# 3. Rodar
python app.py
# → http://127.0.0.1:5000
```

| Variável | Padrão | Descrição |
|---|---|---|
| `JARVIS_HOST` | `127.0.0.1` | Endereço de escuta |
| `JARVIS_PORT` | `5000` | Porta de escuta |

> 💡 Em ambiente de rede (servidor de produção), rode `python app.py` com `JARVIS_HOST=0.0.0.0` — o Waitress assume automaticamente. No Vercel isso é desnecessário (serverless).

---

## 🔧 Configuração (variáveis de ambiente)

O app lê a configuração de variáveis de ambiente (ou de um arquivo `.env` na mesma pasta — o `python-dotenv` não é usado, a leitura é feita via `os.environ`). **O `.env` NUNCA deve ser versionado** (está no `.gitignore`).

| Variável | Obrigatória | Uso |
|---|---|---|
| `JARVIS_EMAIL` | ✅ (envio) | Remetente — conta Gmail |
| `JARVIS_SENHA_APP` | ✅ (envio) | **Senha de app** do Gmail (nunca a senha normal) |
| `JARVIS_DESTINATARIO` | ✅ (envio) | E-mail da GECAV (único destinatário do `.BCK`) |
| `JARVIS_HOST` | ❌ | Endereço de escuta (padrão `127.0.0.1`) |
| `JARVIS_PORT` | ❌ | Porta de escuta (padrão `5000`) |
| `JARVIS_INTERVALO_MIN` | ❌ | Intervalo mínimo entre envios em segundos (padrão `5`) |
| `JARVIS_LIMITE_HORA` | ❌ | Teto de envios por hora (padrão `30`) |
| `JARVIS_RATE_LIMIT=0` | ❌ | Desliga o rate limit (apenas testes) |

> ⚠️ **Sem credenciais configuradas**, o envio falha com mensagem clara (dica de configuração no Vercel) — nunca com erro obscuro. O erro `535 BadCredentials` do Gmail significa senha de app ausente/errada (ver [Troubleshooting](#-troubleshooting)).

---

## 📦 O formato .BCK — anatomia completa

O `.BCK` é o arquivo de **exportação/importação oficial do SCNES** (CNES/DATASUS). O JARVIS o reproduz a partir de um arquivo real exportado pelo SCNES 4.8.40, validado em 3 camadas byte a byte.

### 🧱 Estrutura do container

```
┌─────────────────────────────────────────────┐
│ Cabeçalho + descrição                       │
│   "Exportação de Secretaria Mun P. Gestão   │
│    para Município P. Gestão em DD/MM/AAAA*CN"│
├─────────────────────────────────────────────┤
│ Entradas (68 tabelas + TXT [+ QRP opcional])│
│   Cada entrada: caminho (ex.: c:\users\...  │
│   \appdata\local\temp\lfces004.xml)         │
│   + timestamp + marcador EC2\0 + dados      │
├─────────────────────────────────────────────┤
│ Dados comprimidos em chunks zlib nível 1    │
│   (blocos de ~16 KB)                        │
├─────────────────────────────────────────────┤
│ Trailer                                     │
└─────────────────────────────────────────────┘
```

- **Compressão**: zlib nível 1 em chunks — reproduz **byte a byte** o que o SCNES gera
- **Total**: 69 entradas padrão (68 tabelas + TXT); com QRP, 70

### 🗂️ As 68 tabelas

Cada tabela é serializada como **DATAPACKET XML** (formato do Delphi/Bold): `<DATAPACKET>` com `METADATA` (schemas, campos, larguras, ORIGINs) e `<ROWDATA>` com uma `<ROW>` por registro. O JARVIS mantém as definições **verbatim** do arquivo real — campos, larguras e metadados idênticos:

| Tabela | Conteúdo (ficha de origem) |
|---|---|
| `LFCES004` | Estabelecimento — identificação e características (61 campos; fichas 1–2) |
| `LFCES006` | Atendimento prestado |
| `LFCES008` | Resíduos |
| `LFCES009` | Especializações / serviços especializados (Ficha 8) |
| `LFCES014` | Comissões (Ficha 4) |
| `LFCES015` | Instalações físicas (Ficha 6) **e** leitos por especialidade (Ficha 19) |
| `LFCES018` | Profissionais — dados pessoais (Fichas 20/21) |
| `LFCES019` | Serviços de apoio (Ficha 7) |
| `LFCES020` | Equipamentos — todos os grupos (Fichas 13–17) |
| `LFCES021` | Vínculos profissionais × estabelecimento (21 campos) — **posição 17 do pacote** |
| `LFCES055` | Histórico de exportação |
| `LFCES098` | Horários de funcionamento |
| + demais | `LFCES*`, `TFCES*`, `CFCES*` — tabelas de apoio e complementares (ex.: `LFCES023`, `LFCES027`, `LFCES032`…) |

> 🔑 **Detalhe de fidelidade**: os vínculos de profissionais ficam em `lfces021.xml` (posição 17) — correção aplicada após comparação com exportações reais (antes o pacote saía com `lfces004.xml` duplicado). O campo `CNES` dentro do `LFCES021` referencia `"LFCES004"."CNES"` na metadado — peculiaridade do SCNES preservada.

### 📄 TXT de transmissão

O `.BCK` carrega também um arquivo TXT com os parâmetros de transmissão, no mesmo padrão do SCNES real:

```
0
0
2
RO
110020
SEMUSA
4.8.40
<checksum-hex>
SCNES COMPLETO
```

**Nome do arquivo interno**: `cnes0ro110020<DDMMYYYY><HHMMSS><YYYY><versão>.txt` (ex.: `cnes0ro1100201108202612100720264840.txt`) — mesmo padrão do real.

### 📛 Nome do arquivo `.BCK`

O anexo do e-mail segue **sempre** o padrão de transmissão do SCNES:

```
CNES0RO1100201108202612100720264840.bck
│    ││      │   │          │    │
│    ││      │   │          │    └─ 4840 (dígitos da versão 4.8.40)
│    ││      │   │          └─ 2026 (ano)
│    ││      │   └─ 121007 (HHMMSS)
│    ││      └─ 11082026 (DDMMYYYY)
│    │└─ 110020 (código do município gestor)
│    └─ RO (UF)
└─ CNES0 (prefixo de transmissão)
```

Formato: `CNES0{UF}{COD_MUN_GESTOR}{DDMMYYYY}{HHMMSS}{YYYY}{versão}.bck`

### 🗃️ QRP (opcional)

Exportações reais do SCNES incluem um arquivo `.qrp` (relatório de protocolo de transmissão, binário, ~2,4 MB). O JARVIS tem **suporte opcional** (param `caminho_qrp` em `gerar_bck_bytes`), **desligado por padrão** — a documentação do DATASUS indica que **apenas o `.BCK` é necessário** para importação.

### ⚠️ Checksums internos (não reproduzidos)

- **CHECKSUM do vínculo (LFCES021)**: é determinístico por linha (99% idênticos entre exportações), mas o algoritmo interno do SCNES não é recuperável a partir do arquivo (16 funções de hash × ~1,5 milhão de combinações testadas). O JARVIS usa CRC32 da concatenação `unidade|prof|cbo|vínculo`.
- **Checksum hex do TXT**: constante nas exportações da mesma instalação — provavelmente derivado de configuração/máquina.

Ambos só serão confirmados (ou descartados) pelo teste de importação real no SCNES (ver [Validação](#-validação-no-scnes-de-teste)).

---

## ✉️ Fluxo de envio e segurança

```
[Usuário preenche fichas]                     [GECAV]
        │                                        ▲
        ▼                                        │
[.BCK gerado EM OCULTO] ──┐                     │
[PDF extrato gerado]      ├── SMTP Gmail ───────┘
[anexos opcionais]        │   (587/TLS, senha de app)
                          ▼
                gecav.semusa@portovelho.ro.gov.br
                (destinatário FIXO — sem Cc/Bcc)
```

1. O usuário preenche as fichas — **o CNES pode ficar vazio** (estabelecimento novo: a numeração é atribuída na importação)
2. **"✉ Enviar para GECAV"** gera o `.BCK` **em oculto** e anexa ao e-mail:
   - `.BCK` no padrão de transmissão (ex.: `CNES0RO110020....bck`)
   - `extrato_cnes.pdf`
   - anexos opcionais do usuário
3. **Não existe rota de download do `.BCK`** — acessível **somente** pelo e-mail da GECAV (rota `/gerar-bck` responde 404; o botão de download foi removido por decisão de design)
4. **Rate limit** anti-spam: intervalo mínimo (5 s) + teto por hora (30) entre envios — contador em memória

> 🔒 O `.BCK` é o arquivo de transmissão oficial — por isso o acesso é restrito: **somente o GECAV pode ter acesso a ele**.

---

## 📋 As fichas do cadastro

| Aba principal | Ficha | Conteúdo |
|---|---|---|
| **Cadastro** | 1 — Identificação | Operação, CNES, tipo, CNPJ/CPF, endereço, RT, alvará |
| | 2 — Caracterização | Esfera, ensino, hierarquia, clientela, turno, horários, atendimento |
| **Infraestrutura** | 4 — Comissões | 14 comissões da Ficha 4 |
| | 6 — Instalações | Consultórios, triagem, repouso, clínicas, cirurgia, pré-parto, parto, RN |
| | 7 — Apoio | SAME, farmácia, esterilização, lactário, lavanderia, ambulância… |
| | Resíduos | Biológicos, químicos, radioativos, comuns |
| | 19 — Leitos | 7 grupos: cirúrgicos, obstétricos, pediátricos, clínicos, outras, hospital-dia, complementares |
| **Equipamentos** | 13 — Diagnóstico/Infra | Mamógrafo, raio X, tomógrafo, ressonância, ultrassom, grupo gerador, usina de oxigênio… |
| | 14 — Ópticos | Endoscópios, microscópio, cadeira oftalmológica, refrator, campímetro… |
| | 15 — Gráficos/Vida | ECG, EEG, bomba de infusão, incubadora, desfibrilador, ventilador… |
| | 16 — Odontologia | Equipo, compressor, fotopolimerizador, canetas, amalgamador… |
| | 17 — Audiologia | Audiômetros, imitanciômetro, cabina acústica, emissões otoacústicas… |
| **Pessoas** | 20/21 — Profissionais | CBO (87 ocupações), conselho, carga horária, vínculo, especializações |
| | 8 — Serviços CBO | 22 serviços especializados com classificações oficiais |
| **Finalização** | Declaração | Modelo oficial de declaração PJ/PF (Port. GM 2.022/2017) |
| | Ações | Pré-visualizar PDF · Adicionar anexos · Baixar PDF · **Enviar para GECAV** |

---

## 📄 Geração do PDF (extrato)

O extrato é gerado com **ReportLab** (A4) e contém:

- **Cabeçalho institucional** com as 3 logos (Prefeitura | JARVIS | CNES)
- **Título**: "CNES — Extrato do Cadastro" + data/hora de geração
- **Seções em tabelas** (campo → valor), apenas com campos preenchidos:
  1. Identificação do Estabelecimento
  2. Caracterização
  3. Instalações Físicas (Ficha 6)
  4. Comissões (Ficha 4)
  5. Leitos (Ficha 19)
  6. Profissionais e especializações
  7. Equipamentos
  8. Serviços (Ficha 8)
  9. Declaração
- **Estilo**: grade azul-claro, cabeçalho de seção azul institucional (`#003057`), fonte 8,5 pt

> 📌 O PDF é **auxiliar** — o documento oficial com validade jurídica é o extrato autenticado via **GOV.br** no portal do Ministério da Saúde (a interface orienta o usuário nesse passo).

---

## ☁️ Deploy no Vercel

O projeto roda em produção em **https://jarvis-cnes.vercel.app** (Python 3.12, Flask serverless).

### Primeira vez

```bash
# 1. Vincular a pasta ao projeto
vercel link          # aponta para o projeto jarvis-cnes

# 2. Configurar as variáveis de ambiente de produção
vercel env add JARVIS_EMAIL production
vercel env add JARVIS_SENHA_APP production      # senha de app do Gmail
vercel env add JARVIS_DESTINATARIO production
vercel env add JARVIS_INTERVALO_MIN production
vercel env add JARVIS_LIMITE_HORA production

# 3. Deploy de produção
vercel --prod
```

### Redeploy (após `git push`)

```bash
vercel --prod --yes
```

> ⚠️ **Importante**: variáveis novas/alteradas só valem após um novo deploy. O `vercel link` cria `.env.local` e adiciona `.vercel`/`.env*` ao `.gitignore` (não versionar).

### Configuração do Python no Vercel

- Sem `pyproject.toml`/`.python-version`, o Vercel usa Python 3.12 por padrão
- Dependências instaladas a partir de `requirements.txt` automaticamente
- O app Flask é detectado e servido como serverless function

---

## 🧪 Testes automatizados

```bash
python -m pytest test_bck.py -v
```

### O que cada teste valida

| Teste | O que prova | Roda sempre? |
|---|---|---|
| **1 — Container** | `ler_bck` + reescrita dos chunks originais reproduz o `.BCK` real **exatamente** (integridade do parser) | ⏭️ só com os originais |
| **2 — Escritor** | `ler_bck → escrever_bck` (zlib nível 1) produz arquivo **byte a byte idêntico** ao do SCNES | ⏭️ só com os originais |
| **3 — DATAPACKET** | Regenera o XML das 68 tabelas a partir das linhas reais e compara **byte a byte** | ⏭️ só com os originais |
| **4 — Estrutura** | O `.BCK` do formulário é um pacote válido (69 entradas, integridade) + nome no padrão `CNES0RO110020...bck` | ✅ sempre |
| **5 — E-mail** | `.BCK` anexado com nome no padrão CNES + PDF, destinatário **somente** GECAV, sem Cc/Bcc (fake SMTP) | ✅ sempre |
| **6 — Rota** | Fluxo completo via HTTP: `.BCK` gerado em oculto, anexado ao e-mail (com e sem CNES), e `/gerar-bck` responde **404** | ✅ sempre |

**Resultado atual**: `3 passed, 3 skipped` (os testes 1–3 dependem dos arquivos originais, mantidos no backup local por conterem CPFs — ver [Segurança](#-segurança)).

**Envio de e-mail nos testes**: interceptado com SMTP falso — **nada é enviado de verdade**.

---

## ✅ Validação no SCNES de teste

O guia completo (baixar o SCNES, instalar Firebird no Windows 11, importar e conferir o log) está em **`VALIDACAO_BCK_SCNES.md`**. Resumo:

1. **Baixar** no Portal CNES: SCNES COMPLETO 4.8.40 + Firebird 1.5.5 (32 bits)
2. **Instalar**: Firebird primeiro (no Windows 10/11, renomeie o instalador para `Setup.exe` e execute como Administrador; use modo **"Executar como uma Aplicação"**)
3. **Importar**: SCNES → **Movimento → Importação** → selecionar o `.bck`
4. **Conferir**: **Movimento → Consistência** (erros impeditivos) e **Advertência**

> 🧪 Sequência recomendada: importe primeiro um `.BCK` original (controle), depois o do JARVIS.

---

## 🛠️ Troubleshooting

| Sintoma | Causa | Solução |
|---|---|---|
| `535 Username and Password not accepted` | Senha de app do Gmail ausente/errada no ambiente | Configure `JARVIS_EMAIL` + `JARVIS_SENHA_APP` (senha de **app**, 2FA ativa) e faça redeploy |
| `Credenciais de e-mail não configuradas` | Variáveis vazias no servidor | Configurar no Vercel → Settings → Environment Variables → redeploy |
| E-mail sai sem o `.BCK` | Versão antiga em produção (antes da correção) | Redeploy com a versão atual (geração **sempre** ativa) |
| Firebird não instala no Windows 11 | Instalador de 2009 bloqueado | Renomear para `Setup.exe` + executar como Admin + modo Aplicação |
| Rate limit disparando em teste | Contador de 5 s/30 h ativo | `JARVIS_RATE_LIMIT=0` (apenas testes) |
| Logo não aparece | Arquivo ausente ou nome errado | Colocar `logo_*.png/jpg/jpeg` na raiz (fallback automático) |

---

## 🧩 Limitações e divergências conhecidas

1. **Checksums internos do SCNES não reproduzidos** (CHECKSUM do vínculo LFCES021 e checksum hex do TXT) — o algoritmo é interno do SCNES; o impacto só pode ser medido no teste de importação real
2. **Testes 1–3 pulados no repositório** — dependem dos `.BCK`/XML originais, que ficam no backup local (contêm CPFs — não versionar)
3. **Rate limit em memória** — no Vercel (serverless multi-instância) o contador não é global entre instâncias
4. **`TP_SUS_NAO_SUS` fixo em "S"** — a base real tem mistura S/N (60/40); o valor é dado do cadastro, não da estrutura
5. **Configuração do município hardcoded** (`RO/110020/SEMUSA/4.8.40`) — para outro município, ajustar as constantes no topo do módulo `.BCK`

---

## 🔒 Segurança

- **`.BCK` oculto**: sem rota de download; acesso exclusivo por e-mail para a GECAV (decisão de design — um commit que re-adicionou o download foi **revertido**)
- **Sem Cc/Bcc** no envio: o destinatário é único e fixo
- **Segredos fora do código**: credenciais via variáveis de ambiente (Vercel) ou `.env` local — o `.env` está no `.gitignore`
- **Servidor sem debug**: Waitress em produção; dev server com `debug=False`
- **Dados sensíveis não versionados**: `analise_bck/` (extrações com CPFs) ignorado pelo git

> ⚠️ **ATENÇÃO — pendência de segurança**: o arquivo `.env.example` está versionado no GitHub e contém **valores reais** (credenciais), não placeholders. Recomenda-se: (1) trocar os valores por placeholders (`<SUA_SENHA_APP>`), (2) **rotacionar a senha de app** do Gmail, pois já pode ter sido exposta, e (3) atualizar a variável no Vercel.

---

## 🗺️ Roadmap

- [ ] **Teste de importação no SCNES** com o `.BCK` do JARVIS — fechar as 2 divergências de checksum (ou descartá-las)
- [ ] Reativar os testes 1–3 na suíte (restaurando originais localmente ou criando fixture)
- [ ] Fixar o achado de segurança do `.env.example` (placeholders + rotação da senha)
- [ ] Tornar a configuração do município parametrizável por ambiente (multi-município)
- [ ] CI no GitHub Actions (pytest a cada push)

---

## 📜 Sobre

**JARVIS CNES** — Sistema Auxiliar de Cadastramento (Web), versão 5.

Desenvolvido para a **SEMUSA — Secretaria Municipal de Saúde de Porto Velho/RO** · DRAC · CNES.

*Formato `.BCK` decodificado e validado a partir de exportações reais do SCNES 4.8.40.*

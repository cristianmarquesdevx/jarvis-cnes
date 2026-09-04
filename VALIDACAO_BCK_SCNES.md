# Validação do arquivo .BCK gerado pelo JARVIS numa instalação de teste do SCNES

Guia passo a passo para **validar em ambiente de teste** o arquivo `.BCK` que o JARVIS gera
em oculto e envia para a GECAV (`gecav.semusa@portovelho.ro.gov.br`).

> **⚠️ Importante antes de começar**
> - O `.BCK` é um **snapshot da base** (68 tabelas + arquivo de transmissão). A importação
>   **substitui/atualiza a base local** do SCNES. Use **sempre uma máquina de teste** (ou uma
>   instalação com cópia de segurança) — **nunca** a máquina de produção do município.
> - O arquivo contém **dados pessoais (CPFs, nomes)**. Trate com sigilo.
> - Este guia segue o fluxo oficial descrito na [wiki do CNES](https://wiki.saude.gov.br/cnes/)
>   e no portal do DATASUS. A versão do SCNES considerada é a **4.8.40** (a mesma do arquivo
>   original analisado).

---

## 1. O que você vai precisar

| Item | Detalhe |
|---|---|
| Computador Windows (XP/7/8/10/11) | O SCNES **só** roda em Windows (não homologado em Linux/Mac) |
| **Firebird 1.5.5 (32 bits)** | Pré-requisito do SCNES — mesmo em máquina 64 bits |
| **Java** | Pré-requisito do SCNES |
| **SCNES COMPLETO 4.8.40** | Instala a base zerada, pronta para importar |
| Acesso de **Administrador** no Windows | Necessário para instalar e executar o SCNES no Win 8/10/11 |

---

## 2. Onde baixar

Tudo é baixado do **Portal CNES** (oficial do Ministério da Saúde):

1. Acesse **https://cnes.datasus.gov.br** → menu **Downloads → Aplicativos**
   (link direto: `https://cnes.datasus.gov.br/pages/downloads/aplicativos.jsp`)
2. Baixe, nesta ordem:
   - **FIREBIRD** → `InstaladorFirebird-155.zip` → `Firebird-1.5.5.4926-3-Win32.exe`
   - **JAVA** (versão indicada no portal)
   - **VERSÃO SCNES (4.8.40) → SCNES COMPLETO** → `SCNESXXXX-COMPLETA.ZIP` → `SCNESXXXX-completa.exe`
3. Documentação de referência (mesma página, menu Downloads → Documentação):
   - *Manual de Instalação do SCNES e SCNES em Rede*
   - *Guia de Preenchimento SCNES* (wiki: `wiki.saude.gov.br/cnes`)

> Se a máquina de teste já tem SCNES instalado, a **instalação completa apaga a base local** —
> faça antes uma cópia de segurança (Menu **Segurança → Gerar cópia de Segurança**) ou use
> uma máquina limpa.

---

## 3. Instalação (resumo do passo a passo oficial)

1. **Firebird** (Win 8/10/11):
   - Clique com o botão direito no instalador → **Executar como Administrador**
   - Se o Windows bloquear a instalação, **renomeie o instalador para `Setup.exe`** e tente de novo
   - Componentes: manter **todos selecionados**, opção **"Binários Super Server"**
   - Win 8/10/11: executar como **"Aplicação"**; Win XP: executar como **"Serviço"**
   - Desmarque "Iniciar automaticamente" e "Copiar biblioteca para system" (recomendação oficial)
   - Reinicie a máquina ao final
2. **Java** — instale a versão indicada no portal.
3. **SCNES COMPLETO**:
   - Execute `SCNESXXXX-completa.exe` **como Administrador**
   - Pasta destino recomendada: `C:\Datasus\CNES`
   - Ao concluir, **leia o `leia_me.zip`** da versão (contém mudanças e alertas da competência)
4. **Sempre execute o SCNES como Administrador** no Win 8/10/11 (botão direito → Executar como Administrador).

---

## 4. Obter o .BCK de teste gerado pelo JARVIS

O JARVIS **não expõe o `.BCK` na interface** (acesso exclusivo GECAV). Para teste, use uma
das opções abaixo:

**Opção A — Pelo e-mail (fluxo real):**
1. Preencha as fichas no JARVIS (o **CNES** pode ficar vazio — para estabelecimento novo a numeração é atribuída na inclusão; o `.BCK` é gerado sempre)
2. Clique em **"✉ Enviar para GECAV"**
3. A GECAV recebe o e-mail com o anexo `.bck` no padrão de transmissão do SCNES
   (**`CNES0RO110020<data><hora><ano><versão>.bck`**, ex.: `CNES0RO1100201108202612100720264840.bck`)
   — salve-o na máquina de teste

**Opção B — Gerar localmente (sem e-mail):**
```python
import app
dados = {"f1_cnes": "0036757", "f1_operacao": "Inclusão", "f1_nome_empresarial": "TESTE LTDA"}
with open("teste_exportacao.bck", "wb") as f:
    f.write(app.gerar_bck_bytes(dados))
```
> O arquivo gerado por qualquer uma das opções é **idêntico em formato** — o mesmo gerador,
> comprovado byte a byte contra o `.BCK` original do SCNES (ver `test_bck.py`).

---

## 5. Validação offline ANTES de importar (opcional, recomendado)

Antes de subir no SCNES, confira o pacote com o próprio JARVIS:

```bash
python -m pytest test_bck.py -v        # suíte completa (inclui comparação byte a byte)
```

E uma checagem rápida do arquivo:

```python
import app
desc, total, entradas = app.ler_bck(open("teste_exportacao.bck", "rb").read())
print(len(entradas), "entradas (esperado: 69 = 68 tabelas + TXT)")
print(entradas[-1]["dados"].decode("latin-1"))   # TXT de transmissão
```

Confira no TXT: `0 / 0 / 2 / RO / 110020 / SEMUSA / 4.8.40 / <checksum 8 hex> / SCNES COMPLETO`.

---

## 6. Importar o .BCK no SCNES de teste

1. Abra o **SCNES** (como Administrador) e faça o login na base local
2. Menu **Movimento → Importação**
3. Selecione o arquivo **`.BCK`** gerado (ex.: `CNES0RO1100201108202612100720264840.bck`,
   no padrão de transmissão do SCNES)
4. Confirme a importação e aguarde o processamento (o sistema lê o container, descomprime as
   68 tabelas e grava na base Firebird)

> **Nota:** o fluxo oficial de *download da base do gestor* usa Menu **Utilitários → Carregar Base**
> com um `.zip`; o fluxo de **importação de arquivo de exportação** (nosso caso — `.BCK`) é o
> **Movimento → Importação**, conforme o [Guia de Instalação](https://wiki.saude.gov.br/cnes/index.php/Guia_de_Instala%C3%A7%C3%A3o_dos_Sistemas).

---

## 7. O que conferir no log / relatórios

O SCNES **não grava um "log de texto" da importação** — a conferência é feita pelos
**relatórios do próprio sistema** (menu **Movimento**) e pela consulta dos cadastros:

### 7.1 Relatório de erros/inconsistências da importação
- Menu **Movimento → Consistência** → **Executar consistência** → depois **Relatório da Última Consistência Realizada**
- A consistência é **impeditiva**: estabelecimento com crítica **não pode ser exportado**.
  O relatório lista cada campo inválido por estabelecimento.

### 7.2 Advertências
- Menu **Movimento → Advertência** → **Executar advertência** → **Relatório da Última Advertência Realizada**
- Informativo (não impede exportação), mas indica campos que devem ser revisados.

### 7.3 Conferir o cadastro importado
- Menu **Cadastros → Estabelecimentos** → pesquise o **CNES** usado no formulário
- Verifique aba a aba os dados vindos do JARVIS:

| Dado do JARVIS | Onde conferir no SCNES |
|---|---|
| Razão Social / Nome Fantasia / CNPJ | Aba Básico → Identificação Principal |
| Endereço, CEP, telefone, e-mail | Aba Básico → Endereço Complementar |
| Tipo de estabelecimento | Aba Básico → Identificação Principal |
| Atendimento prestado | Aba Básico → Atividades |
| Comissões | Aba Básico → Comissões |
| Instalações físicas / salas / leitos | Aba Conjunto → Instalações Físicas e Aba **Leitos** |
| Equipamentos | Aba Equipamentos → Equipamentos |
| Resíduos | Aba Equipamentos → Rejeitos |
| Serviços de apoio | Aba Conjunto → Serviços de Apoio |
| Profissionais (CBO, conselho, vínculo, carga horária) | Menu **Cadastros → Profissionais** e botão **Profissionais** do estabelecimento |
| Especializações | Aba Conjunto → Serviços Especializados |

### 7.4 Checar valores críticos gerados pelo JARVIS
- **Vínculo** `IND_VINC` = 6 dígitos (ex.: `010500`) — confira no cadastro do profissional
- **Conselho** `CONSELHOID` (ex.: `66` = COREN) e **número de registro** — confira no profissional
- **CBO** sem hífen (ex.: `223505`) — confira no profissional
- **Carga horária** (`CG_HORAAMB` etc.) — confira no profissional
- **Leitos** — o JARVIS escreve `QTDE_EXIST`/`QTDE_SUS`; confira na aba Leitos
- **CNES** com 7 dígitos — confira na Identificação Principal

### 7.5 Onde ficam os arquivos no disco (referência)
- Instalação (padrão recomendado): `C:\Datasus\CNES`
- Arquivos de exportação gerados pelo SCNES (caminho informado pelo próprio sistema, ex. do
  arquivo original analisado): `C:\Data Sus\CNES\` → `exp_cnes0...bck` / `exp_cnes0...qrp`
- Cópia de segurança local: Menu **Segurança → Gerar/Restaurar cópia de Segurança**

---

## 8. Teste de retorno (fechar o ciclo)

Depois que a importação validar o cadastro:

1. Menu **Movimento → Consistência** → o estabelecimento deve estar **sem críticas impeditivas**
2. Menu **Movimento → Exportação → Base** → gere um novo `.BCK` a partir da base de teste
3. **Confira o relatório impresso (QRP)** — o "Protocolo de Exportação" deve listar o
   estabelecimento corretamente (é o mesmo relatório que o SCNES embute dentro do `.BCK`)
4. Se o SCNES exportou sem erros, o fluxo está validado e o JARVIS pode ser usado em produção
   (com o acompanhamento da GECAV e da Plataforma Solicita CNES)

---

## 9. Checklist final

- [ ] Máquina de teste separada (ou cópia de segurança feita)
- [ ] Firebird 1.5.5 + Java instalados; SCNES COMPLETO 4.8.40 instalado
- [ ] SCNES aberto como Administrador
- [ ] `.BCK` obtido (via e-mail da GECAV ou gerado localmente) com **CNES preenchido**
- [ ] Validação offline OK (`python -m pytest test_bck.py -v`)
- [ ] Importado via **Movimento → Importação** sem erros
- [ ] **Consistência** executada: 0 críticas impeditivas no estabelecimento
- [ ] Cadastro conferido aba a aba (identificação, leitos, equipamentos, profissionais)
- [ ] **Exportação → Base** de retorno OK (ciclo completo)
- [ ] Dados sensíveis tratados com sigilo; teste apagado da máquina quando não for mais necessário

---

## 10. Referências oficiais

- Portal CNES — Downloads de Aplicativos: `https://cnes.datasus.gov.br/pages/downloads/aplicativos.jsp`
- Wiki CNES — Guia de Instalação dos Sistemas: `https://wiki.saude.gov.br/cnes/index.php/Guia_de_Instala%C3%A7%C3%A3o_dos_Sistemas`
- Wiki CNES — Guia de Preenchimento SCNES: `https://wiki.saude.gov.br/cnes/index.php/SCNES_-_Guia_de_Preenchimento`
- Instrutivo SCNES COMPLETO (Secretarias de Saúde): fluxo de exportação BCK+QRP e envio pela
  Plataforma Solicita CNES (documentos publicados pelas SES, ex.: rio.rj.gov.br / saude.prefeitura.rio)

#!/usr/bin/env python3
"""
Testes automatizados (pytest) — validação do gerador .BCK do JARVIS.

Valida o .BCK gerado contra o arquivo original exportado pelo SCNES,
byte a byte, em 4 camadas:

  1. Container (preservação)  — ler_bck + reescrita dos chunks originais
                                reproduz o arquivo EXATAMENTE (integridade do parser)
  2. Escritor (recompressão)  — ler_bck → escrever_bck (zlib nível 1) produz
                                o arquivo BYTE A BYTE idêntico ao do SCNES
  3. XML DATAPACKET           — para cada uma das 68 tabelas, regenerar o
                                DATAPACKET a partir das linhas originais e
                                comparar byte a byte com o XML extraído
  4. Fluxo JARVIS             — o .BCK gerado pelo formulário é um pacote
                                válido (mesma estrutura do original)

Rodar:  python -m pytest test_bck.py -v
Os testes 1–3 dependem dos arquivos originais extraídos nesta análise
("Documento de Cristian Marques (1)" e "export_cnes.xml"); sem eles,
são pulados automaticamente.
"""

import json
import os
import re
import struct
from datetime import datetime

import pytest

import app


def _caminho(nome):
    """Localiza artefatos de análise em analise_bck/ (ou na raiz, legacy)."""
    for base in ("analise_bck", "."):
        p = os.path.join(base, nome)
        if os.path.exists(p):
            return p
    return nome


ORIGINAL     = _caminho("Documento de Cristian Marques (1)")   # .BCK real do SCNES 4.8.40
XML_EXTRAIDO = _caminho("export_cnes.xml")                    # 24,9 MB — 68 DATAPACKET

# Só os testes 1–3 dependem do .BCK original / XML extraído (mantidos fora do
# repositório, em backup local); sem eles, são pulados. Os testes 4–6 rodam sempre.
PRECISA_ORIGINAL = pytest.mark.skipif(
    not os.path.exists(ORIGINAL),
    reason="Arquivo .BCK original não está presente (backup local fora do repositório)"
)

N_ENTRADAS_ORIGINAL = 70      # 68 tabelas + 1 TXT de transmissão + 1 QRP
N_TABELAS = 68                # quantidade de DATAPACKET no XML extraído


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════
def _segmentos_xml_bytes():
    """Fatia o XML extraído em 68 segmentos `<?xml ...></DATAPACKET>`, em bytes."""
    raw = open(XML_EXTRAIDO, "rb").read()
    starts = [m.start() for m in re.finditer(
        rb'<\?xml version="1\.0" encoding="ISO-8859-1"\?>\s*<DATAPACKET[ >]', raw)]
    ends = [m.end() for m in re.finditer(rb"</DATAPACKET>", raw)]
    assert len(starts) == len(ends) == N_TABELAS, \
        f"esperava {N_TABELAS} DATAPACKET, achei {len(starts)}"
    return [raw[s:e] for s, e in zip(starts, ends)]


def _unescape_xml(v):
    """Decodifica as entidades XML que o SCNES escreve, para o valor original
    (o escritor do JARVIS re-escapará, reproduzindo os mesmos bytes)."""
    return (v.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", "\"").replace("&apos;", "'")
             .replace("&amp;", "&"))


def _parse_rows(seg):
    """Extrai as linhas <ROW .../> como dicts com os atributos NA ORDEM original,
    decodificando as entidades XML (para que o re-escape reproduza os bytes)."""
    rows = []
    for m in re.finditer(rb"<ROW ([^>]*)/>", seg):
        attrs = re.findall(rb'([A-Z0-9_]+)="([^"]*)"', m.group(1))
        rows.append({k.decode("latin-1"): _unescape_xml(v.decode("latin-1"))
                     for k, v in attrs})
    return rows


def _bck_original_raw():
    return open(ORIGINAL, "rb").read()


def _dados_formulario_teste():
    """Payload no formato exato do coletarDados() do JARVIS (fichas preenchidas)."""
    return {
        "f1_operacao": "Inclusão", "f1_cnes": "0036757", "f1_tipo_estab": "05",
        "f1_cnpj": "01.957.226/0001-38",
        "f1_nome_empresarial": "CENTRO DE ANALISES CLINICAS DE PORTO VELHO LTDA",
        "f1_fantasia": "CEACLIN TESTE", "f1_cep": "76.804-034",
        "f1_endereco": "AV JATUARANA", "f1_numero": "5871",
        "f1_complemento": "LOTE 173", "f1_bairro": "NOVA FLORESTA",
        "f1_telefone": "69 30264560", "f1_email": "teste@ceaclin.com.br",
        "f1_administrador": "Dr. Carlos Mendes",
        "f1_conselho_rt": "CRM-RO 2268", "f1_alvara": "123/2026",
        "f1_alvara_data": "2026-08-10",
        "f2_esfera": "Municipal", "f2_turno": "Manhã e Tarde",
        "f2_dias_func": "Seg-Sex", "f2_horas_func": "07h-17h",
        "atendimento_prestado": ["01 - INTERNAÇÃO", "02 - AMBULATORIAL"],
        "residuos": ["Resíduos Biológicos", "Resíduos Químicos"],
        "f6_ue_med": "3", "f6_repouso_ped_salas": "2", "f6_repouso_ped_leitos": "4",
        "f6_cirurgia": "1", "f6_leitos_rn_normal": "6",
        "f6_amb_basicas": "2",
        "f4_001": "Sim", "f4_004": "Sim", "f4_002": "Não",
        "f4_internet": "Sim", "f4_tipo_conexao": "Fibra Óptica",
        "f4_telefonia_fixa": "Sim", "f4_telefonia_movel": "Sim",
        "eq_diag_imagem": [{"possui": False, "qtd": 0}] * 5 +
                          [{"possui": True, "qtd": 2}] +
                          [{"possui": False, "qtd": 0}] * 9,
        "eq_infra": [
            {"possui": True, "qtd": 1},
            {"possui": False, "qtd": 0},
            {"possui": False, "qtd": 0},
        ],
        "metodos": {"01": {"simnao": "sim", "existente": 1, "uso": 1}},
        "manutencao": {"14": {"simnao": "sim", "existente": 2, "uso": 2}},
        "leitos_cirurgicos": {"Cirurgia Geral": {"existente": "8", "sus": "8"}},
        "leitos_complementares": {"UTI Adulto": {"existente": "10", "sus": "10"}},
        "apoio": {"1": "Proprio", "2": "Terceirizado", "3": "Nao"},
        "especializacoes": [{"servico": "159", "classificacao": "004"}],
        "profissionais": [
            {"nome": "MARIA DA SILVA", "cpf": "000.011.642-44",
             "mae": "EDILENA DE SOUSA", "conselho": "COREN-RO 123456",
             "profissao": "2235-05", "ch": "30",
             "estabelecimento": "01 - VÍNCULO EMPREGATÍCIO",
             "empregador": "05 - CELETISTA"},
            {"nome": "JOSE SOUZA", "cpf": "000.015.562-40",
             "conselho": "CRM 2268", "profissao": "2251-25", "ch": "20",
             "estabelecimento": "02 - AUTÔNOMO",
             "empregador": "10 - PESSOA FÍSICA"},
        ],
    }


# ═══════════════════════════════════════════════════════════════
#  1) Container — integridade do parser (reescrita dos chunks originais)
# ═══════════════════════════════════════════════════════════════
@PRECISA_ORIGINAL
def test_1_container_reescrita_preserva_bytes():
    raw = _bck_original_raw()
    desc, total, entradas = app.ler_bck(raw)

    assert len(entradas) == N_ENTRADAS_ORIGINAL
    assert sum(len(e["dados"]) for e in entradas) == total

    # reconstrói copiando os bytes comprimidos originais (não recomprime)
    out = bytearray()
    desc_b = desc.encode("latin-1")
    out += struct.pack("<I", len(desc_b)) + desc_b
    out += struct.pack("<I", total)
    pos = 8 + len(desc_b)
    for e in entradas:
        plen = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        hdr_end = pos + 8 + plen + 8            # lead + pathlen + path + ts + "EC2\0"
        out += raw[pos:hdr_end]
        pos = hdr_end
        while pos < len(raw) - 4:
            size = struct.unpack("<I", raw[pos:pos + 4])[0]
            if size <= 0 or pos + 4 + size > len(raw):
                break
            out += raw[pos:pos + 4 + size]
            pos += 4 + size
    out += b"\x00" * 8

    assert bytes(out) == raw, "reescrita com chunks originais difere do arquivo!"


# ═══════════════════════════════════════════════════════════════
#  2) Escritor — recompressão zlib nível 1 reproduz o SCNES byte a byte
# ═══════════════════════════════════════════════════════════════
@PRECISA_ORIGINAL
def test_2_escritor_recomprime_byte_a_byte():
    raw = _bck_original_raw()
    desc, total, entradas = app.ler_bck(raw)

    bck = app.escrever_bck(desc, [
        {"path": e["path"], "ts": e["ts"], "dados": e["dados"]}
        for e in entradas
    ])

    assert len(bck) == len(raw), \
        f"tamanho difere: gerado {len(bck)} vs original {len(raw)}"
    assert bck == raw, "zlib nível 1 NÃO reproduziu os bytes exatos do SCNES"


# ═══════════════════════════════════════════════════════════════
#  3) XML — DATAPACKET regenerado byte a byte para as 68 tabelas
# ═══════════════════════════════════════════════════════════════
@PRECISA_ORIGINAL
def test_3_datapacket_xml_byte_a_byte_68_tabelas():
    segmentos = _segmentos_xml_bytes()
    assert len(segmentos) == N_TABELAS

    for i, tabela in enumerate(app.ORDEM):
        seg_original = segmentos[i]

        linhas = _parse_rows(seg_original)
        regenerado = app.datapacket_xml(tabela, linhas, pack_idx=0)

        assert regenerado == seg_original, (
            f"tabela {tabela} (posição {i}) — XML regenerado difere byte a byte!\n"
            f"  original  : {seg_original[:120]!r}\n"
            f"  regenerado: {regenerado[:120]!r}"
        )


# ═══════════════════════════════════════════════════════════════
#  Fakes
# ═══════════════════════════════════════════════════════════════
class _FakeSMTP:
    """Intercepta smtplib.SMTP — captura as mensagens sem enviar e-mail real.
    Suporta o uso como context manager (a rota usa `with smtplib.SMTP(...) as s:`)."""
    instances = []

    def __init__(self, *args, **kwargs):
        self.mensagens = []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, *args, **kwargs):
        pass

    def send_message(self, msg):
        self.mensagens.append(msg)
        return {}


def _anexos(msg):
    """Lista de (nome_do_anexo, payload_bytes) de uma mensagem MIME."""
    out = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        nome = part.get_filename()
        if nome:
            out.append((nome, part.get_payload(decode=True)))
    return out


def _regex_nome_bck_padrao():
    """Regex do nome do .BCK no padrão de transmissão do SCNES:
    CNES0{UF}{COD_MUN_GESTOR}{14 dígitos (DDMMYYYYHHMMSS)}{YYYY}{versao}.bck
    (ex.: CNES0RO1100201108202612100720264840.bck)."""
    versao_dig = "".join(d for d in app.VERSAO if d.isdigit())
    return re.compile(rf"CNES0{app.UF}{app.COD_MUN_GESTOR}\d{{14}}\d{{4}}{versao_dig}\.bck")


def _nome_bck_do_anexo(anexos):
    """Nome do anexo .bck na lista de (nome, payload) — o único .bck."""
    return next(n for n, _ in anexos if n.lower().endswith(".bck"))


# ═══════════════════════════════════════════════════════════════
#  5) E-mail — .BCK oculto anexado, destinatário somente GECAV
# ═══════════════════════════════════════════════════════════════
def test_5_email_bck_anexado_somente_gecav(monkeypatch, tmp_path):
    """enviar_email_com_pdf anexa o .BCK com nome no padrão de transmissão do
    SCNES (CNES0RO110020....bck) e envia somente para
    gecav.semusa@portovelho.ro.gov.br (sem Cc/Bcc)."""
    monkeypatch.setattr(app.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.instances.clear()

    dados = _dados_formulario_teste()
    pdf = tmp_path / "extrato_cnes.pdf"
    bck = tmp_path / "exportacao_scnes.bck"
    app.gerar_pdf_completo(dados, str(pdf))
    bck.write_bytes(app.gerar_bck_bytes(dados))

    ok, msg_status = app.enviar_email_com_pdf(dados, str(pdf), None, str(bck))
    assert ok, msg_status
    assert len(_FakeSMTP.instances) == 1
    enviada = _FakeSMTP.instances[0].mensagens[0]

    # destinatário: somente a GECAV, sem cópia para ninguém
    assert enviada["To"] == "gecav.semusa@portovelho.ro.gov.br"
    assert not enviada.get("Cc")
    assert not enviada.get("Bcc")

    # anexos: PDF + .BCK com nome no padrão de transmissão do SCNES
    anexos = _anexos(enviada)
    nomes = sorted(n for n, _ in anexos)
    nome_bck = _nome_bck_do_anexo(anexos)
    assert _regex_nome_bck_padrao().fullmatch(nome_bck)
    assert nomes == [nome_bck, "extrato_cnes.pdf"]

    # o .BCK anexado é um pacote válido (69 entradas: 68 tabelas + TXT)
    bck_bytes = dict(anexos)[_nome_bck_do_anexo(anexos)]
    desc, total, entradas = app.ler_bck(bck_bytes)
    assert len(entradas) == 69
    assert sum(len(e["dados"]) for e in entradas) == total
    assert bck_bytes == app.gerar_bck_bytes(dados)


# ═══════════════════════════════════════════════════════════════
#  6) Rota /enviar-email — .BCK gerado em oculto e enviado junto
# ═══════════════════════════════════════════════════════════════
def test_6_rota_enviar_email_bck_oculto(monkeypatch):
    """Fluxo completo via HTTP: o servidor gera o .BCK em oculto, anexa ao
    e-mail da GECAV, e não existe rota de download do .BCK."""
    monkeypatch.setattr(app.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.instances.clear()

    dados = _dados_formulario_teste()
    form = {}
    for k, v in dados.items():
        form[k] = json.dumps(v) if isinstance(v, (list, dict)) else str(v)

    # rate limit desligado para o teste
    monkeypatch.setenv("JARVIS_RATE_LIMIT", "0")
    client = app.app.test_client()
    resp = client.post("/enviar-email", data=form)
    assert resp.status_code == 200
    status = resp.get_json()["status"]
    assert "sucesso" in status and "com .BCK" in status

    enviada = _FakeSMTP.instances[-1].mensagens[-1]
    assert enviada["To"] == "gecav.semusa@portovelho.ro.gov.br"
    anexos = _anexos(enviada)
    assert _regex_nome_bck_padrao().fullmatch(_nome_bck_do_anexo(anexos))
    assert "extrato_cnes.pdf" in dict(anexos)

    # corpo do e-mail menciona o anexo interno da GECAV
    corpo = "".join(p.get_payload(decode=True).decode("utf-8", "replace")
                     for p in enviada.walk()
                     if p.get_content_type() == "text/plain")
    assert "uso exclusivo GECAV" in corpo
    assert "CNES0RO110020" in corpo

    # SEM CNES o .BCK também é gerado: o cadastro serve justamente para gerar
    # a numeração CNES de estabelecimentos novos (não se exige CNES preenchido)
    _FakeSMTP.instances.clear()
    resp2 = client.post("/enviar-email", data={"f1_nome_empresarial": "SEM CNES"})
    assert resp2.status_code == 200
    assert "com .BCK" in resp2.get_json()["status"]
    enviada2 = _FakeSMTP.instances[-1].mensagens[-1]
    anexos2 = dict(_anexos(enviada2))
    assert _regex_nome_bck_padrao().fullmatch(_nome_bck_do_anexo(list(anexos2.items())))
    assert "extrato_cnes.pdf" in anexos2

    # não existe rota de download do .BCK (removida — acesso apenas via e-mail)
    assert client.get("/gerar-bck").status_code == 404


# ═══════════════════════════════════════════════════════════════
#  4) Fluxo JARVIS — .BCK do formulário é um pacote válido
# ═══════════════════════════════════════════════════════════════
def test_4_bck_do_formulario_estrutura_valida():
    dados = _dados_formulario_teste()
    bck = app.gerar_bck_bytes(dados)

    desc, total, entradas = app.ler_bck(bck)

    # 68 tabelas + TXT de transmissão (sem QRP: não é gerado)
    assert len(entradas) == 69
    assert sum(len(e["dados"]) for e in entradas) == total

    # ordem e nomes dos arquivos seguem o padrão do SCNES
    for i, e in enumerate(entradas[:N_TABELAS]):
        tabela = app.ORDEM[i]
        assert e["path"].endswith(f"\\{tabela.lower()}.xml"), e["path"]

    # TXT de transmissão no formato oficial
    txt = entradas[-1]["dados"].decode("latin-1")
    linhas_txt = txt.split("\r\n")
    assert linhas_txt[0:5] == ["0", "0", "2", app.UF, app.COD_MUN_GESTOR]
    assert linhas_txt[6] == app.VERSAO
    assert re.fullmatch(r"[0-9A-F]{8}", linhas_txt[7])      # checksum 8 hex
    assert linhas_txt[8] == "SCNES COMPLETO"

    # nome do TXT no padrão real do SCNES: cnes0<uf><mun><timestamp><ano><dígitos da versão>.txt
    nome_txt = entradas[-1]["path"].split("\\")[-1]
    versao_dig = "".join(d for d in app.VERSAO if d.isdigit())
    assert nome_txt.startswith(f"cnes0{app.UF.lower()}{app.COD_MUN_GESTOR}")
    assert nome_txt.endswith(f"{datetime.now():%Y}{versao_dig}.txt")

    # identificação do estabelecimento (posição 4) preenchida
    xml_estab = entradas[4]["dados"].decode("latin-1")
    assert 'CNES="0036757"' in xml_estab
    assert 'R_SOCIAL="CENTRO DE ANALISES CLINICAS DE PORTO VELHO LTDA"' in xml_estab

    # vínculos na tabela LFCES021 (posição 17), como na exportação real do SCNES
    assert entradas[17]["path"].endswith("\\lfces021.xml")
    xml_vinculos = entradas[17]["dados"].decode("latin-1")
    assert xml_vinculos.count("<ROW ") == 2
    assert 'COD_CBO="223505"' in xml_vinculos
    assert 'IND_VINC="010500"' in xml_vinculos
    assert 'CONSELHOID="66"' in xml_vinculos          # COREN
    assert 'CHECKSUM="' in xml_vinculos

    # round-trip: reler o gerado não altera o conteúdo
    desc2, total2, entradas2 = app.ler_bck(app.escrever_bck(
        desc, [{"path": e["path"], "ts": e["ts"], "dados": e["dados"]} for e in entradas]))
    assert [e["dados"] for e in entradas2] == [e["dados"] for e in entradas]

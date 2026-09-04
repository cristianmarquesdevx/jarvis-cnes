#!/usr/bin/env python3
"""
JARVIS CNES — Sistema Auxiliar de Cadastramento (Web) — VERSÃO 5
Refatorado: estrutura modular, CSS consolidado, patches visuais aplicados.
Logo superior direita com mesmo estilo visual da logo central.
Declaração compacta. Todos os campos e funcionalidades preservados.
"""

import os, re, json, tempfile, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ─────────────────────────────────────────────────────────────
#  AMBIENTE (.env) — segredos NUNCA no código
# ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _carregar_env():
    """Lê o arquivo .env (mesma pasta do app) e injeta no ambiente.
    Formato simples: CHAVE=valor por linha (suporta aspas simples/duplas)."""
    p = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(p):
        return
    for linha in open(p, encoding="utf-8"):
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


_carregar_env()

# ─────────────────────────────────────────────────────────────
#  CONFIGURAÇÕES DE E-MAIL (via .env / variáveis de ambiente)
# ─────────────────────────────────────────────────────────────
EMAIL_REMETENTE   = os.environ.get("JARVIS_EMAIL", "cnespvh1@gmail.com")
SENHA_APP         = os.environ.get("JARVIS_SENHA_APP", "")
DESTINATARIO_FIXO = os.environ.get("JARVIS_DESTINATARIO",
                                   "gecav.semusa@portovelho.ro.gov.br")



# ─────────────────────────────────────────────────────────────
#  VALIDAÇÃO CPF / CNPJ
# ─────────────────────────────────────────────────────────────
def _so_digitos(v):
    return re.sub(r'\D', '', v)

def validar_cpf(cpf):
    c = _so_digitos(cpf)
    if len(c) != 11 or len(set(c)) == 1:
        return False
    for i in range(2):
        s = sum(int(c[j]) * (10 + i - j) for j in range(9 + i))
        if (s * 10 % 11) % 11 != int(c[9 + i]):
            return False
    return True

def validar_cnpj(cnpj):
    c = _so_digitos(cnpj)
    if len(c) != 14 or len(set(c)) == 1:
        return False
    for idx, pesos in enumerate([[5,4,3,2,9,8,7,6,5,4,3,2],[6,5,4,3,2,9,8,7,6,5,4,3,2]]):
        s = sum(int(c[i]) * pesos[i] for i in range(12 + idx))
        d = 0 if s % 11 < 2 else 11 - (s % 11)
        if d != int(c[12 + idx]):
            return False
    return True

def validar_cpf_cnpj(valor):
    d = _so_digitos(valor)
    if len(d) == 11: return validar_cpf(d)
    if len(d) == 14: return validar_cnpj(d)
    return False

# ─────────────────────────────────────────────────────────────
#  TABELA CBO
# ─────────────────────────────────────────────────────────────
cbo_dict = {
    "7823-20":"CONDUTOR DE AMBULÂNCIA","2235-**":"ENFERMEIROS E AFINS","3222-05":"TÉCNICO DE ENFERMAGEM",
    "3222-30":"AUXILIAR DE ENFERMAGEM","2251-25":"MÉDICO CLÍNICO - CLÍNICO GERAL","2252-60":"MÉDICO NEUROCIRURGIÃO",
    "2252-70":"MÉDICO ORTOPEDISTA E TRAUMATOLOGISTA","2252-25":"MÉDICO CIRURGIÃO GERAL",
    "2251-12":"MÉDICO NEUROLOGISTA","2251-51":"MÉDICO ANESTESIOLOGISTA","2235-05":"ENFERMEIRO",
    "2236-05":"FISIOTERAPEUTA","2516-05":"ASSISTENTE SOCIAL","2237-10":"NUTRICIONISTA",
    "2238-10":"FONOAUDIÓLOGO","2252-35":"MÉDICO CIRURGIÃO PLÁSTICO","2251-33":"MÉDICO PSIQUIATRA",
    "2251-24":"MÉDICO PEDIATRA","2251-20":"MÉDICO CARDIOLOGISTA","2251-27":"MÉDICO PNEUMOLOGISTA",
    "2252-50":"MÉDICO GINECOLOGISTA E OBSTETRA","2252-03":"MÉDICO CIRURGIÃO VASCULAR",
    "2252-10":"MÉDICO CIRURGIÃO CARDIOVASCULAR","2253-20":"MÉDICO EM RADIOLOGIA E DIAGNÓSTICO POR IMAGEM",
    "3241-15":"TÉCNICO EM RADIOLOGIA E IMAGENOLOGIA","2251-42":"MÉDICO DA ESTRATÉGIA DE SAÚDE DA FAMÍLIA",
    "2251-03":"MÉDICO INFECTOLOGISTA","2232-08":"CIRURGIÃO-DENTISTA CLÍNICO GERAL",
    "2234-05":"FARMACÊUTICO","3251-15":"TÉCNICO EM FARMÁCIA","3513-05":"TÉCNICO ADMINISTRATIVO",
    "2252-75":"MÉDICO OTORRINOLARINGOLOGISTA","2252-85":"MÉDICO UROLOGISTA",
    "2235-65":"ENFERMEIRO DA ESTRATÉGIA DE SAÚDE DA FAMÍLIA","2235-45":"ENFERMEIRO OBSTÉTRICO",
    "5151-15":"PARTEIRA","2235-60":"ENFERMEIRO SANITARISTA","2239-05":"TERAPEUTA OCUPACIONAL",
    "2251-09":"MÉDICO NEFROLOGISTA","2251-55":"MÉDICO ENDOCRINOLOGISTA",
    "2251-65":"MÉDICO GASTROENTEROLOGISTA","2251-48":"MÉDICO ANATOMOPATOLOGISTA",
    "2253-35":"MÉDICO PATOLOGISTA CLÍNICO","2253-05":"MÉDICO CITOPATOLOGISTA",
    "2232-44":"CIRURGIÃO DENTISTA PATOLOGISTA BUCAL","2234-10":"FARMACÊUTICO BIOQUÍMICO",
    "2211-05":"BIÓLOGO / BIOMÉDICO","2212-05":"BIOMÉDICO","2234-15":"FARMACÊUTICO ANALISTA CLÍNICO",
    "2232-60":"CIRURGIÃO DENTISTA RADIOLOGISTA","2251-15":"MÉDICO ANGIOLOGISTA",
    "2252-55":"MÉDICO MASTOLOGISTA","2253-15":"MÉDICO EM MEDICINA NUCLEAR",
    "2251-85":"MÉDICO HEMATOLOGISTA","2251-90":"MÉDICO HEMOTERAPEUTA",
    "2252-20":"MÉDICO CIRURGIÃO DO APARELHO DIGESTIVO","2252-15":"MÉDICO CIRURGIÃO DE CABEÇA E PESCOÇO",
    "2251-22":"MÉDICO CANCEROLOGISTA PEDIÁTRICO","2251-21":"MÉDICO ONCOLOGISTA CLÍNICO",
    "2253-30":"MÉDICO RADIOTERAPEUTA","2131-55":"FÍSICO NUCLEAR","2252-90":"MÉDICO CANCEROLOGISTA CIRÚRGICO",
    "2263-20":"NATURÓLOGO","3221-05":"TÉCNICO EM ACUPUNTURA","5151-05":"AGENTE COMUNITÁRIO DE SAÚDE",
    "3224-10":"PROTÉTICO DENTÁRIO","3224-15":"AUXILIAR EM SAÚDE BUCAL","3224-25":"TÉCNICO EM SAÚDE BUCAL ESF",
    "3224-30":"AUXILIAR EM SAÚDE BUCAL ESF","2241-**":"PROFISSIONAL DE EDUCAÇÃO FÍSICA",
    "2394-15":"PEDAGOGO","5162-20":"CUIDADOR EM SAÚDE","3222-20":"TÉCNICO DE ENFERMAGEM PSIQUIÁTRICA",
    "3222-45":"TÉCNICO DE ENFERMAGEM ESF","3222-50":"AUXILIAR DE ENFERMAGEM ESF",
    "3242-05":"TÉCNICO EM PATOLOGIA CLÍNICA","2251-75":"MÉDICO GENETICISTA",
    "2251-18":"MÉDICO NUTROLOGISTA","2252-80":"MÉDICO COLOPROCTOLOGISTA",
    "2252-40":"MÉDICO CIRURGIÃO TORÁCICO","2252-30":"MÉDICO CIRURGIÃO PEDIÁTRICO",
    "2253-10":"MÉDICO EM ENDOSCOPIA","5153-05":"EDUCADOR SOCIAL","2233-05":"MÉDICO VETERINÁRIO",
    "3223-05":"TÉCNICO EM ÓTICA E OPTOMETRIA","2252-**":"MÉDICOS EM ESPECIALIDADES CIRÚRGICAS",
    "2253-**":"MÉDICOS EM MEDICINA DIAGNÓSTICA",
}

# ─────────────────────────────────────────────────────────────
#  LISTAS DE EQUIPAMENTOS
# ─────────────────────────────────────────────────────────────
EQUIP_DIAG_IMAGEM = [
    "Mamógrafo com Comando Simples","Mamógrafo com Estereotaxia",
    "Raio X até 100 mA","Raio X de 100 a 500 mA","Raio X mais de 500 mA",
    "Raio X Dentário","Raio X com Fluoroscopia","Raio X para Densitometria Óssea",
    "Raio X para Hemodinâmica","Tomógrafo Computadorizado","Ressonância Magnética",
    "Ultra-som Doppler Colorido","Ultra-som Ecógrafo","Ultra-som Convencional",
    "Processadora de Filme Exclusiva para Mamografia",
]
EQUIP_INFRA = ["Controle Ambiental/Ar-condicionado Central","Grupo Gerador","Usina de Oxigênio"]
EQUIP_OPTICOS = [
    "Endoscópio das Vias Respiratórias","Endoscópio das Vias Urinárias",
    "Endoscópio Digestivo","Equipamentos para Optometria","Laparoscópio/Vídeo",
    "Microscópio Cirúrgico","Cadeira Oftalmológica","Coluna Oftalmológica",
    "Refrator","Lensômetro","Projetor ou Tabela de Optótipos","Retinoscópio",
    "Oftalmoscópio","Ceratômetro","Tonômetro de Aplanação",
    "Biomicroscópio (Lâmpada de Fenda)","Campímetro",
]
METODOS_GRAFICOS = [("01","Eletrocardiógrafo"),("02","Eletroencefalógrafo")]
MANUTENCAO_VIDA = [
    ("01","Bomba/Balão Intra-aórtico"),("02","Bomba de Infusão"),("03","Berço Aquecido"),
    ("04","Bilirrubinômetro"),("05","Debitômetro"),("06","Desfibrilador"),
    ("07","Equipamento de Fototerapia"),("08","Incubadora"),("09","Marcapasso Temporário"),
    ("10","Monitor de ECG"),("11","Monitor de Pressão Invasivo"),("12","Monitor de Pressão não-Invasivo"),
    ("13","Reanimador Pulmonar/Ambu"),("14","Respirador/Ventilador"),
]
EQUIP_ODONTO = [
    "Equipo Odontológico Completo","Compressor Odontológico","Fotopolimerizador",
    "Caneta de Alta Rotação","Caneta de Baixa Rotação","Amalgamador",
    "Aparelho de Profilaxia com Jato de Bicarbonato",
]
EQUIP_OUTROS = [
    "Aparelho de Diatermia por Ultra-som/Ondas Curtas","Aparelho de Eletroestimulação",
    "Bomba de Infusão de Hemoderivados","Equipamentos de Aférese",
    "Equipamento de Circulação Extracorpórea","Equipamento para Hemodiálise","Forno de Bier",
]
EQUIP_AUDIO = [
    "Emissões Otoacústicas Evocadas Transientes",
    "Emissões Otoacústicas Evocadas por Produto de Distorção",
    "Potencial Evocado Auditivo de Tronco Encefálico Automático",
    "Potencial Evocado Auditivo de Tronco Encefálico de Curta, Média e Longa Latência",
    "Audiômetro de um Canal","Audiômetro de dois Canais","Imitanciômetro",
    "Imitanciômetro multifreqüencial","Cabina acústica","Sistema de campo livre",
    "Sistema completo de reforço visual (VRA)","Ganho de inserção","HI-PRO",
]

# ─────────────────────────────────────────────────────────────
#  SERVIÇOS DE APOIO / RESÍDUOS
# ─────────────────────────────────────────────────────────────
SERVICOS_APOIO = [
    "SAME ou SPP","Serviço Social","Farmácia",
    "Central de Esterilização de Materiais","Nutrição e Dietética (S.N.D.)",
    "Lactário","Banco de Leite","Lavanderia","Serviço de Manutenção de Equipamentos",
    "Ambulância","Necrotério",
]
OPCOES_REJEITOS = ["Resíduos Biológicos","Resíduos Químicos","Rejeitos Radioativos","Resíduos Comuns","Nenhum"]

# ─────────────────────────────────────────────────────────────
#  LEITOS
# ─────────────────────────────────────────────────────────────
LEITOS_CIRURGICOS = [
    "Buco Maxilo Facial","Cardiologia","Cirurgia Geral","Endocrinologia","Gastroenterologia",
    "Ginecologia","Nefrologia/Urologia","Neurocirurgia","Oftalmologia","Oncologia",
    "Ortopedia/Traumatologia","Otorrinolaringologia","Plástica","Toráxica","Transplante",
]
LEITOS_OBSTETRICOS = ["Obstetrícia Clínica","Obstetrícia Cirúrgica"]
LEITOS_PEDIATRICOS = ["Pediatria Clínica","Pediatria Cirúrgica"]
LEITOS_CLINICOS = [
    "AIDS","Cardiologia","Clínica Geral","Dermatologia","Geriatria","Hansenologia",
    "Hematologia","Nefrologia/Urologia","Neonatologia","Neurologia","Oncologia","Pneumologia",
]
LEITOS_OUTRAS = [
    "Crônicos","Psiquiatria","Reabilitação","Pneumologia Sanitária (Tisiologia)",
    "Cirúrgico/Diagnóstico/Terapêutico","AIDS","Fibrose Cística","Intercorrência Pós-transplante",
    "Geriatria","Saúde Mental",
]
LEITOS_HOSPITAL_DIA = [
    "Cirúrgico/Diagnóstico/Terapêutico","AIDS","Fibrose Cística",
    "Intercorrência Pós-transplante","Geriatria","Saúde Mental","Acolhimento Noturno",
]
LEITOS_COMPLEMENTARES = [
    "UTI Adulto","UTI Pediátrica","UTI Neonatal","UTI Queimados",
    "Unidade Intermediária","Unidade Intermediária Neonatal","Unidade de Isolamento",
    "UCO tipo II","UCO tipo III",
]

# ─────────────────────────────────────────────────────────────
#  COMISSÕES FICHA 4
# ─────────────────────────────────────────────────────────────
COMISSOES_F4 = [
    ("001","Ética Médica"),("002","Ética de Enfermagem"),("003","Farmácia e Terapêutica"),
    ("004","Controle de Infecção Hospitalar"),("005","Apropriação de Custos"),
    ("006","CIPA"),("007","Revisão de Prontuários"),("008","Revisão de Documentação Médica"),
    ("009","Análise de Óbitos e Biópsias"),("010","Investigação Epidemiológica"),
    ("011","Notificação de Doenças"),("012","Controle de Zoonoses e Vetores"),
    ("013","Mortalidade Materna"),("014","Mortalidade Neonatal"),
]

# ─────────────────────────────────────────────────────────────
#  SERVIÇOS CBO — FICHA 8
# ─────────────────────────────────────────────────────────────
SERVICOS_CBO = {
    "103":{"desc":"SERVIÇO DE ATENDIMENTO MÓVEL DE URGÊNCIAS","classificacoes":{
        "001":{"desc":"AMBULÂNCIA DE TRANSPORTE"},"002":{"desc":"UNIDADE SUPORTE BÁSICO (USB)"},
        "003":{"desc":"UNIDADE SUPORTE AVANÇADO (USA)"},"005":{"desc":"USB EMBARCAÇÃO"},
        "006":{"desc":"VEÍCULOS DE INTERVENÇÃO RÁPIDA"},"007":{"desc":"OUTROS VEÍCULOS"},
        "008":{"desc":"AMBULÂNCIA DE RESGATE"},"010":{"desc":"MOTOLÂNCIA"},
        "011":{"desc":"USA EMBARCAÇÃO"},"012":{"desc":"SUPORTE AVANÇADO AEROMÉDICO"},
    }},
    "104":{"desc":"REGULAÇÃO ASSISTENCIAL","classificacoes":{
        "001":{"desc":"REGULAÇÃO DE INTERNAÇÃO HOSPITALAR"},"003":{"desc":"CENTRAL DE REGULAÇÃO DAS URGÊNCIAS"},
        "006":{"desc":"REGULAÇÃO ESTADUAL ALTA COMPLEXIDADE"},"007":{"desc":"REGULAÇÃO NACIONAL ALTA COMPLEXIDADE"},
        "008":{"desc":"REGULAÇÃO AMBULATORIAL MÉDIA COMPLEXIDADE"},"009":{"desc":"REGULAÇÃO AMBULATORIAL ALTA COMPLEXIDADE"},
    }},
    "112":{"desc":"ATENÇÃO AO PRÉ-NATAL, PARTO E NASCIMENTO","classificacoes":{
        "001":{"desc":"PRÉ-NATAL BAIXO RISCO"},"002":{"desc":"PRÉ-NATAL ALTO RISCO"},
        "003":{"desc":"PARTO RISCO HABITUAL"},"004":{"desc":"PARTO ALTO RISCO"},
        "005":{"desc":"CENTRO DE PARTO NORMAL"},"006":{"desc":"CASA DA GESTANTE, BEBÊ E PUÉRPERA"},
        "007":{"desc":"SEGUIMENTO RN EGRESSO DE UTI"},"008":{"desc":"ATENÇÃO GESTANTE ALTO RISCO (AGAR)"},
    }},
    "114":{"desc":"ATENÇÃO ESPECIALIZADA EM SAÚDE BUCAL","classificacoes":{
        "001":{"desc":"DENTÍSTICA"},"002":{"desc":"ENDODONTIA"},"003":{"desc":"PERIODONTIA CLÍNICA"},
        "004":{"desc":"MOLDAGEM/MANUTENÇÃO"},"005":{"desc":"CIRURGIA ORAL"},
        "006":{"desc":"CIRURGIA BUCO-MAXILO FACIAL"},"007":{"desc":"ATENDIMENTO À PESSOA COM DEFICIÊNCIA"},
        "008":{"desc":"ODONTOPEDIATRIA"},"009":{"desc":"DISFUNÇÃO TEMPOROMANDIBULAR"},
        "010":{"desc":"ESTOMATOLOGIA"},"011":{"desc":"IMPLANTODONTIA"},
        "012":{"desc":"ODONTOGERIATRIA"},"013":{"desc":"ORTODONTIA"},
        "014":{"desc":"PRÓTESE DENTÁRIA"},"015":{"desc":"RADIOLOGIA ODONTOLÓGICA"},
        "016":{"desc":"ACUPUNTURA NA ODONTOLOGIA"},"017":{"desc":"ORTOPEDIA FUNCIONAL DOS MAXILARES"},
        "018":{"desc":"ODONTOLOGIA HOSPITALAR"},
    }},
    "115":{"desc":"SERVIÇO DE ATENÇÃO PSICOSSOCIAL","classificacoes":{
        "001":{"desc":"RESIDÊNCIA TERAPÊUTICA"},"002":{"desc":"ATENDIMENTO PSICOSSOCIAL"},
        "003":{"desc":"SERVIÇO HOSPITALAR SAÚDE MENTAL"},"004":{"desc":"SRT TIPO I"},
        "005":{"desc":"SRT TIPO II"},"006":{"desc":"UA ADULTO"},"007":{"desc":"UA INFANTO-JUVENIL"},
        "008":{"desc":"REGIME RESIDENCIAL"},"009":{"desc":"INTERNAÇÃO TRANSTORNOS E DEPENDÊNCIA"},
        "010":{"desc":"DESINSTITUCIONALIZAÇÃO"},
    }},
    "116":{"desc":"SERVIÇO DE ATENÇÃO CARDIOVASCULAR","classificacoes":{
        "001":{"desc":"ELETROFISIOLOGIA"},"002":{"desc":"CIRURGIA CARDIOVASCULAR ADULTO"},
        "003":{"desc":"CIRURGIA CARDIOVASCULAR PEDIÁTRICO"},"004":{"desc":"CIRURGIA VASCULAR"},
        "005":{"desc":"CARDIOLOGIA INTERVENCIONISTA (HEMODINÂMICA)"},"006":{"desc":"CARDIOLOGIA ENDOVASCULAR"},
        "007":{"desc":"CARDIOLOGIA CLÍNICA"},"008":{"desc":"ANGIOLOGIA"},
    }},
    "120":{"desc":"DIAGNÓSTICO POR ANATOMIA PATOLÓGICA/CITOPATOLOGIA","classificacoes":{
        "001":{"desc":"EXAMES ANATOMOPATOLÓGICOS"},"002":{"desc":"EXAMES CITOPATOLÓGICOS"},
        "003":{"desc":"LABORATÓRIO TIPO II"},
    }},
    "121":{"desc":"SERVIÇO DE DIAGNÓSTICO POR IMAGEM","classificacoes":{
        "001":{"desc":"RADIOLOGIA"},"002":{"desc":"ULTRA-SONOGRAFIA"},
        "003":{"desc":"TOMOGRAFIA COMPUTADORIZADA"},"004":{"desc":"RESSONÂNCIA MAGNÉTICA"},
        "006":{"desc":"RADIOLOGIA INTERVENCIONISTA"},"012":{"desc":"MAMOGRAFIA"},
    }},
    "122":{"desc":"DIAGNÓSTICO POR MÉTODOS GRÁFICOS/DINÂMICOS","classificacoes":{
        "001":{"desc":"TESTE ERGOMÉTRICO"},"002":{"desc":"TESTE DE HOLTER"},
        "003":{"desc":"EXAME ELETROCARDIOGRAFICO"},"004":{"desc":"EXAME ELETROENCEFALOGRAFICO"},
        "009":{"desc":"ELETRONEUROMIOGRAFIA"},"010":{"desc":"VIDEOELETROENCEFALOGRAFIA"},
        "011":{"desc":"POTENCIAIS EVOCADOS"},
    }},
    "125":{"desc":"SERVIÇO DE FARMÁCIA","classificacoes":{
        "001":{"desc":"COMPONENTE ESPECIALIZADO DA ASSISTÊNCIA FARMACÊUTICA"},
        "002":{"desc":"FARMÁCIA POPULAR"},"003":{"desc":"FARMÁCIA COM MANIPULAÇÃO HOMEOPÁTICA"},
        "004":{"desc":"MEDICAMENTOS ESTRATÉGICOS"},"005":{"desc":"MEDICAMENTOS BÁSICOS"},
        "006":{"desc":"FARMÁCIA HOSPITALAR"},"007":{"desc":"FARMÁCIA VIVA"},
    }},
    "126":{"desc":"SERVIÇO DE FISIOTERAPIA","classificacoes":{
        "001":{"desc":"ALTERAÇÕES OBSTÉTRICAS/NEONATAIS/UROGINECOLÓGICAS"},
        "002":{"desc":"ALTERAÇÕES ONCOLÓGICAS"},"003":{"desc":"OFTALMOLOGIA"},
        "004":{"desc":"CARDIOVASCULARES E PNEUMO-FUNCIONAIS"},
        "005":{"desc":"DISFUNÇÕES MÚSCULO ESQUELÉTICAS"},"006":{"desc":"QUEIMADOS"},
        "007":{"desc":"ALTERAÇÕES EM NEUROLOGIA"},"008":{"desc":"DIAGNÓSTICO CINÉTICO FUNCIONAL"},
    }},
    "130":{"desc":"ATENÇÃO À DOENÇA RENAL CRÔNICA","classificacoes":{
        "001":{"desc":"HEMODIÁLISE"},"003":{"desc":"ACESSOS PARA DIÁLISE"},
        "004":{"desc":"NEFROLOGIA EM GERAL"},"005":{"desc":"DIÁLISE PERITONEAL"},
        "006":{"desc":"PRÉ-DIALÍTICO"},
    }},
    "132":{"desc":"SERVIÇO DE ONCOLOGIA","classificacoes":{
        "001":{"desc":"ONCOLOGIA PEDIÁTRICA"},"002":{"desc":"HEMATOLOGIA"},
        "003":{"desc":"ONCOLOGIA CLÍNICA"},"004":{"desc":"RADIOTERAPIA"},
        "005":{"desc":"ONCOLOGIA CIRÚRGICA"},
    }},
    "134":{"desc":"PRÁTICAS INTEGRATIVAS E COMPLEMENTARES","classificacoes":{
        "001":{"desc":"ACUPUNTURA"},"002":{"desc":"FITOTERAPIA"},
        "003":{"desc":"OUTRAS TÉCNICAS EM MTC"},"004":{"desc":"PRÁTICAS CORPORAIS E MENTAIS"},
        "005":{"desc":"HOMEOPATIA"},"006":{"desc":"TERMALISMO/CRENOTERAPIA"},
        "007":{"desc":"ANTROPOSOFIA APLICADA À SAÚDE"},"008":{"desc":"PRÁTICAS EXPRESSIVAS"},
    }},
    "135":{"desc":"SERVIÇO DE REABILITAÇÃO","classificacoes":{
        "001":{"desc":"REABILITAÇÃO VISUAL"},"002":{"desc":"REABILITAÇÃO INTELECTUAL"},
        "003":{"desc":"REABILITAÇÃO FÍSICA"},"005":{"desc":"REABILITAÇÃO AUDITIVA"},
        "010":{"desc":"ATENÇÃO FONOAUDIOLÓGICA"},"011":{"desc":"ATENÇÃO FISIOTERAPÊUTICA"},
    }},
    "140":{"desc":"SERVIÇO DE URGÊNCIA E EMERGÊNCIA","classificacoes":{
        "004":{"desc":"SALA DE ESTABILIZAÇÃO"},"005":{"desc":"ATENDIMENTO AVC"},
        "006":{"desc":"PRONTO ATENDIMENTO CLÍNICO"},"007":{"desc":"PRONTO ATENDIMENTO PEDIÁTRICO"},
        "008":{"desc":"PRONTO ATENDIMENTO OBSTÉTRICO"},"009":{"desc":"PRONTO ATENDIMENTO PSIQUIÁTRICO"},
        "010":{"desc":"PRONTO ATENDIMENTO OFTALMOLÓGICO"},"011":{"desc":"PRONTO ATENDIMENTO ODONTOLÓGICO"},
        "012":{"desc":"PRONTO SOCORRO PEDIÁTRICO"},"013":{"desc":"PRONTO SOCORRO OBSTÉTRICO"},
        "014":{"desc":"PRONTO SOCORRO CARDIOVASCULAR"},"015":{"desc":"PRONTO SOCORRO NEUROLOGIA/NEUROCIRURGIA"},
        "016":{"desc":"PRONTO SOCORRO TRAUMATO-ORTOPÉDICO"},"019":{"desc":"PRONTO SOCORRO GERAL/CLÍNICO"},
    }},
    "145":{"desc":"DIAGNÓSTICO POR LABORATÓRIO CLÍNICO","classificacoes":{
        "001":{"desc":"EXAMES BIOQUÍMICOS"},"002":{"desc":"EXAMES HEMATOLÓGICOS E HEMOSTASIA"},
        "003":{"desc":"EXAMES SOROLÓGICOS E IMUNOLÓGICOS"},"004":{"desc":"EXAMES COPROLÓGICOS"},
        "005":{"desc":"EXAMES DE UROANÁLISE"},"006":{"desc":"EXAMES HORMONAIS"},
        "007":{"desc":"VIGILÂNCIA EPIDEMIOLÓGICA E AMBIENTAL"},"008":{"desc":"TOXICOLÓGICOS"},
        "009":{"desc":"EXAMES MICROBIOLÓGICOS"},"010":{"desc":"OUTROS LÍQUIDOS BIOLÓGICOS"},
        "011":{"desc":"EXAMES DE GENÉTICA"},"012":{"desc":"TRIAGEM NEONATAL"},
        "013":{"desc":"EXAMES IMUNOHEMATOLÓGICOS"},
    }},
    "148":{"desc":"HOSPITAL-DIA","classificacoes":{
        "001":{"desc":"SAÚDE MENTAL"},"002":{"desc":"AIDS"},"003":{"desc":"GERIÁTRICO"},
        "004":{"desc":"FIBROSE CÍSTICA"},"005":{"desc":"CIRÚRGICO/DIAGNÓSTICO"},
        "006":{"desc":"ACOMPANHAMENTO PÓS TRANSPLANTE DE MEDULA ÓSSEA"},
    }},
    "149":{"desc":"TRANSPLANTE","classificacoes":{
        "001":{"desc":"RIM"},"002":{"desc":"MEDULA ÓSSEA"},"003":{"desc":"CORAÇÃO"},
        "004":{"desc":"PULMÃO"},"005":{"desc":"CÓRNEA/ESCLERA"},"006":{"desc":"FÍGADO"},
        "007":{"desc":"PÂNCREAS"},"008":{"desc":"RETIRADA DE ÓRGÃOS"},"009":{"desc":"PELE"},
    }},
    "159":{"desc":"ATENÇÃO PRIMÁRIA","classificacoes":{
        "001":{"desc":"ATENÇÃO PRIMÁRIA"},"003":{"desc":"ACADEMIA DA SAÚDE"},
        "004":{"desc":"ESTRATÉGIA DE SAÚDE DA FAMÍLIA"},"005":{"desc":"SAÚDE BUCAL"},
        "006":{"desc":"ATENÇÃO MULTIPROFISSIONAL"},"007":{"desc":"POPULAÇÃO RIBEIRINHA"},
        "008":{"desc":"CONSULTÓRIO NA RUA"},"009":{"desc":"POPULAÇÃO PRISIONAL"},
        "010":{"desc":"ADOLESCENTES EM UNIDADE SOCIOEDUCATIVA"},
    }},
    "162":{"desc":"SERVIÇO DE TERAPIA INTENSIVA","classificacoes":{
        "001":{"desc":"ADULTO"},"002":{"desc":"NEONATAL"},"003":{"desc":"PEDIÁTRICO"},
        "004":{"desc":"QUEIMADOS"},"005":{"desc":"DOENÇA CORONARIANA (UCO)"},
    }},
    "163":{"desc":"CUIDADOS INTERMEDIÁRIOS","classificacoes":{
        "001":{"desc":"NEONATAL CONVENCIONAL"},"002":{"desc":"NEONATAL CANGURU"},
        "003":{"desc":"PEDIÁTRICO"},"004":{"desc":"ADULTO"},
    }},
}

# ─────────────────────────────────────────────────────────────
#  HELPERS PDF
# ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _encontrar_logo(nome):
    for ext in ('.png', '.jpg', '.jpeg'):
        p = os.path.join(BASE_DIR, nome + ext)
        if os.path.exists(p):
            return p
    return None

def _val(v):
    if v is None:
        return False
    s = str(v).strip()
    return s not in ('', '0', '0/0', '—', 'Não', 'Nao', 'nao', 'não')

def adicionar_cabecalho(story, styles):
    def make_logo(nome, w=80, h=60):
        p = _encontrar_logo(nome)
        if p:
            try:
                return Image(p, width=w, height=h)
            except:
                pass
        return Paragraph('', styles['Normal'])

    logo_esq    = make_logo('logo_prefeitura')
    logo_centro = make_logo('logo_jarvis', w=90, h=60)
    if not isinstance(logo_centro, Image):
        logo_centro = Paragraph(
            "<b><font size=14 color='#003057'>JARVIS CNES</font></b>",
            ParagraphStyle(name='lc', alignment=TA_CENTER)
        )
    logo_dir = make_logo('logo_cnes')

    t = Table([[logo_esq, logo_centro, logo_dir]], colWidths=[160, 200, 160])
    t.setStyle(TableStyle([
        ('ALIGN',  (0,0),(0,0), 'LEFT'),
        ('ALIGN',  (1,0),(1,0), 'CENTER'),
        ('ALIGN',  (2,0),(2,0), 'RIGHT'),
        ('VALIGN', (0,0),(-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0),(-1,-1), 10),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

# ─────────────────────────────────────────────────────────────
#  GERAÇÃO DO PDF
# ─────────────────────────────────────────────────────────────
def gerar_pdf_completo(dados, caminho_pdf, lista_anexos=None):
    doc = SimpleDocTemplate(
        caminho_pdf, pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=48, bottomMargin=30
    )
    story = []
    styles = getSampleStyleSheet()
    CW = [160, 360]

    T = ParagraphStyle('T', parent=styles['Heading1'],
                       alignment=TA_CENTER, textColor=colors.HexColor('#003057'),
                       fontSize=13, spaceAfter=8)
    H2 = ParagraphStyle('H2', parent=styles['Heading2'],
                        textColor=colors.HexColor('#003057'),
                        fontSize=10, spaceAfter=4, spaceBefore=10,
                        backColor=colors.HexColor('#e8f0f8'), borderPad=4)
    N  = ParagraphStyle('N',  parent=styles['Normal'], fontSize=8.5, leading=12)
    Ns = ParagraphStyle('Ns', parent=styles['Normal'], fontSize=8,   leading=11,
                        textColor=colors.HexColor('#444444'))

    GRID_STYLE = TableStyle([
        ("GRID",         (0,0),(-1,-1), 0.4, colors.HexColor('#c8d4e0')),
        ("BACKGROUND",   (0,0),(0,-1),  colors.HexColor('#f0f4f8')),
        ("FONTSIZE",     (0,0),(-1,-1), 8.5),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",  (0,0),(-1,-1), 6),
        ("RIGHTPADDING", (0,0),(-1,-1), 6),
        ("FONTNAME",     (0,0),(0,-1),  'Helvetica-Bold'),
        ("VALIGN",       (0,0),(-1,-1), 'MIDDLE'),
    ])

    adicionar_cabecalho(story, styles)
    story.append(Paragraph("CNES — Extrato do Cadastro", T))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", Ns))
    story.append(Spacer(1, 12))

    def tab(titulo, pares):
        rows = [[k, str(v)] for k, v in pares if _val(v)]
        if not rows:
            return
        story.append(Paragraph(titulo, H2))
        story.append(Spacer(1, 3))
        t = Table(rows, colWidths=CW)
        t.setStyle(GRID_STYLE)
        story.append(t)
        story.append(Spacer(1, 8))

    def bloco_texto(titulo, txt):
        if not _val(txt):
            return
        story.append(Paragraph(titulo, H2))
        story.append(Spacer(1, 3))
        story.append(Paragraph(str(txt), N))
        story.append(Spacer(1, 8))

    # 1. Identificação
    tab("1. Identificação do Estabelecimento", [
        ("Operação",               dados.get("f1_operacao")),
        ("Código CNES",            dados.get("f1_cnes")),
        ("Tipo de Estabelecimento",dados.get("f1_tipo_estab")),
        ("CNPJ / CPF",             dados.get("f1_cnpj")),
        ("Razão Social",           dados.get("f1_nome_empresarial")),
        ("Nome Fantasia",          dados.get("f1_fantasia")),
        ("CEP",                    dados.get("f1_cep")),
        ("Logradouro",             f"{dados.get('f1_endereco','')} {dados.get('f1_numero','')}".strip()),
        ("Complemento",            dados.get("f1_complemento")),
        ("Bairro",                 dados.get("f1_bairro")),
        ("Telefone",               dados.get("f1_telefone")),
        ("E-mail Institucional",   dados.get("f1_email")),
        ("Diretor / Administrador",dados.get("f1_administrador")),
        ("Registro no Conselho",   dados.get("f1_conselho_rt")),
        ("Nº do Alvará",           dados.get("f1_alvara")),
        ("Data de Expedição",      dados.get("f1_alvara_data")),
        ("Órgão Expedidor",        dados.get("f1_alvara_orgao")),
    ])

    # 2. Caracterização
    atend = ", ".join(dados.get("atendimento_prestado", []))
    tab("2. Caracterização", [
        ("Esfera Administrativa",  dados.get("f2_esfera")),
        ("Ensino / Pesquisa",      dados.get("f2_ensino")),
        ("Nível de Hierarquia",    dados.get("f2_hierarquia")),
        ("Fluxo de Clientela",     dados.get("f2_fluxo_clientela")),
        ("Convênio",               dados.get("f2_convenio")),
        ("Turno de Atendimento",   dados.get("f2_turno")),
        ("Dias de Funcionamento",  dados.get("f2_dias_func")),
        ("Horários",               dados.get("f2_horas_func")),
        ("Atendimento Prestado",   atend if atend else None),
    ])

    # 3. Instalações Físicas
    salas_pares = [
        ("Consultórios Médicos (UE)",           dados.get("f6_ue_med")),
        ("Odontologia — Consultórios (UE)",     dados.get("f6_ue_odonto")),
        ("Triagem Pediátrico",                  dados.get("f6_triagem_ped")),
        ("Triagem Feminino",                    dados.get("f6_triagem_fem")),
        ("Triagem Masculino",                   dados.get("f6_triagem_masc")),
        ("Triagem Indiferenciado",              dados.get("f6_triagem_indf")),
        ("Sala de Curativo (UE)",               dados.get("f6_ue_curativo")),
        ("Sala de Gesso (UE)",                  dados.get("f6_ue_gesso")),
        ("Sala de Higienização",                dados.get("f6_higienizacao")),
        ("Sala de Pequena Cirurgia (UE)",       dados.get("f6_ue_peq_cir")),
        ("Repouso Pediátrico (salas/leitos)",
            f"{dados.get('f6_repouso_ped_salas','0')}/{dados.get('f6_repouso_ped_leitos','0')}"),
        ("Repouso Feminino (salas/leitos)",
            f"{dados.get('f6_repouso_fem_salas','0')}/{dados.get('f6_repouso_fem_leitos','0')}"),
        ("Repouso Masculino (salas/leitos)",
            f"{dados.get('f6_repouso_masc_salas','0')}/{dados.get('f6_repouso_masc_leitos','0')}"),
        ("Repouso Indiferenciado (salas/leitos)",
            f"{dados.get('f6_repouso_indf_salas','0')}/{dados.get('f6_repouso_indf_leitos','0')}"),
        ("Clínicas Básicas (Amb)",              dados.get("f6_amb_basicas")),
        ("Clínicas Especializadas (Amb)",       dados.get("f6_amb_especializadas")),
        ("Consultórios Indiferenciado (Amb)",   dados.get("f6_amb_indf")),
        ("Outros Consultórios Não Médicos",     dados.get("f6_outros_nmed")),
        ("Odontologia — Consultórios (Amb)",    dados.get("f6_odonto_amb")),
        ("Pequena Cirurgia (Amb)",              dados.get("f6_peq_cirurgia_amb")),
        ("Sala de Enfermagem",                  dados.get("f6_enfermagem")),
        ("Sala de Imunização",                  dados.get("f6_imunizacao")),
        ("Sala de Nebulização",                 dados.get("f6_nebulizacao")),
        ("Sala de Gesso (Amb)",                 dados.get("f6_gesso_amb")),
        ("Sala de Curativo (Amb)",              dados.get("f6_curativo_amb")),
        ("Cirurgia Ambulatorial (Amb)",         dados.get("f6_cirurgia_amb")),
        ("Sala de Cirurgia (CC)",               dados.get("f6_cirurgia")),
        ("Recuperação — Salas",                 dados.get("f6_recuperacao")),
        ("Recuperação — Leitos",                dados.get("f6_recuperacao_leitos")),
        ("Cirurgia Ambulatorial (CC)",          dados.get("f6_cirurgia_amb_cc")),
        ("Pré-parto — Salas",                   dados.get("f6_preparto_qtd")),
        ("Pré-parto — Leitos",                  dados.get("f6_preparto_leitos")),
        ("Sala de Parto Normal",                dados.get("f6_parto_normal")),
        ("Sala de Curetagem",                   dados.get("f6_curetagem")),
        ("Sala de Cirurgia (CO)",               dados.get("f6_cirurgia_co")),
        ("Leitos RN Normal",                    dados.get("f6_leitos_rn_normal")),
        ("Leitos RN Patológico",                dados.get("f6_leitos_rn_patologico")),
        ("Leitos Alojamento Conjunto",          dados.get("f6_leitos_alojamento")),
    ]
    tab("3. Instalações Físicas — Ficha 6", salas_pares)

    # 4. Comissões
    comissoes_ativas = [
        f"{cod} — {nome}"
        for cod, nome in COMISSOES_F4
        if _val(dados.get(f"f4_{cod}")) and dados.get(f"f4_{cod}") == "Sim"
    ]
    if comissoes_ativas:
        story.append(Paragraph("4. Comissões — Ficha 4", H2))
        story.append(Spacer(1, 3))
        rows = [["Comissão", "Situação"]]
        for c in comissoes_ativas:
            rows.append([c, "Ativa"])
        t = Table(rows, colWidths=CW)
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0), colors.HexColor('#003057')),
            ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
            ("FONTNAME",     (0,0),(-1,0), 'Helvetica-Bold'),
            ("FONTSIZE",     (0,0),(-1,-1), 8.5),
            ("GRID",         (0,0),(-1,-1), 0.4, colors.HexColor('#c8d4e0')),
            ("TOPPADDING",   (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
            ("BACKGROUND",   (0,1),(0,-1),  colors.HexColor('#f0f4f8')),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    tab("PNASS / Acreditação", [
        ("PNASS — Avaliado",       dados.get("f4_pnass_avaliado")),
        ("PNASS — Data",           dados.get("f4_pnass_data")),
        ("Acreditação Hospitalar", dados.get("f4_acreditado")),
        ("Data de Acreditação",    dados.get("f4_acreditacao_data")),
        ("Prog. Filantrópico",     dados.get("f4_adesao_filantropico")),
        ("Internet",               dados.get("f4_internet")),
        ("Tipo de Conexão",        dados.get("f4_tipo_conexao")),
        ("Telefonia Fixa",         dados.get("f4_telefonia_fixa")),
        ("Telefonia Móvel",        dados.get("f4_telefonia_movel")),
    ])

    # 5. Serviços de Apoio
    apoio_rows = []
    for i, nome in enumerate(SERVICOS_APOIO, 1):
        v = dados.get("apoio", {}).get(str(i), '')
        if _val(v) and v not in ('Nao', 'Não'):
            apoio_rows.append([nome, v])
    if apoio_rows:
        story.append(Paragraph("5. Serviços de Apoio — Ficha 7", H2))
        story.append(Spacer(1, 3))
        t = Table(apoio_rows, colWidths=CW)
        t.setStyle(GRID_STYLE)
        story.append(t)
        story.append(Spacer(1, 8))

    # 6. Resíduos
    res = ", ".join(dados.get("residuos", []))
    if _val(res):
        tab("6. Resíduos / Rejeitos", [
            ("Tipos",         res),
            ("Especificações",dados.get("f17_outros_res")),
        ])

    # 7. Equipamentos
    def equip_section(titulo, lista, lista_dados):
        rows = []
        for i, nome in enumerate(lista):
            if i < len(lista_dados) and lista_dados[i].get("possui"):
                qtd = lista_dados[i].get("qtd", 0)
                if int(qtd) > 0:
                    rows.append([nome, f"{qtd} unidade(s)"])
        if rows:
            story.append(Paragraph(titulo, H2))
            story.append(Spacer(1, 3))
            t = Table(rows, colWidths=CW)
            t.setStyle(GRID_STYLE)
            story.append(t)
            story.append(Spacer(1, 8))

    equip_section("7. Diagnóstico por Imagem", EQUIP_DIAG_IMAGEM, dados.get("eq_diag_imagem", []))
    equip_section("Infraestrutura",             EQUIP_INFRA,       dados.get("eq_infra", []))
    equip_section("Métodos Ópticos",            EQUIP_OPTICOS,     dados.get("eq_opticos", []))
    equip_section("Odontologia",                EQUIP_ODONTO,      dados.get("eq_odonto", []))
    equip_section("Outros Equipamentos",        EQUIP_OUTROS,      dados.get("eq_outros", []))
    equip_section("Audiologia",                 EQUIP_AUDIO,       dados.get("eq_audio", []))

    # 8. Leitos
    grupos = [
        ("8.1 Leitos Cirúrgicos",     LEITOS_CIRURGICOS,     "leitos_cirurgicos"),
        ("8.2 Leitos Obstétricos",    LEITOS_OBSTETRICOS,    "leitos_obstetricos"),
        ("8.3 Leitos Pediátricos",    LEITOS_PEDIATRICOS,    "leitos_pediatricos"),
        ("8.4 Leitos Clínicos",       LEITOS_CLINICOS,       "leitos_clinicos"),
        ("8.5 Outras Especialidades", LEITOS_OUTRAS,         "leitos_outras"),
        ("8.6 Hospital Dia",          LEITOS_HOSPITAL_DIA,   "leitos_hospital_dia"),
        ("8.7 Leitos Complementares", LEITOS_COMPLEMENTARES, "leitos_complementares"),
    ]
    for titulo, lista, chave in grupos:
        d = dados.get(chave, {})
        rows = []
        for e in lista:
            ex  = int(d.get(e, {}).get("existente", 0) or 0)
            sus = int(d.get(e, {}).get("sus", 0) or 0)
            if ex > 0 or sus > 0:
                rows.append([e, f"{ex} total / {sus} SUS"])
        if rows:
            story.append(Paragraph(titulo, H2))
            story.append(Spacer(1, 3))
            t = Table(rows, colWidths=CW)
            t.setStyle(GRID_STYLE)
            story.append(t)
            story.append(Spacer(1, 8))

    # 9. Especializações
    esps = dados.get("especializacoes", [])
    esp_validos = [e for e in esps if _val(e.get("servico")) or _val(e.get("classificacao"))]
    if esp_validos:
        story.append(Paragraph("9. Especializações — Ficha 8", H2))
        story.append(Spacer(1, 3))
        for esp in esp_validos:
            cbos_desc = "; ".join(
                f"{c} — {cbo_dict.get(c, c)}"
                for c in esp.get("cbos_selecionados", []) if c
            )
            txt = f"<b>{esp.get('servico','')}</b>"
            if esp.get('classificacao'):
                txt += f" · {esp['classificacao']}"
            if cbos_desc:
                txt += f"<br/><i>CBOs:</i> {cbos_desc}"
            story.append(Paragraph(txt, N))
            story.append(Spacer(1, 5))
        story.append(Spacer(1, 6))

    # 10. Profissionais
    profs = dados.get("profissionais", [])
    profs_validos = [p for p in profs if _val(p.get("nome")) or _val(p.get("cpf"))]
    if profs_validos:
        story.append(Paragraph("10. Profissionais — Fichas 20/21", H2))
        story.append(Spacer(1, 3))
        for i, p in enumerate(profs_validos, 1):
            cbo_desc = cbo_dict.get(p.get('profissao', ''), p.get('profissao', ''))
            pares = [
                ("Nome",           p.get('nome')),
                ("CPF",            p.get('cpf')),
                ("Nome da Mãe",    p.get('mae')),
                ("Endereço",       f"{p.get('endereco','')} {p.get('numero','')}".strip()),
                ("Telefone",       p.get('telefone')),
                ("E-mail",         p.get('email')),
                ("Conselho/Reg.",  p.get('conselho')),
                ("CBO",            f"{p.get('profissao','')} — {cbo_desc}" if p.get('profissao') else None),
                ("C.H. Semanal",   p.get('ch')),
                ("Vínculo Estab.", p.get('estabelecimento')),
                ("Vínculo Empreg.",p.get('empregador')),
                ("CNPJ da PJ",     p.get('cnpj_pj')),
                ("Detalhamento",   p.get('detalhamento')),
            ]
            rows = [[k, str(v)] for k, v in pares if _val(v)]
            if rows:
                story.append(Paragraph(f"Profissional {i}", ParagraphStyle(
                    'ph', parent=styles['Normal'], fontSize=8.5, fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#003057'), spaceBefore=6
                )))
                t = Table(rows, colWidths=CW)
                t.setStyle(GRID_STYLE)
                story.append(t)
                story.append(Spacer(1, 6))

    # 11. Declaração PJ/PF
    decl_razao = dados.get("d_razao", "")
    if _val(decl_razao):
        story.append(Spacer(1, 6))
        story.append(Paragraph("11. Declaração — Pessoa Jurídica e/ou Física", H2))
        story.append(Spacer(1, 6))
        DECL_STYLE = TableStyle([
            ("GRID",         (0,0),(-1,-1), 0.4, colors.HexColor('#c8d4e0')),
            ("BACKGROUND",   (0,0),(0,-1),  colors.HexColor('#f0f4f8')),
            ("FONTSIZE",     (0,0),(-1,-1), 8.5),
            ("TOPPADDING",   (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
            ("RIGHTPADDING", (0,0),(-1,-1), 6),
            ("FONTNAME",     (0,0),(0,-1),  'Helvetica-Bold'),
            ("VALIGN",       (0,0),(-1,-1), 'MIDDLE'),
        ])
        decl_pares = [
            ("Razão Social / Nome",      dados.get("d_razao")),
            ("CNPJ",                     dados.get("d_cnpj")),
            ("Nome Fantasia",            dados.get("d_fantasia")),
            ("Logradouro",               dados.get("d_rua")),
            ("Bairro",                   dados.get("d_bairro")),
            ("CEP",                      dados.get("d_cep")),
            ("RT / Administrador",       dados.get("d_rt_nome")),
            ("Profissão",                dados.get("d_profissao")),
            ("RG",                       dados.get("d_rg")),
            ("Órgão Expedidor",          dados.get("d_rg_orgao")),
            ("CPF do RT",                dados.get("d_cpf")),
            ("Registro no Conselho",     dados.get("d_conselho")),
            ("Tipo de Estabelecimento",  dados.get("d_tipo_estab")),
            ("Atividade Principal",      dados.get("d_atv_principal")),
            ("Atividades Secundárias",   dados.get("d_atv_sec")),
            ("Horário de Funcionamento", dados.get("d_horarios")),
            ("Data",                     f"{dados.get('d_dia','')} de {dados.get('d_mes','')} de {dados.get('d_ano','')}"),
        ]
        rows_decl = [[k, str(v)] for k, v in decl_pares if _val(v)]
        if rows_decl:
            t = Table(rows_decl, colWidths=CW)
            t.setStyle(DECL_STYLE)
            story.append(t)
            story.append(Spacer(1, 16))
            assin_data = [
                ["_" * 40, "_" * 40],
                ["Titular / Administrador / Responsável Técnico", "Carimbo do Estabelecimento"],
                ["(pode ser assinatura GOV.br)", "CNPJ / CRM / CRO / COREN"],
            ]
            t_assin = Table(assin_data, colWidths=[260, 260])
            t_assin.setStyle(TableStyle([
                ("ALIGN",        (0,0),(-1,-1), 'CENTER'),
                ("FONTSIZE",     (0,0),(-1,-1), 8),
                ("TOPPADDING",   (0,0),(-1,-1), 4),
                ("BOTTOMPADDING",(0,0),(-1,-1), 2),
                ("FONTNAME",     (0,1),(-1,1),  'Helvetica-Bold'),
                ("TEXTCOLOR",    (0,1),(-1,1),  colors.HexColor('#003057')),
            ]))
            story.append(t_assin)
        story.append(Spacer(1, 10))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Acompanhe o extrato CNES: <b>https://cnes.datasus.gov.br/</b> · "
        "Dúvidas: <b>gecav.semusa@portovelho.ro.gov.br</b>",
        Ns
    ))

    if lista_anexos:
        story.append(Paragraph("Documentos Anexados", H2))
        for a in lista_anexos:
            story.append(Paragraph(f"• {os.path.basename(a)}", N))

    doc.build(story)

# ─────────────────────────────────────────────────────────────
#  ENVIO DE E-MAIL
# ─────────────────────────────────────────────────────────────
def enviar_email_com_pdf(dados, pdf_path, anexos=None, bck_path=None):
    try:
        nome_estab  = dados.get('f1_nome_empresarial', 'Estabelecimento')
        cnes_num    = dados.get('f1_cnes', '')
        solicitante = dados.get('f1_administrador', '')
        email_inst  = dados.get('f1_email', '')
        rt_conselho = dados.get('f1_conselho_rt', '')
        data_hora   = datetime.now().strftime('%d/%m/%Y às %H:%M:%S')

        msg = MIMEMultipart()
        msg["Subject"] = f"[CNES] Cadastro — {nome_estab} · CNES {cnes_num}"
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = DESTINATARIO_FIXO

        corpo = f"""PREFEITURA MUNICIPAL DE PORTO VELHO
Secretaria Municipal de Saúde — SEMUSA
Sistema JARVIS CNES · Cadastro Nacional de Estabelecimentos de Saúde
{'─'*60}

SOLICITANTE / RESPONSÁVEL TÉCNICO (RT)

  Nome:              {solicitante or '(não informado)'}
  Registro Conselho: {rt_conselho or '(não informado)'}
  E-mail:            {email_inst or '(não informado)'}

{'─'*60}

ESTABELECIMENTO

  Razão Social: {nome_estab}
  Código CNES:  {cnes_num or '(não informado)'}
  CNPJ/CPF:     {dados.get('f1_cnpj', '(não informado)')}
  Endereço:     {dados.get('f1_endereco','')} {dados.get('f1_numero','')} — {dados.get('f1_bairro','')}
  Telefone:     {dados.get('f1_telefone','(não informado)')}

{'─'*60}

Documento gerado automaticamente pelo sistema JARVIS CNES Web.
Data/Hora: {data_hora}

O extrato completo em PDF está anexo a esta mensagem.
Acompanhe o cadastro em: https://cnes.datasus.gov.br/

ANEXO INTERNO (uso exclusivo GECAV): arquivo no padrão de transmissão do
SCNES (CNES0RO110020....bck) para importação no SCNES.

{'─'*60}
SEMUSA — Secretaria Municipal de Saúde de Porto Velho
Av. Campos Sales, 2283, Centro — Porto Velho / RO
gecav.semusa@portovelho.ro.gov.br
"""
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

        def _anexar(path, nome, maintype='application', subtype='octet-stream'):
            with open(path, 'rb') as f:
                part = MIMEBase(maintype, subtype)
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{nome}"')
            msg.attach(part)

        bck_tamanho = None
        anexos_nome = [(a, os.path.basename(a)) for a in (anexos or [])]
        if bck_path and os.path.exists(bck_path):
            bck_tamanho = os.path.getsize(bck_path)
            _anexar(bck_path, _nome_bck())
        _anexar(pdf_path, 'extrato_cnes.pdf')
        for path, name in anexos_nome:
            _anexar(path, name)

        if not SENHA_APP or not EMAIL_REMETENTE:
            return False, ("Credenciais de e-mail não configuradas. Defina JARVIS_EMAIL e "
                           "JARVIS_SENHA_APP (senha de app do Gmail) nas variáveis de "
                           "ambiente do servidor (Vercel: Settings → Environment Variables) "
                           "e faça o redeploy.")
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(EMAIL_REMETENTE, SENHA_APP)
            falhas = s.send_message(msg)
        if falhas:
            return False, f"E-mail enviado, mas o Gmail recusou destinatário(s): {falhas}"
        if bck_tamanho:
            return True, f"E-mail enviado com sucesso (com .BCK {bck_tamanho//1024} KB para a GECAV)"
        return True, "E-mail enviado com sucesso"
    except Exception as e:
        msg = str(e)
        if "535" in msg or "BadCredentials" in msg:
            msg += (" | Confira JARVIS_EMAIL e JARVIS_SENHA_APP (senha de app do Gmail) "
                    "nas variáveis de ambiente do servidor — sem elas o Gmail recusa (535).")
        return False, msg

# ─────────────────────────────────────────────────────────────
#  FLASK APP
# ─────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════
#  [JARVIS + BCK] — GERAÇÃO DE ARQUIVO .BCK (SCNES/CNES DATASUS)
#  Injetado sobre o JARVIS original — layout do app não foi alterado.
#  Formato decodificado de um .BCK real exportado pelo SCNES 4.8.40
#  (68 tabelas LFCES/TFCES/CFCES + TXT + QRP opcional; zlib nível 1
#  reproduz byte a byte o que o SCNES gera — comprovado em round-trip).
# ═══════════════════════════════════════════════════════════════
import zlib, struct, time as _time

# ── Configuração do município (ajuste se necessário) ──
UF             = "RO"
COD_MUN_GESTOR = "110020"
GESTOR         = "SEMUSA"
VERSAO         = "4.8.40"
USUARIO        = "SEMUSA"
CMPT           = datetime.now().strftime("%Y%m")

CHUNK  = 16384
MARKER = b"EC2\x00"
TRAILER = b"\x00" * 8

def comprimir(dados: bytes, nivel: int = 1) -> bytes:
    return zlib.compress(dados, nivel)

def escrever_bck(descricao: str, entradas: list, nivel: int = 1) -> bytes:
    """entradas: [{path, ts, dados}] — 'dados' é o conteúdo descomprimido."""
    out = bytearray()
    desc = descricao.encode("latin-1", "replace")
    out += struct.pack("<I", len(desc)) + desc
    out += struct.pack("<I", sum(len(e["dados"]) for e in entradas))
    for i, e in enumerate(entradas):
        path = e["path"].encode("latin-1", "replace")
        out += struct.pack("<I", len(entradas) if i == 0 else 0)
        out += struct.pack("<I", len(path)) + path
        out += struct.pack("<I", e.get("ts", 0)) + MARKER
        dados = e["dados"]
        for off in range(0, len(dados), CHUNK):
            comp = comprimir(dados[off:off + CHUNK], nivel)
            out += struct.pack("<I", len(comp)) + comp
    out += TRAILER
    return bytes(out)

def ler_bck(dados: bytes):
    """Retorna (descricao, total_uncomp, entradas) — útil p/ conferência."""
    n = len(dados)
    desc_len = struct.unpack("<I", dados[0:4])[0]
    desc = dados[4:4 + desc_len].decode("latin-1")
    total = struct.unpack("<I", dados[4 + desc_len:8 + desc_len])[0]
    pos = 8 + desc_len
    entradas = []
    while pos < n - 8:
        lead = struct.unpack("<I", dados[pos:pos + 4])[0]
        plen = struct.unpack("<I", dados[pos + 4:pos + 8])[0]
        path = dados[pos + 8:pos + 8 + plen].decode("latin-1")
        p2 = pos + 8 + plen
        ts = struct.unpack("<I", dados[p2:p2 + 4])[0]
        assert dados[p2 + 4:p2 + 8] == MARKER
        pos = p2 + 8
        blob = b""
        while pos < n - 4:
            size = struct.unpack("<I", dados[pos:pos + 4])[0]
            if size <= 0 or pos + 4 + size > n:
                break
            blob += zlib.decompress(dados[pos + 4:pos + 4 + size])
            pos += 4 + size
        entradas.append({"lead": lead, "path": path, "ts": ts, "dados": blob})
    return desc, total, entradas

# ── Schemas reais das 68 tabelas (extraídos do .BCK do SCNES) ──
# LFCES004 tem 2 schemas: [0] identificação, [1] vínculo profissional
SCHEMAS = {
    "CFCES000": [
        [
            ('VERSAO', 'string', '', '', '10', '<FIELD attrname="VERSAO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;VERSAO&quot;" Roundtrip="True"/></FIELD>'),
            ('VERSAO_ANT', 'string', '', '', '10', '<FIELD attrname="VERSAO_ANT" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;VERSAO_ANT&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_VERSAO', 'string', '', '', '60', '<FIELD attrname="DT_VERSAO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;DT_VERSAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ULTIMA_ATU_SIST', 'string', '', '', '60', '<FIELD attrname="DT_ULTIMA_ATU_SIST" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;DT_ULTIMA_ATU_SIST&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_LEU_MSG_VERSAO', 'string', '', 'FixedChar', '1', '<FIELD attrname="FL_LEU_MSG_VERSAO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;FL_LEU_MSG_VERSAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ULTIMO_INFORME', 'string', '', '', '60', '<FIELD attrname="DT_ULTIMO_INFORME" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;DT_ULTIMO_INFORME&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_EXIGIR_CONSISTENCIA', 'string', '', 'FixedChar', '1', '<FIELD attrname="FL_EXIGIR_CONSISTENCIA" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;FL_EXIGIR_CONSISTENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_SCNES_SIMPLIFICADO', 'string', '', 'FixedChar', '1', '<FIELD attrname="FL_SCNES_SIMPLIFICADO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;CFCES000&quot;.&quot;FL_SCNES_SIMPLIFICADO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES000": [
        [
            ('NU_MAC', 'string', 'true', '', '20', '<FIELD attrname="NU_MAC" fieldtype="string" required="true" WIDTH="20"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NU_MAC&quot;" Roundtrip="True"/></FIELD>'),
            ('SIGLA_EST', 'string', '', '', '2', '<FIELD attrname="SIGLA_EST" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;SIGLA_EST&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', '', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('REGIAO', 'string', '', '', '4', '<FIELD attrname="REGIAO" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;REGIAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DISTRITO', 'string', '', '', '4', '<FIELD attrname="DISTRITO" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;DISTRITO&quot;" Roundtrip="True"/></FIELD>'),
            ('CNPJSIASUS', 'string', '', '', '14', '<FIELD attrname="CNPJSIASUS" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;CNPJSIASUS&quot;" Roundtrip="True"/></FIELD>'),
            ('NOMEGESTOR', 'string', '', '', '60', '<FIELD attrname="NOMEGESTOR" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NOMEGESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', '', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENT', 'string', '', '', '60', '<FIELD attrname="COMPLEMENT" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;COMPLEMENT&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '10', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRO', 'string', '', '', '60', '<FIELD attrname="BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('CEP', 'string', '', '', '8', '<FIELD attrname="CEP" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('FAX', 'string', '', '', '40', '<FIELD attrname="FAX" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('EMAIL', 'string', '', '', '60', '<FIELD attrname="EMAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;EMAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('INDGESTOR', 'string', '', 'FixedChar', '1', '<FIELD attrname="INDGESTOR" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;INDGESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('INDCADASTR', 'string', '', 'FixedChar', '1', '<FIELD attrname="INDCADASTR" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;INDCADASTR&quot;" Roundtrip="True"/></FIELD>'),
            ('INDEXPORTA', 'string', '', 'FixedChar', '1', '<FIELD attrname="INDEXPORTA" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;INDEXPORTA&quot;" Roundtrip="True"/></FIELD>'),
            ('EMAIL_GEST', 'string', '', '', '60', '<FIELD attrname="EMAIL_GEST" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;EMAIL_GEST&quot;" Roundtrip="True"/></FIELD>'),
            ('PREFIXOMAQ', 'string', '', '', '60', '<FIELD attrname="PREFIXOMAQ" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;PREFIXOMAQ&quot;" Roundtrip="True"/></FIELD>'),
            ('N_MAQUINA', 'string', '', '', '3', '<FIELD attrname="N_MAQUINA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;N_MAQUINA&quot;" Roundtrip="True"/></FIELD>'),
            ('INDTIPOCAD', 'string', '', 'FixedChar', '1', '<FIELD attrname="INDTIPOCAD" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;INDTIPOCAD&quot;" Roundtrip="True"/></FIELD>'),
            ('RESPONSAVEL', 'string', '', '', '60', '<FIELD attrname="RESPONSAVEL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;RESPONSAVEL&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_COMPUTADOR', 'string', '', '', '60', '<FIELD attrname="NO_COMPUTADOR" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NO_COMPUTADOR&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_SIST_OPER', 'string', '', '', '60', '<FIELD attrname="NO_SIST_OPER" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NO_SIST_OPER&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_VERSAO', 'string', '', '', '10', '<FIELD attrname="NU_VERSAO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NU_VERSAO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_SERV_PACK', 'string', '', '', '10', '<FIELD attrname="NU_SERV_PACK" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NU_SERV_PACK&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_CPU', 'string', '', '', '60', '<FIELD attrname="TP_CPU" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;TP_CPU&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_CLOCK', 'string', '', '', '10', '<FIELD attrname="TP_CLOCK" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;TP_CLOCK&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_MEMORIA', 'string', '', '', '15', '<FIELD attrname="NU_MEMORIA" fieldtype="string" WIDTH="15"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NU_MEMORIA&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_HD', 'string', '', '', '20', '<FIELD attrname="NU_HD" fieldtype="string" WIDTH="20"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NU_HD&quot;" Roundtrip="True"/></FIELD>'),
            ('IN_CD', 'string', '', '', '3', '<FIELD attrname="IN_CD" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;IN_CD&quot;" Roundtrip="True"/></FIELD>'),
            ('IN_IMPRESSORA', 'string', '', '', '3', '<FIELD attrname="IN_IMPRESSORA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;IN_IMPRESSORA&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_REDE', 'string', '', '', '10', '<FIELD attrname="TP_REDE" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;TP_REDE&quot;" Roundtrip="True"/></FIELD>'),
            ('IN_INTERNET', 'string', '', '', '13', '<FIELD attrname="IN_INTERNET" fieldtype="string" WIDTH="13"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;IN_INTERNET&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_USU_COMP', 'string', '', '', '60', '<FIELD attrname="NO_USU_COMP" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NO_USU_COMP&quot;" Roundtrip="True"/></FIELD>'),
            ('BANCO', 'string', '', '', '60', '<FIELD attrname="BANCO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;BANCO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_ARQ_ATUA_VIAWEB', 'i4', '', '', '', '<FIELD attrname="NU_ARQ_ATUA_VIAWEB" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;NU_ARQ_ATUA_VIAWEB&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES000&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES002": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_LEITO', 'string', 'true', '', '2', '<FIELD attrname="COD_LEITO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;COD_LEITO&quot;" Roundtrip="True"/></FIELD>'),
            ('CODTPLEITO', 'string', 'true', '', '2', '<FIELD attrname="CODTPLEITO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;CODTPLEITO&quot;" Roundtrip="True"/></FIELD>'),
            ('D_ALTACOMP', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_ALTACOMP" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;D_ALTACOMP&quot;" Roundtrip="True"/></FIELD>'),
            ('QTDE_EXIST', 'i4', '', '', '', '<FIELD attrname="QTDE_EXIST" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;QTDE_EXIST&quot;" Roundtrip="True"/></FIELD>'),
            ('QTDE_CONTR', 'i4', '', '', '', '<FIELD attrname="QTDE_CONTR" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;QTDE_CONTR&quot;" Roundtrip="True"/></FIELD>'),
            ('QTDE_SUS', 'i4', '', '', '', '<FIELD attrname="QTDE_SUS" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;QTDE_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES002&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES004": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES', 'string', '', '', '7', '<FIELD attrname="CNES" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CNES&quot;" Roundtrip="True"/></FIELD>'),
            ('CNPJ_MANT', 'string', '', '', '14', '<FIELD attrname="CNPJ_MANT" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CNPJ_MANT&quot;" Roundtrip="True"/></FIELD>'),
            ('PFPJ_IND', 'string', '', 'FixedChar', '1', '<FIELD attrname="PFPJ_IND" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;PFPJ_IND&quot;" Roundtrip="True"/></FIELD>'),
            ('NIVEL_DEP', 'string', '', 'FixedChar', '1', '<FIELD attrname="NIVEL_DEP" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NIVEL_DEP&quot;" Roundtrip="True"/></FIELD>'),
            ('R_SOCIAL', 'string', 'true', '', '60', '<FIELD attrname="R_SOCIAL" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;R_SOCIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_FANTA', 'string', 'true', '', '60', '<FIELD attrname="NOME_FANTA" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NOME_FANTA&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', 'true', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '10', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENT', 'string', '', '', '60', '<FIELD attrname="COMPLEMENT" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;COMPLEMENT&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRO', 'string', 'true', '', '60', '<FIELD attrname="BAIRRO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CEP', 'string', 'true', '', '8', '<FIELD attrname="COD_CEP" fieldtype="string" required="true" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;COD_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('REG_SAUDE', 'string', '', '', '4', '<FIELD attrname="REG_SAUDE" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;REG_SAUDE&quot;" Roundtrip="True"/></FIELD>'),
            ('MICRO_REG', 'string', '', '', '6', '<FIELD attrname="MICRO_REG" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;MICRO_REG&quot;" Roundtrip="True"/></FIELD>'),
            ('DIST_SANIT', 'string', '', '', '4', '<FIELD attrname="DIST_SANIT" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DIST_SANIT&quot;" Roundtrip="True"/></FIELD>'),
            ('DIST_ADMIN', 'string', '', '', '4', '<FIELD attrname="DIST_ADMIN" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DIST_ADMIN&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('FAX', 'string', '', '', '60', '<FIELD attrname="FAX" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('E_MAIL', 'string', '', '', '60', '<FIELD attrname="E_MAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;E_MAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('CPF', 'string', '', '', '11', '<FIELD attrname="CPF" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CPF&quot;" Roundtrip="True"/></FIELD>'),
            ('CNPJ', 'string', '', '', '14', '<FIELD attrname="CNPJ" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CNPJ&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_ATIV', 'string', '', '', '2', '<FIELD attrname="COD_ATIV" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;COD_ATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CLIENT', 'string', '', '', '2', '<FIELD attrname="COD_CLIENT" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;COD_CLIENT&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_ALVARA', 'string', '', '', '60', '<FIELD attrname="NUM_ALVARA" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NUM_ALVARA&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_EXPED', 'date', '', '', '', '<FIELD attrname="DATA_EXPED" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DATA_EXPED&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_VAL_LIC_SANI', 'date', '', '', '', '<FIELD attrname="DT_VAL_LIC_SANI" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DT_VAL_LIC_SANI&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_LIC_SANI', 'string', '', '', '1', '<FIELD attrname="TP_LIC_SANI" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;TP_LIC_SANI&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_ORGEXP', 'string', '', '', '2', '<FIELD attrname="IND_ORGEXP" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;IND_ORGEXP&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_UNID_ID', 'string', '', '', '2', '<FIELD attrname="TP_UNID_ID" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;TP_UNID_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_TURNAT', 'string', '', '', '2', '<FIELD attrname="COD_TURNAT" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;COD_TURNAT&quot;" Roundtrip="True"/></FIELD>'),
            ('SIGESTGEST', 'string', '', '', '2', '<FIELD attrname="SIGESTGEST" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;SIGESTGEST&quot;" Roundtrip="True"/></FIELD>'),
            ('CODMUNGEST', 'string', 'true', '', '7', '<FIELD attrname="CODMUNGEST" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CODMUNGEST&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_PRESTADOR', 'string', '', '', '2', '<FIELD attrname="TP_PRESTADOR" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;TP_PRESTADOR&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('NMUSUARIOEMUSO', 'string', '', '', '60', '<FIELD attrname="NMUSUARIOEMUSO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NMUSUARIOEMUSO&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFDIRETORCLINICO', 'string', '', '', '14', '<FIELD attrname="CPFDIRETORCLINICO" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CPFDIRETORCLINICO&quot;" Roundtrip="True"/></FIELD>'),
            ('REGDIRETORCLINICO', 'string', '', '', '60', '<FIELD attrname="REGDIRETORCLINICO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;REGDIRETORCLINICO&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_MOTIVO_DESAB', 'string', '', '', '2', '<FIELD attrname="CD_MOTIVO_DESAB" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CD_MOTIVO_DESAB&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_VALIDACAO', 'dateTime', '', '', '', '<FIELD attrname="DT_VALIDACAO" fieldtype="dateTime"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DT_VALIDACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_ADESAO_FILANTROP', 'string', '', 'FixedChar', '1', '<FIELD attrname="FL_ADESAO_FILANTROP" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;FL_ADESAO_FILANTROP&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_VIGENTE', 'string', '', '', '6', '<FIELD attrname="CMPT_VIGENTE" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CMPT_VIGENTE&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_URL', 'string', '', '', '60', '<FIELD attrname="NO_URL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NO_URL&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_LATITUDE', 'string', '', '', '30', '<FIELD attrname="NU_LATITUDE" fieldtype="string" WIDTH="30"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NU_LATITUDE&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_LONGITUDE', 'string', '', '', '30', '<FIELD attrname="NU_LONGITUDE" fieldtype="string" WIDTH="30"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NU_LONGITUDE&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATU_GEO', 'date', '', '', '', '<FIELD attrname="DT_ATU_GEO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;DT_ATU_GEO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_USUARIO_GEO', 'string', '', '', '60', '<FIELD attrname="NO_USUARIO_GEO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;NO_USUARIO_GEO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_NATUREZA_JUR', 'string', '', '', '4', '<FIELD attrname="CO_NATUREZA_JUR" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CO_NATUREZA_JUR&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_CNESGERADO_TRANSMISSOR', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_CNESGERADO_TRANSMISSOR" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_CNESGERADO_TRANSMISSOR&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_ESTAB_SEMPRE_ABERTO', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_ESTAB_SEMPRE_ABERTO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;TP_ESTAB_SEMPRE_ABERTO&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_GERACREDITO_GERENTE_SGIF', 'string', '', '', '1', '<FIELD attrname="ST_GERACREDITO_GERENTE_SGIF" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_GERACREDITO_GERENTE_SGIF&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_NAT_JUR_WEBSERVICE', 'string', '', '', '1', '<FIELD attrname="ST_NAT_JUR_WEBSERVICE" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_NAT_JUR_WEBSERVICE&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_DADOS_CADONLINE_WEBSERV', 'string', '', '', '1', '<FIELD attrname="ST_DADOS_CADONLINE_WEBSERV" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_DADOS_CADONLINE_WEBSERV&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_CONEXAOINTERNET', 'string', '', '', '1', '<FIELD attrname="ST_CONEXAOINTERNET" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_CONEXAOINTERNET&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_TIPO_ESTABELECIMENTO', 'string', '', '', '3', '<FIELD attrname="CO_TIPO_ESTABELECIMENTO" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CO_TIPO_ESTABELECIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_ATIVIDADE_PRINCIPAL', 'string', '', '', '3', '<FIELD attrname="CO_ATIVIDADE_PRINCIPAL" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CO_ATIVIDADE_PRINCIPAL&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_CONTRATO_FORMALIZADO', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_CONTRATO_FORMALIZADO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_CONTRATO_FORMALIZADO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_TIPO_ABRANGENCIA', 'string', '', '', '2', '<FIELD attrname="CO_TIPO_ABRANGENCIA" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CO_TIPO_ABRANGENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_COWORKING', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_COWORKING" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;ST_COWORKING&quot;" Roundtrip="True"/></FIELD>'),
        ],
        [
            ('CNES', 'string', '', '', '7', '<FIELD attrname="CNES" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES004&quot;.&quot;CNES&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CBO', 'string', 'true', '', '6', '<FIELD attrname="COD_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;COD_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINC', 'string', 'true', '', '6', '<FIELD attrname="IND_VINC" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;IND_VINC&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CNPJ_DET_VINC', 'string', '', '', '14', '<FIELD attrname="NU_CNPJ_DET_VINC" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;NU_CNPJ_DET_VINC&quot;" Roundtrip="True"/></FIELD>'),
            ('D_TERCSIH', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_TERCSIH" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;D_TERCSIH&quot;" Roundtrip="True"/></FIELD>'),
            ('CGHORAOUTR', 'i4', '', '', '', '<FIELD attrname="CGHORAOUTR" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;CGHORAOUTR&quot;" Roundtrip="True"/></FIELD>'),
            ('CG_HORAAMB', 'i4', '', '', '', '<FIELD attrname="CG_HORAAMB" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;CG_HORAAMB&quot;" Roundtrip="True"/></FIELD>'),
            ('CGHORAHOSP', 'i4', '', '', '', '<FIELD attrname="CGHORAHOSP" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;CGHORAHOSP&quot;" Roundtrip="True"/></FIELD>'),
            ('CONSELHOID', 'string', '', '', '2', '<FIELD attrname="CONSELHOID" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;CONSELHOID&quot;" Roundtrip="True"/></FIELD>'),
            ('N_REGISTRO', 'string', '', '', '60', '<FIELD attrname="N_REGISTRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;N_REGISTRO&quot;" Roundtrip="True"/></FIELD>'),
            ('SG_UF_CRM', 'string', '', '', '2', '<FIELD attrname="SG_UF_CRM" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;SG_UF_CRM&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_PRECEPTOR', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_PRECEPTOR" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;TP_PRECEPTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_RESIDENTE', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_RESIDENTE" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;TP_RESIDENTE&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('CHECKSUM', 'string', '', '', '24', '<FIELD attrname="CHECKSUM" fieldtype="string" WIDTH="24"><PARAM Name="ORIGIN" Value="&quot;LFCES021&quot;.&quot;CHECKSUM&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES005": [
        [
            ('CNPJ_MANT', 'string', 'true', '', '14', '<FIELD attrname="CNPJ_MANT" fieldtype="string" required="true" WIDTH="14"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;CNPJ_MANT&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_BANCO', 'string', '', '', '3', '<FIELD attrname="COD_BANCO" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;COD_BANCO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_AGENC', 'string', '', '', '5', '<FIELD attrname="NUM_AGENC" fieldtype="string" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;NUM_AGENC&quot;" Roundtrip="True"/></FIELD>'),
            ('R_SOCIAL', 'string', '', '', '60', '<FIELD attrname="R_SOCIAL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;R_SOCIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', '', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '5', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENT', 'string', '', '', '60', '<FIELD attrname="COMPLEMENT" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;COMPLEMENT&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRO', 'string', '', '', '60', '<FIELD attrname="BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CEP', 'string', '', '', '8', '<FIELD attrname="COD_CEP" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;COD_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', '', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('REG', 'string', '', '', '4', '<FIELD attrname="REG" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;REG&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('CONTA_CC', 'string', '', '', '14', '<FIELD attrname="CONTA_CC" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;CONTA_CC&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_FMS_FES', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_FMS_FES" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;ST_FMS_FES&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CNPJ_FMS_FES', 'string', '', '', '14', '<FIELD attrname="NU_CNPJ_FMS_FES" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;NU_CNPJ_FMS_FES&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_PREENCH', 'date', '', '', '', '<FIELD attrname="DT_PREENCH" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;DT_PREENCH&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_NATUREZA_JUR', 'string', '', '', '4', '<FIELD attrname="CO_NATUREZA_JUR" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;CO_NATUREZA_JUR&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS_MOV', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="STATUS_MOV" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;STATUS_MOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('NMUSUARIOEMUSO', 'string', '', '', '12', '<FIELD attrname="NMUSUARIOEMUSO" fieldtype="string" WIDTH="12"><PARAM Name="ORIGIN" Value="&quot;LFCES005&quot;.&quot;NMUSUARIOEMUSO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES006": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CODATPREST', 'string', 'true', '', '2', '<FIELD attrname="CODATPREST" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;CODATPREST&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CONVEN', 'string', 'true', '', '2', '<FIELD attrname="COD_CONVEN" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;COD_CONVEN&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES006&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES007": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_PROG', 'string', 'true', '', '2', '<FIELD attrname="COD_PROG" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;COD_PROG&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_ESTMUN', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="IND_ESTMUN" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;IND_ESTMUN&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES007&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES008": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES008&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CODREJEITO', 'string', 'true', '', '2', '<FIELD attrname="CODREJEITO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES008&quot;.&quot;CODREJEITO&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES008&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES008&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES008&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES008&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES009": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CODSERVICO', 'string', 'true', '', '2', '<FIELD attrname="CODSERVICO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;CODSERVICO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CARACT', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="COD_CARACT" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;COD_CARACT&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES009&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES012": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALAHBAG', 'i4', '', '', '', '<FIELD attrname="NSALAHBAG" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALAHBAG&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALAHBAG_', 'i4', '', '', '', '<FIELD attrname="NSALAHBAG_" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALAHBAG_&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALA_DPI', 'i4', '', '', '', '<FIELD attrname="NSALA_DPI" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALA_DPI&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALA_DPAC', 'i4', '', '', '', '<FIELD attrname="NSALA_DPAC" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALA_DPAC&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALAREAG', 'i4', '', '', '', '<FIELD attrname="NSALAREAG" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALAREAG&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALAREAG_', 'i4', '', '', '', '<FIELD attrname="NSALAREAG_" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALAREAG_&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALAREHCV', 'i4', '', '', '', '<FIELD attrname="NSALAREHCV" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NSALAREHCV&quot;" Roundtrip="True"/></FIELD>'),
            ('NMAQH_PROP', 'i4', '', '', '', '<FIELD attrname="NMAQH_PROP" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NMAQH_PROP&quot;" Roundtrip="True"/></FIELD>'),
            ('NMAQH_OUTR', 'i4', '', '', '', '<FIELD attrname="NMAQH_OUTR" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NMAQH_OUTR&quot;" Roundtrip="True"/></FIELD>'),
            ('NEURO_RESP', 'string', '', '', '60', '<FIELD attrname="NEURO_RESP" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;NEURO_RESP&quot;" Roundtrip="True"/></FIELD>'),
            ('CPF_NEURO', 'string', '', '', '11', '<FIELD attrname="CPF_NEURO" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;CPF_NEURO&quot;" Roundtrip="True"/></FIELD>'),
            ('DIRET_RESP', 'string', '', '', '60', '<FIELD attrname="DIRET_RESP" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;DIRET_RESP&quot;" Roundtrip="True"/></FIELD>'),
            ('CPF_DIRETO', 'string', '', '', '11', '<FIELD attrname="CPF_DIRETO" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;CPF_DIRETO&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('FILTAREIA', 'string', '', 'FixedChar', '1', '<FIELD attrname="FILTAREIA" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;FILTAREIA&quot;" Roundtrip="True"/></FIELD>'),
            ('FILTCARV', 'string', '', 'FixedChar', '1', '<FIELD attrname="FILTCARV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;FILTCARV&quot;" Roundtrip="True"/></FIELD>'),
            ('ABRAND', 'string', '', 'FixedChar', '1', '<FIELD attrname="ABRAND" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;ABRAND&quot;" Roundtrip="True"/></FIELD>'),
            ('DEIONIZ', 'string', '', 'FixedChar', '1', '<FIELD attrname="DEIONIZ" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;DEIONIZ&quot;" Roundtrip="True"/></FIELD>'),
            ('MOSMOREV', 'string', '', 'FixedChar', '1', '<FIELD attrname="MOSMOREV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;MOSMOREV&quot;" Roundtrip="True"/></FIELD>'),
            ('OUTROS', 'string', '', 'FixedChar', '1', '<FIELD attrname="OUTROS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;OUTROS&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES012&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES013": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALARSIMU', 'i4', '', '', '', '<FIELD attrname="NSALARSIMU" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSALARSIMU&quot;" Roundtrip="True"/></FIELD>'),
            ('NSALARPLAN', 'i4', '', '', '', '<FIELD attrname="NSALARPLAN" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSALARPLAN&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMEDRADM', 'string', '', '', '11', '<FIELD attrname="CPFMEDRADM" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;CPFMEDRADM&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRONCPD', 'string', '', '', '11', '<FIELD attrname="CPFMRONCPD" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;CPFMRONCPD&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRCIRON', 'string', '', '', '11', '<FIELD attrname="CPFMRCIRON" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;CPFMRCIRON&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMR_RAD', 'string', '', '', '11', '<FIELD attrname="CPFMR_RAD" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;CPFMR_RAD&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMR_FIS', 'string', '', '', '11', '<FIELD attrname="CPFMR_FIS" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;CPFMR_FIS&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLARARMFO', 'i4', '', '', '', '<FIELD attrname="NSLARARMFO" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLARARMFO&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLARCONFM', 'i4', '', '', '', '<FIELD attrname="NSLARCONFM" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLARCONFM&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLARMOLDE', 'i4', '', '', '', '<FIELD attrname="NSLARMOLDE" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLARMOLDE&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLARBOLCP', 'i4', '', '', '', '<FIELD attrname="NSLARBOLCP" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLARBOLCP&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLAQARMAZ', 'i4', '', '', '', '<FIELD attrname="NSLAQARMAZ" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLAQARMAZ&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLAQPREPA', 'i4', '', '', '', '<FIELD attrname="NSLAQPREPA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLAQPREPA&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLAQCDURA', 'i4', '', '', '', '<FIELD attrname="NSLAQCDURA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLAQCDURA&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLAQLDURA', 'i4', '', '', '', '<FIELD attrname="NSLAQLDURA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLAQLDURA&quot;" Roundtrip="True"/></FIELD>'),
            ('NSLACPFLUL', 'i4', '', '', '', '<FIELD attrname="NSLACPFLUL" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NSLACPFLUL&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRSIMULA', 'i4', '', '', '', '<FIELD attrname="QEQRSIMULA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRSIMULA&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRACELL6', 'i4', '', '', '', '<FIELD attrname="QEQRACELL6" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRACELL6&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQR_6SEME', 'i4', '', '', '', '<FIELD attrname="QEQR_6SEME" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQR_6SEME&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQR_6COME', 'i4', '', '', '', '<FIELD attrname="QEQR_6COME" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQR_6COME&quot;" Roundtrip="True"/></FIELD>'),
            ('QRORTV1050', 'i4', '', '', '', '<FIELD attrname="QRORTV1050" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QRORTV1050&quot;" Roundtrip="True"/></FIELD>'),
            ('QRORV50150', 'i4', '', '', '', '<FIELD attrname="QRORV50150" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QRORV50150&quot;" Roundtrip="True"/></FIELD>'),
            ('QROV150500', 'i4', '', '', '', '<FIELD attrname="QROV150500" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QROV150500&quot;" Roundtrip="True"/></FIELD>'),
            ('QRUNIDCOBA', 'i4', '', '', '', '<FIELD attrname="QRUNIDCOBA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QRUNIDCOBA&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRBRBAIX', 'i4', '', '', '', '<FIELD attrname="QEQRBRBAIX" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRBRBAIX&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRBRMEDI', 'i4', '', '', '', '<FIELD attrname="QEQRBRMEDI" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRBRMEDI&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRBRALTA', 'i4', '', '', '', '<FIELD attrname="QEQRBRALTA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRBRALTA&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRMONITA', 'i4', '', '', '', '<FIELD attrname="QEQRMONITA" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRMONITA&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRMONITI', 'i4', '', '', '', '<FIELD attrname="QEQRMONITI" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRMONITI&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRSISPLN', 'i4', '', '', '', '<FIELD attrname="QEQRSISPLN" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRSISPLN&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRDOSCLI', 'i4', '', '', '', '<FIELD attrname="QEQRDOSCLI" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRDOSCLI&quot;" Roundtrip="True"/></FIELD>'),
            ('QEQRFONSEL', 'i4', '', '', '', '<FIELD attrname="QEQRFONSEL" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;QEQRFONSEL&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_MEDRADM', 'string', '', '', '60', '<FIELD attrname="NM_MEDRADM" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NM_MEDRADM&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_MRONCPD', 'string', '', '', '60', '<FIELD attrname="NM_MRONCPD" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NM_MRONCPD&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_MRCIRON', 'string', '', '', '60', '<FIELD attrname="NM_MRCIRON" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NM_MRCIRON&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_MR_RAD', 'string', '', '', '60', '<FIELD attrname="NM_MR_RAD" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NM_MR_RAD&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_MRFIS', 'string', '', '', '60', '<FIELD attrname="NM_MRFIS" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NM_MRFIS&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRONC', 'string', '', '', '11', '<FIELD attrname="CPFMRONC" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;CPFMRONC&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_MRONC', 'string', '', '', '60', '<FIELD attrname="NM_MRONC" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;NM_MRONC&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES013&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES014": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_COMIS', 'string', 'true', '', '2', '<FIELD attrname="COD_COMIS" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;COD_COMIS&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_ATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;DT_ATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_DESATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;DT_DESATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES014&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES015": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_INSTAL', 'string', 'true', '', '2', '<FIELD attrname="COD_INSTAL" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;COD_INSTAL&quot;" Roundtrip="True"/></FIELD>'),
            ('QTDE_INST', 'i4', '', '', '', '<FIELD attrname="QTDE_INST" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;QTDE_INST&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_LEITOS', 'i4', '', '', '', '<FIELD attrname="NUM_LEITOS" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;NUM_LEITOS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES015&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES018": [
        [
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CPF_PROF', 'string', 'true', '', '11', '<FIELD attrname="CPF_PROF" fieldtype="string" required="true" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CPF_PROF&quot;" Roundtrip="True"/></FIELD>'),
            ('PISPASEP', 'string', '', '', '11', '<FIELD attrname="PISPASEP" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;PISPASEP&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_PROF', 'string', 'true', '', '60', '<FIELD attrname="NOME_PROF" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NOME_PROF&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_MAE', 'string', '', '', '60', '<FIELD attrname="NOME_MAE" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NOME_MAE&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_NASC', 'date', '', '', '', '<FIELD attrname="DATA_NASC" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DATA_NASC&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', '', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('SEXO', 'string', '', 'FixedChar', '1', '<FIELD attrname="SEXO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;SEXO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_LIVRO', 'string', '', '', '8', '<FIELD attrname="NUM_LIVRO" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NUM_LIVRO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_FOLHA', 'string', '', '', '4', '<FIELD attrname="NUM_FOLHA" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NUM_FOLHA&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_TERMO', 'string', '', '', '8', '<FIELD attrname="NUM_TERMO" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NUM_TERMO&quot;" Roundtrip="True"/></FIELD>'),
            ('CODORGEMIS', 'string', '', '', '2', '<FIELD attrname="CODORGEMIS" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CODORGEMIS&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_EMISS', 'date', '', '', '', '<FIELD attrname="DATA_EMISS" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DATA_EMISS&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_IDENT', 'string', '', '', '15', '<FIELD attrname="NUM_IDENT" fieldtype="string" WIDTH="15"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NUM_IDENT&quot;" Roundtrip="True"/></FIELD>'),
            ('SIGLA_EST', 'string', '', '', '2', '<FIELD attrname="SIGLA_EST" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;SIGLA_EST&quot;" Roundtrip="True"/></FIELD>'),
            ('DTEMIIDENT', 'date', '', '', '', '<FIELD attrname="DTEMIIDENT" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DTEMIIDENT&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ENTRA', 'date', '', '', '', '<FIELD attrname="DATA_ENTRA" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DATA_ENTRA&quot;" Roundtrip="True"/></FIELD>'),
            ('CTPS_NUMER', 'string', '', '', '7', '<FIELD attrname="CTPS_NUMER" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CTPS_NUMER&quot;" Roundtrip="True"/></FIELD>'),
            ('SERIE', 'string', '', '', '5', '<FIELD attrname="SERIE" fieldtype="string" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;SERIE&quot;" Roundtrip="True"/></FIELD>'),
            ('SIGESTCTPS', 'string', '', '', '2', '<FIELD attrname="SIGESTCTPS" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;SIGESTCTPS&quot;" Roundtrip="True"/></FIELD>'),
            ('DTEMISCTPS', 'date', '', '', '', '<FIELD attrname="DTEMISCTPS" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DTEMISCTPS&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', '', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '10', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENT', 'string', '', '', '60', '<FIELD attrname="COMPLEMENT" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COMPLEMENT&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRODIST', 'string', '', '', '60', '<FIELD attrname="BAIRRODIST" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;BAIRRODIST&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CEP', 'string', '', '', '8', '<FIELD attrname="COD_CEP" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COD_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('SIGLA_UF', 'string', '', '', '2', '<FIELD attrname="SIGLA_UF" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;SIGLA_UF&quot;" Roundtrip="True"/></FIELD>'),
            ('CODESCOLAR', 'string', '', '', '2', '<FIELD attrname="CODESCOLAR" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CODESCOLAR&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CERTID', 'string', '', '', '2', '<FIELD attrname="COD_CERTID" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COD_CERTID&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_NACIO', 'string', '', 'FixedChar', '1', '<FIELD attrname="IND_NACIO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;IND_NACIO&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_CARTO', 'string', '', '', '60', '<FIELD attrname="NOME_CARTO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NOME_CARTO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_BANCO', 'string', '', '', '3', '<FIELD attrname="COD_BANCO" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COD_BANCO&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_PAIS', 'string', '', '', '60', '<FIELD attrname="NOME_PAIS" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NOME_PAIS&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_AGENC', 'string', '', '', '5', '<FIELD attrname="NUM_AGENC" fieldtype="string" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NUM_AGENC&quot;" Roundtrip="True"/></FIELD>'),
            ('CONTA_CC', 'string', '', '', '14', '<FIELD attrname="CONTA_CC" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CONTA_CC&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CNS', 'string', '', '', '60', '<FIELD attrname="COD_CNS" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COD_CNS&quot;" Roundtrip="True"/></FIELD>'),
            ('D_TERCSIH', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_TERCSIH" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;D_TERCSIH&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('NMUSUARIOEMUSO', 'string', '', '', '12', '<FIELD attrname="NMUSUARIOEMUSO" fieldtype="string" WIDTH="12"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NMUSUARIOEMUSO&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_RACA', 'string', '', '', '2', '<FIELD attrname="CD_RACA" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CD_RACA&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_ETNIA', 'string', '', '', '3', '<FIELD attrname="CO_ETNIA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CO_ETNIA&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_PAI', 'string', '', '', '60', '<FIELD attrname="NOME_PAI" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NOME_PAI&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_TP_LOGR', 'string', '', '', '3', '<FIELD attrname="CD_TP_LOGR" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CD_TP_LOGR&quot;" Roundtrip="True"/></FIELD>'),
            ('PORTARIA', 'string', '', '', '16', '<FIELD attrname="PORTARIA" fieldtype="string" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;PORTARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_NATUR', 'date', '', '', '', '<FIELD attrname="DT_NATUR" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DT_NATUR&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_PAIS', 'string', '', '', '3', '<FIELD attrname="CD_PAIS" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CD_PAIS&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN_RES', 'string', '', '', '6', '<FIELD attrname="COD_MUN_RES" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;COD_MUN_RES&quot;" Roundtrip="True"/></FIELD>'),
            ('UF_RES', 'string', '', 'FixedChar', '2', '<FIELD attrname="UF_RES" fieldtype="string" SUBTYPE="FixedChar" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;UF_RES&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_EMAIL', 'string', '', '', '60', '<FIELD attrname="NO_EMAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NO_EMAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PAIS_RESID', 'string', '', '', '3', '<FIELD attrname="CO_PAIS_RESID" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;CO_PAIS_RESID&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CARTEIRA_HAB', 'string', '', '', '15', '<FIELD attrname="NU_CARTEIRA_HAB" fieldtype="string" WIDTH="15"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NU_CARTEIRA_HAB&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_EMIS_CARTEIRA_HAB', 'date', '', '', '', '<FIELD attrname="DT_EMIS_CARTEIRA_HAB" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;DT_EMIS_CARTEIRA_HAB&quot;" Roundtrip="True"/></FIELD>'),
            ('UF_CARTEIRA_HAB', 'string', '', '', '2', '<FIELD attrname="UF_CARTEIRA_HAB" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;UF_CARTEIRA_HAB&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_NMPROF_CADSUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_NMPROF_CADSUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;ST_NMPROF_CADSUS&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_CNS_CORRIGIDO', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_CNS_CORRIGIDO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;ST_CNS_CORRIGIDO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_SOCIAL', 'string', '', '', '60', '<FIELD attrname="NO_SOCIAL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES018&quot;.&quot;NO_SOCIAL&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES019": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CODSERVCOM', 'string', 'true', '', '2', '<FIELD attrname="CODSERVCOM" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;CODSERVCOM&quot;" Roundtrip="True"/></FIELD>'),
            ('INDSERVCOM', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="INDSERVCOM" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;INDSERVCOM&quot;" Roundtrip="True"/></FIELD>'),
            ('CNPJ', 'string', 'true', '', '14', '<FIELD attrname="CNPJ" fieldtype="string" required="true" WIDTH="14"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;CNPJ&quot;" Roundtrip="True"/></FIELD>'),
            ('R_SOCIAL', 'string', 'true', '', '60', '<FIELD attrname="R_SOCIAL" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;R_SOCIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', 'true', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES019&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES020": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_EQUIP', 'string', 'true', '', '2', '<FIELD attrname="COD_EQUIP" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;COD_EQUIP&quot;" Roundtrip="True"/></FIELD>'),
            ('QTDE_EXIST', 'i4', '', '', '', '<FIELD attrname="QTDE_EXIST" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;QTDE_EXIST&quot;" Roundtrip="True"/></FIELD>'),
            ('QTDE_USO', 'i4', '', '', '', '<FIELD attrname="QTDE_USO" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;QTDE_USO&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_SUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="IND_SUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;IND_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('CODTPEQUIP', 'string', 'true', 'FixedChar', '2', '<FIELD attrname="CODTPEQUIP" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;CODTPEQUIP&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('QT_SUS', 'i4', '', '', '', '<FIELD attrname="QT_SUS" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES020&quot;.&quot;QT_SUS&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES023": [
        [
            ('COD_BANCO', 'string', 'true', 'FixedChar', '3', '<FIELD attrname="COD_BANCO" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="3"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES023&quot;.&quot;COD_BANCO&quot;" Roundtrip="True"/></FIELD>'),
            ('DESCRICAO', 'string', 'true', '', '60', '<FIELD attrname="DESCRICAO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES023&quot;.&quot;DESCRICAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES023&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES027": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('NSRECEPCAD', 'string', '', '', '3', '<FIELD attrname="NSRECEPCAD" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSRECEPCAD&quot;" Roundtrip="True"/></FIELD>'),
            ('NSTRIAGHMT', 'string', '', '', '3', '<FIELD attrname="NSTRIAGHMT" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSTRIAGHMT&quot;" Roundtrip="True"/></FIELD>'),
            ('NSTRIAGCLN', 'string', '', '', '3', '<FIELD attrname="NSTRIAGCLN" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSTRIAGCLN&quot;" Roundtrip="True"/></FIELD>'),
            ('NSCOLETA', 'string', '', '', '3', '<FIELD attrname="NSCOLETA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSCOLETA&quot;" Roundtrip="True"/></FIELD>'),
            ('NSAFERESE', 'string', '', '', '3', '<FIELD attrname="NSAFERESE" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSAFERESE&quot;" Roundtrip="True"/></FIELD>'),
            ('NSPRESTOQ', 'string', '', '', '3', '<FIELD attrname="NSPRESTOQ" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSPRESTOQ&quot;" Roundtrip="True"/></FIELD>'),
            ('NSPROCES', 'string', '', '', '3', '<FIELD attrname="NSPROCES" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSPROCES&quot;" Roundtrip="True"/></FIELD>'),
            ('NSESTOQUE', 'string', '', '', '3', '<FIELD attrname="NSESTOQUE" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSESTOQUE&quot;" Roundtrip="True"/></FIELD>'),
            ('NSDISTRIB', 'string', '', '', '3', '<FIELD attrname="NSDISTRIB" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSDISTRIB&quot;" Roundtrip="True"/></FIELD>'),
            ('NSOROLOGIA', 'string', '', '', '3', '<FIELD attrname="NSOROLOGIA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSOROLOGIA&quot;" Roundtrip="True"/></FIELD>'),
            ('NSIMUNOHEM', 'string', '', '', '3', '<FIELD attrname="NSIMUNOHEM" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSIMUNOHEM&quot;" Roundtrip="True"/></FIELD>'),
            ('NSPRETRANF', 'string', '', '', '3', '<FIELD attrname="NSPRETRANF" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSPRETRANF&quot;" Roundtrip="True"/></FIELD>'),
            ('NSHEMOSTA', 'string', '', '', '3', '<FIELD attrname="NSHEMOSTA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSHEMOSTA&quot;" Roundtrip="True"/></FIELD>'),
            ('NSCONTROLQ', 'string', '', '', '3', '<FIELD attrname="NSCONTROLQ" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSCONTROLQ&quot;" Roundtrip="True"/></FIELD>'),
            ('NSBIOMOLEC', 'string', '', '', '3', '<FIELD attrname="NSBIOMOLEC" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSBIOMOLEC&quot;" Roundtrip="True"/></FIELD>'),
            ('NSIMUNOFEN', 'string', '', '', '3', '<FIELD attrname="NSIMUNOFEN" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSIMUNOFEN&quot;" Roundtrip="True"/></FIELD>'),
            ('NSTRANSFUS', 'string', '', '', '3', '<FIELD attrname="NSTRANSFUS" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSTRANSFUS&quot;" Roundtrip="True"/></FIELD>'),
            ('NSSGDOADOR', 'string', '', '', '3', '<FIELD attrname="NSSGDOADOR" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NSSGDOADOR&quot;" Roundtrip="True"/></FIELD>'),
            ('QECADRECLI', 'string', '', '', '3', '<FIELD attrname="QECADRECLI" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QECADRECLI&quot;" Roundtrip="True"/></FIELD>'),
            ('QECENTREFR', 'string', '', '', '3', '<FIELD attrname="QECENTREFR" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QECENTREFR&quot;" Roundtrip="True"/></FIELD>'),
            ('QERFGUASNG', 'string', '', '', '3', '<FIELD attrname="QERFGUASNG" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QERFGUASNG&quot;" Roundtrip="True"/></FIELD>'),
            ('QECONGRAPD', 'string', '', '', '3', '<FIELD attrname="QECONGRAPD" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QECONGRAPD&quot;" Roundtrip="True"/></FIELD>'),
            ('QEEXTAPLSM', 'string', '', '', '3', '<FIELD attrname="QEEXTAPLSM" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEEXTAPLSM&quot;" Roundtrip="True"/></FIELD>'),
            ('QEFREEZE18', 'string', '', '', '3', '<FIELD attrname="QEFREEZE18" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEFREEZE18&quot;" Roundtrip="True"/></FIELD>'),
            ('QEFREEZE30', 'string', '', '', '3', '<FIELD attrname="QEFREEZE30" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEFREEZE30&quot;" Roundtrip="True"/></FIELD>'),
            ('QEAGITPLQT', 'string', '', '', '3', '<FIELD attrname="QEAGITPLQT" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEAGITPLQT&quot;" Roundtrip="True"/></FIELD>'),
            ('QESELADORA', 'string', '', '', '3', '<FIELD attrname="QESELADORA" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QESELADORA&quot;" Roundtrip="True"/></FIELD>'),
            ('QEIRRADHEM', 'string', '', '', '3', '<FIELD attrname="QEIRRADHEM" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEIRRADHEM&quot;" Roundtrip="True"/></FIELD>'),
            ('QEAGLTNOSC', 'string', '', '', '3', '<FIELD attrname="QEAGLTNOSC" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEAGLTNOSC&quot;" Roundtrip="True"/></FIELD>'),
            ('QEMAQAFRES', 'string', '', '', '3', '<FIELD attrname="QEMAQAFRES" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QEMAQAFRES&quot;" Roundtrip="True"/></FIELD>'),
            ('QERFGAREAG', 'string', '', '', '3', '<FIELD attrname="QERFGAREAG" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QERFGAREAG&quot;" Roundtrip="True"/></FIELD>'),
            ('QERFGAMSTS', 'string', '', '', '3', '<FIELD attrname="QERFGAMSTS" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QERFGAMSTS&quot;" Roundtrip="True"/></FIELD>'),
            ('QECAPFLLAM', 'string', '', '', '3', '<FIELD attrname="QECAPFLLAM" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;QECAPFLLAM&quot;" Roundtrip="True"/></FIELD>'),
            ('NOMRHEMOT', 'string', '', '', '60', '<FIELD attrname="NOMRHEMOT" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NOMRHEMOT&quot;" Roundtrip="True"/></FIELD>'),
            ('NOMRHEMAT', 'string', '', '', '60', '<FIELD attrname="NOMRHEMAT" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NOMRHEMAT&quot;" Roundtrip="True"/></FIELD>'),
            ('NORETECSO', 'string', '', '', '60', '<FIELD attrname="NORETECSO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NORETECSO&quot;" Roundtrip="True"/></FIELD>'),
            ('NOMRCAPAC', 'string', '', '', '60', '<FIELD attrname="NOMRCAPAC" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;NOMRCAPAC&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRHEMOT', 'string', '', '', '11', '<FIELD attrname="CPFMRHEMOT" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;CPFMRHEMOT&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRHEMAT', 'string', '', '', '11', '<FIELD attrname="CPFMRHEMAT" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;CPFMRHEMAT&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRTECSO', 'string', '', '', '11', '<FIELD attrname="CPFMRTECSO" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;CPFMRTECSO&quot;" Roundtrip="True"/></FIELD>'),
            ('CPFMRCAPAC', 'string', '', '', '11', '<FIELD attrname="CPFMRCAPAC" fieldtype="string" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;CPFMRCAPAC&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES027&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES032": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CODSERVICO', 'string', 'true', '', '3', '<FIELD attrname="CODSERVICO" fieldtype="string" required="true" WIDTH="3"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;CODSERVICO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CARACT', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="COD_CARACT" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;COD_CARACT&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CLASS', 'string', 'true', '', '3', '<FIELD attrname="COD_CLASS" fieldtype="string" required="true" WIDTH="3"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;COD_CLASS&quot;" Roundtrip="True"/></FIELD>'),
            ('CNPJCPF', 'string', 'true', '', '14', '<FIELD attrname="CNPJCPF" fieldtype="string" required="true" WIDTH="14"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;CNPJCPF&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_ENDCOMPL', 'string', 'true', '', '5', '<FIELD attrname="COD_ENDCOMPL" fieldtype="string" required="true" WIDTH="5"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;COD_ENDCOMPL&quot;" Roundtrip="True"/></FIELD>'),
            ('D_AMB', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_AMB" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;D_AMB&quot;" Roundtrip="True"/></FIELD>'),
            ('D_AMBSUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_AMBSUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;D_AMBSUS&quot;" Roundtrip="True"/></FIELD>'),
            ('D_HOSP', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_HOSP" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;D_HOSP&quot;" Roundtrip="True"/></FIELD>'),
            ('D_HOSPSUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="D_HOSPSUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;D_HOSPSUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_ATIVO_SN', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_ATIVO_SN" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES032&quot;.&quot;ST_ATIVO_SN&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES034": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COOP_ID', 'string', 'true', '', '31', '<FIELD attrname="COOP_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;COOP_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CBO', 'string', 'true', '', '6', '<FIELD attrname="CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES034&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES035": [
        [
            ('NO_TABELA', 'string', '', '', '60', '<FIELD attrname="NO_TABELA" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;NO_TABELA&quot;" Roundtrip="True"/></FIELD>'),
            ('COMP_CHV1', 'string', '', '', '60', '<FIELD attrname="COMP_CHV1" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;COMP_CHV1&quot;" Roundtrip="True"/></FIELD>'),
            ('COMP_CHV2', 'string', '', '', '60', '<FIELD attrname="COMP_CHV2" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;COMP_CHV2&quot;" Roundtrip="True"/></FIELD>'),
            ('COMP_CHV3', 'string', '', '', '60', '<FIELD attrname="COMP_CHV3" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;COMP_CHV3&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_PROCESS', 'date', '', '', '', '<FIELD attrname="DT_PROCESS" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;DT_PROCESS&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_EXPORT', 'date', '', '', '', '<FIELD attrname="DT_EXPORT" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;DT_EXPORT&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_EXCL', 'date', '', '', '', '<FIELD attrname="DT_EXCL" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;DT_EXCL&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_MANTEN', 'string', '', '', '60', '<FIELD attrname="NO_MANTEN" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;NO_MANTEN&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_PROF', 'string', '', '', '60', '<FIELD attrname="NO_PROF" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;NO_PROF&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_ESTAB', 'string', '', '', '60', '<FIELD attrname="NO_ESTAB" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;NO_ESTAB&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', '', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', '', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPETENCIA', 'string', '', '', '6', '<FIELD attrname="COMPETENCIA" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES035&quot;.&quot;COMPETENCIA&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES037": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_EQUIPE', 'string', '', '', '10', '<FIELD attrname="CO_EQUIPE" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CO_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_EQUIPE', 'string', 'true', '', '2', '<FIELD attrname="TP_EQUIPE" fieldtype="string" required="true" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_SUB_TIPO_EQUIPE', 'string', '', '', '2', '<FIELD attrname="CO_SUB_TIPO_EQUIPE" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CO_SUB_TIPO_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_REFERENCIA', 'string', 'true', '', '60', '<FIELD attrname="NM_REFERENCIA" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;NM_REFERENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATIVACAO', 'date', 'true', '', '', '<FIELD attrname="DT_ATIVACAO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;DT_ATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_DESATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;DT_DESATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_QUILOMB', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_QUILOMB" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_QUILOMB&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_ASSENT', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_ASSENT" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_ASSENT&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_GERAL', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_GERAL" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_GERAL&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_ESCOLA', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_ESCOLA" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_ESCOLA&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_PRONASCI', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_PRONASCI" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_PRONASCI&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_INDIGENA', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_INDIGENA" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_INDIGENA&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_RIBEIRINHA', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_RIBEIRINHA" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_RIBEIRINHA&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_SITUACAO_RUA', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_SITUACAO_RUA" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_SITUACAO_RUA&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_PRIV_LIBERDADE', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_PRIV_LIBERDADE" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_PRIV_LIBERDADE&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_CONFLITO_LEI', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_CONFLITO_LEI" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_CONFLITO_LEI&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_POP_ASSIST_ADOL_CONF_LEI', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_POP_ASSIST_ADOL_CONF_LEI" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;TP_POP_ASSIST_ADOL_CONF_LEI&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_MOTIVO_DESATIV', 'string', '', '', '2', '<FIELD attrname="CD_MOTIVO_DESATIV" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CD_MOTIVO_DESATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_TP_DESATIV', 'string', '', '', '2', '<FIELD attrname="CD_TP_DESATIV" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CD_TP_DESATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_UOM', 'string', '', '', '7', '<FIELD attrname="CO_CNES_UOM" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CO_CNES_UOM&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CH_AMB_UOM', 'i4', '', '', '', '<FIELD attrname="NU_CH_AMB_UOM" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;NU_CH_AMB_UOM&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PROF_SUS_PRECEPTOR', 'string', '', '', '16', '<FIELD attrname="CO_PROF_SUS_PRECEPTOR" fieldtype="string" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CO_PROF_SUS_PRECEPTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_PRECEPTOR', 'string', '', '', '7', '<FIELD attrname="CO_CNES_PRECEPTOR" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;CO_CNES_PRECEPTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUSMOV', 'string', '', 'FixedChar', '1', '<FIELD attrname="STATUSMOV" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;STATUSMOV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES037&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES038": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CBO', 'string', 'true', '', '6', '<FIELD attrname="COD_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;COD_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINC', 'string', 'true', '', '6', '<FIELD attrname="IND_VINC" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;IND_VINC&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_EQUIPEMINIMA', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="FL_EQUIPEMINIMA" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;FL_EQUIPEMINIMA&quot;" Roundtrip="True"/></FIELD>'),
            ('MICROAREA', 'string', '', '', '2', '<FIELD attrname="MICROAREA" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;MICROAREA&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUN_ATUACAO', 'string', '', '', '6', '<FIELD attrname="CO_MUN_ATUACAO" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;CO_MUN_ATUACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ENTRADA', 'date', 'true', '', '', '<FIELD attrname="DT_ENTRADA" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;DT_ENTRADA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESLIGAMENTO', 'date', '', '', '', '<FIELD attrname="DT_DESLIGAMENTO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;DT_DESLIGAMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES_OUTRAEQUIPE', 'string', '', '', '7', '<FIELD attrname="CNES_OUTRAEQUIPE" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;CNES_OUTRAEQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN_OUTRAEQUIPE', 'string', '', '', '6', '<FIELD attrname="COD_MUN_OUTRAEQUIPE" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;COD_MUN_OUTRAEQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA_OUTRAEQUIPE', 'string', '', '', '4', '<FIELD attrname="COD_AREA_OUTRAEQUIPE" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;COD_AREA_OUTRAEQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID_CH_COMPL', 'string', '', '', '16', '<FIELD attrname="PROF_ID_CH_COMPL" fieldtype="string" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;PROF_ID_CH_COMPL&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CBO_CH_COMPL', 'string', '', '', '6', '<FIELD attrname="COD_CBO_CH_COMPL" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;COD_CBO_CH_COMPL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES038&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES039": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('SQ_RESIDENCIA', 'i4', 'true', '', '', '<FIELD attrname="SQ_RESIDENCIA" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;SQ_RESIDENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_RESIDENCIA', 'string', 'true', '', '10', '<FIELD attrname="NU_RESIDENCIA" fieldtype="string" required="true" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_RESIDENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_REFERENCIA', 'string', 'true', '', '60', '<FIELD attrname="NM_REFERENCIA" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NM_REFERENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_LOGRADOURO', 'string', '', '', '60', '<FIELD attrname="DS_LOGRADOURO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;DS_LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_COMPLEMENTO', 'string', '', '', '60', '<FIELD attrname="DS_COMPLEMENTO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;DS_COMPLEMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_LOGRADOURO', 'string', '', '', '10', '<FIELD attrname="NU_LOGRADOURO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_BAIRRO', 'string', '', '', '60', '<FIELD attrname="DS_BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;DS_BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', '', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CEP', 'string', '', '', '8', '<FIELD attrname="CO_CEP" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;CO_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_DDD', 'string', '', '', '3', '<FIELD attrname="CO_DDD" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;CO_DDD&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_TELEFONE', 'string', '', '', '40', '<FIELD attrname="NU_TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SRT', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_SRT" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;TP_SRT&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CUIDADORES', 'i4', '', '', '', '<FIELD attrname="NU_CUIDADORES" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_CUIDADORES&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CAPACIDADE_MASC', 'i4', '', '', '', '<FIELD attrname="NU_CAPACIDADE_MASC" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_CAPACIDADE_MASC&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CAPACIDADE_FEM', 'i4', '', '', '', '<FIELD attrname="NU_CAPACIDADE_FEM" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_CAPACIDADE_FEM&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CBO', 'string', 'true', '', '6', '<FIELD attrname="COD_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;COD_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINC', 'string', 'true', '', '6', '<FIELD attrname="IND_VINC" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;IND_VINC&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_PARCERIA_ONG', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_PARCERIA_ONG" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;ST_PARCERIA_ONG&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CNPJ_ONG', 'string', '', '', '14', '<FIELD attrname="NU_CNPJ_ONG" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;NU_CNPJ_ONG&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_ATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;DT_ATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_DESATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;DT_DESATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES039&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES040": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES040&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_SEGMENTO', 'string', 'true', '', '2', '<FIELD attrname="CD_SEGMENTO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES040&quot;.&quot;CD_SEGMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_SEGMENTO', 'string', 'true', '', '60', '<FIELD attrname="DS_SEGMENTO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES040&quot;.&quot;DS_SEGMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SEGMENTO', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SEGMENTO" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES040&quot;.&quot;TP_SEGMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES040&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES040&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES041": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES041&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES041&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_AREA', 'string', 'true', '', '60', '<FIELD attrname="DS_AREA" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES041&quot;.&quot;DS_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_SEGMENTO', 'string', 'true', '', '2', '<FIELD attrname="CD_SEGMENTO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES041&quot;.&quot;CD_SEGMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES041&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES041&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES043": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_CHDIFER', 'string', 'true', '', '2', '<FIELD attrname="TP_CHDIFER" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;TP_CHDIFER&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_CHDIFER', 'i4', 'true', '', '', '<FIELD attrname="SEQ_CHDIFER" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;SEQ_CHDIFER&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES_CHDIFER', 'string', '', '', '7', '<FIELD attrname="CNES_CHDIFER" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;CNES_CHDIFER&quot;" Roundtrip="True"/></FIELD>'),
            ('CGHORAOUTR', 'i4', '', '', '', '<FIELD attrname="CGHORAOUTR" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;CGHORAOUTR&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES043&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES044": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES_ATENDCOMP', 'string', 'true', '', '7', '<FIELD attrname="CNES_ATENDCOMP" fieldtype="string" required="true" WIDTH="7"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;CNES_ATENDCOMP&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES044&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES045": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_HABILITACAO', 'string', 'true', '', '4', '<FIELD attrname="CO_HABILITACAO" fieldtype="string" required="true" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;CO_HABILITACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_INICIAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_INICIAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;CMPT_INICIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_FINAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_FINAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;CMPT_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('QT_LEITOS', 'i4', 'true', '', '', '<FIELD attrname="QT_LEITOS" fieldtype="i4" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;QT_LEITOS&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_PORTARIA', 'string', '', '', '50', '<FIELD attrname="NU_PORTARIA" fieldtype="string" WIDTH="50"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;NU_PORTARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_LANCAMENTO', 'date', 'true', '', '', '<FIELD attrname="DT_LANCAMENTO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;DT_LANCAMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES045&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES046": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_REGRA', 'string', 'true', '', '4', '<FIELD attrname="CO_REGRA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;CO_REGRA&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_INICIAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_INICIAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;CMPT_INICIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_FINAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_FINAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;CMPT_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_PORTARIA', 'string', '', '', '50', '<FIELD attrname="NU_PORTARIA" fieldtype="string" WIDTH="50"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;NU_PORTARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_LANCAMENTO', 'date', 'true', '', '', '<FIELD attrname="DT_LANCAMENTO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;DT_LANCAMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES046&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES047": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('SQ_RESIDENCIA', 'i4', 'true', '', '', '<FIELD attrname="SQ_RESIDENCIA" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;SQ_RESIDENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CBO', 'string', 'true', '', '6', '<FIELD attrname="COD_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;COD_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINC', 'string', 'true', '', '6', '<FIELD attrname="IND_VINC" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;IND_VINC&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES047&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES051": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_GESTAO', 'string', 'true', '', '4', '<FIELD attrname="CO_GESTAO" fieldtype="string" required="true" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;CO_GESTAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_INICIAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_INICIAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;CMPT_INICIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_FINAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_FINAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;CMPT_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_PORTARIA', 'string', '', '', '50', '<FIELD attrname="NU_PORTARIA" fieldtype="string" WIDTH="50"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;NU_PORTARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_LANCAMENTO', 'date', 'true', '', '', '<FIELD attrname="DT_LANCAMENTO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;DT_LANCAMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES051&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES052": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES052&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_UNID_ID', 'string', 'true', '', '2', '<FIELD attrname="TP_UNID_ID" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES052&quot;.&quot;TP_UNID_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_SUBTIPO', 'string', 'true', '', '3', '<FIELD attrname="CD_SUBTIPO" fieldtype="string" required="true" WIDTH="3"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES052&quot;.&quot;CD_SUBTIPO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES052&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES052&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES053": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_INTEGRASUS', 'string', 'true', '', '4', '<FIELD attrname="CO_INTEGRASUS" fieldtype="string" required="true" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;CO_INTEGRASUS&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_INICIAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_INICIAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;CMPT_INICIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_FINAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_FINAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;CMPT_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_PORTARIA', 'string', '', '', '50', '<FIELD attrname="NU_PORTARIA" fieldtype="string" WIDTH="50"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;NU_PORTARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_LANCAMENTO', 'date', 'true', '', '', '<FIELD attrname="DT_LANCAMENTO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;DT_LANCAMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_LEITOS', 'i4', '', '', '', '<FIELD attrname="NU_LEITOS" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;NU_LEITOS&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES053&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES055": [
        [
            ('COMPETENCIA', 'string', 'true', '', '6', '<FIELD attrname="COMPETENCIA" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;COMPETENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN_GESTOR', 'string', 'true', '', '7', '<FIELD attrname="COD_MUN_GESTOR" fieldtype="string" required="true" WIDTH="7"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;COD_MUN_GESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('DESTINO', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="DESTINO" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;DESTINO&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES', 'string', 'true', '', '7', '<FIELD attrname="CNES" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;CNES&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_FANTA', 'string', 'true', '', '60', '<FIELD attrname="NOME_FANTA" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;NOME_FANTA&quot;" Roundtrip="True"/></FIELD>'),
            ('NM_ARQUIVO_EXP', 'string', '', '', '60', '<FIELD attrname="NM_ARQUIVO_EXP" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;NM_ARQUIVO_EXP&quot;" Roundtrip="True"/></FIELD>'),
            ('STATUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="STATUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;STATUS&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_MAC', 'string', 'true', '', '20', '<FIELD attrname="NU_MAC" fieldtype="string" required="true" WIDTH="20"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;NU_MAC&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_TRANSMISSAO_DIRETA', 'string', '', '', '1', '<FIELD attrname="FL_TRANSMISSAO_DIRETA" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;FL_TRANSMISSAO_DIRETA&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES055&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES056": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_ENDCOMPL', 'string', 'true', '', '5', '<FIELD attrname="COD_ENDCOMPL" fieldtype="string" required="true" WIDTH="5"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;COD_ENDCOMPL&quot;" Roundtrip="True"/></FIELD>'),
            ('IDENTIFICACAO', 'string', 'true', '', '60', '<FIELD attrname="IDENTIFICACAO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;IDENTIFICACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_TP_LOGR', 'string', '', '', '3', '<FIELD attrname="CD_TP_LOGR" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;CD_TP_LOGR&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', 'true', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '10', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENTO', 'string', '', '', '60', '<FIELD attrname="COMPLEMENTO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;COMPLEMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRO', 'string', '', '', '60', '<FIELD attrname="BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CEP', 'string', 'true', '', '8', '<FIELD attrname="COD_CEP" fieldtype="string" required="true" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;COD_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', 'true', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('DDD_TEL', 'string', '', '', '3', '<FIELD attrname="DDD_TEL" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;DDD_TEL&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('DDD_FAX', 'string', '', '', '3', '<FIELD attrname="DDD_FAX" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;DDD_FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('FAX', 'string', '', '', '40', '<FIELD attrname="FAX" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('E_MAIL', 'string', '', '', '60', '<FIELD attrname="E_MAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;E_MAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATIVACAO', 'date', 'true', '', '', '<FIELD attrname="DT_ATIVACAO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;DT_ATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_DESATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;DT_DESATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES056&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES058": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES058&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_BANCO', 'string', '', '', '3', '<FIELD attrname="COD_BANCO" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES058&quot;.&quot;COD_BANCO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUM_AGENC', 'string', '', '', '5', '<FIELD attrname="NUM_AGENC" fieldtype="string" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES058&quot;.&quot;NUM_AGENC&quot;" Roundtrip="True"/></FIELD>'),
            ('CONTA_CC', 'string', '', '', '14', '<FIELD attrname="CONTA_CC" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES058&quot;.&quot;CONTA_CC&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES058&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES058&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES059": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN_ESF', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN_ESF" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;COD_MUN_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA_ESF', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA_ESF" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;COD_AREA_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE_ESF', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE_ESF" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;SEQ_EQUIPE_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQUENCIAL', 'i4', 'true', '', '', '<FIELD attrname="SEQUENCIAL" fieldtype="i4" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;SEQUENCIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_EQUIPE_ESF', 'string', 'true', '', '2', '<FIELD attrname="TP_EQUIPE_ESF" fieldtype="string" required="true" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;TP_EQUIPE_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES_ESF', 'string', 'true', '', '7', '<FIELD attrname="CNES_ESF" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;CNES_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_FANTA_ESF', 'string', '', '', '60', '<FIELD attrname="NOME_FANTA_ESF" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;NOME_FANTA_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_SEGMENTO_ESF', 'string', '', '', '2', '<FIELD attrname="CD_SEGMENTO_ESF" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;CD_SEGMENTO_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_SEGMENTO_ESF', 'string', '', '', '60', '<FIELD attrname="DS_SEGMENTO_ESF" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;DS_SEGMENTO_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_AREA_ESF', 'string', '', '', '60', '<FIELD attrname="DS_AREA_ESF" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;DS_AREA_ESF&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES059&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES065": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES065&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_DSEI', 'string', '', '', '4', '<FIELD attrname="CO_DSEI" fieldtype="string" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES065&quot;.&quot;CO_DSEI&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_POLOBASE', 'string', '', '', '6', '<FIELD attrname="CD_POLOBASE" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES065&quot;.&quot;CD_POLOBASE&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_ALDEIA', 'string', '', '', '60', '<FIELD attrname="CD_ALDEIA" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES065&quot;.&quot;CD_ALDEIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES065&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES065&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES072": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_ADESAO', 'string', 'true', '', '4', '<FIELD attrname="CO_ADESAO" fieldtype="string" required="true" WIDTH="4"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;CO_ADESAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_INICIAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_INICIAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;CMPT_INICIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CMPT_FINAL', 'string', 'true', '', '6', '<FIELD attrname="CMPT_FINAL" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;CMPT_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_PORTARIA', 'string', '', '', '50', '<FIELD attrname="NU_PORTARIA" fieldtype="string" WIDTH="50"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;NU_PORTARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_LANCAMENTO', 'date', 'true', '', '', '<FIELD attrname="DT_LANCAMENTO" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;DT_LANCAMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES072&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES073": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CPF', 'string', 'true', '', '11', '<FIELD attrname="CO_CPF" fieldtype="string" required="true" WIDTH="11"><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;CO_CPF&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_REPRESENTANTE', 'string', 'true', '', '60', '<FIELD attrname="NO_REPRESENTANTE" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;NO_REPRESENTANTE&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_CARGO', 'string', '', '', '60', '<FIELD attrname="DS_CARGO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;DS_CARGO&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_E_MAIL', 'string', '', '', '60', '<FIELD attrname="DS_E_MAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;DS_E_MAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES073&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES074": [
        [
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_ARTIGO_PORT', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="FL_ARTIGO_PORT" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;FL_ARTIGO_PORT&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_JUSTIFICATIVA', 'string', 'true', '', '256', '<FIELD attrname="DS_JUSTIFICATIVA" fieldtype="string" required="true" WIDTH="256"><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;DS_JUSTIFICATIVA&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUN_GESTOR', 'string', 'true', '', '6', '<FIELD attrname="CO_MUN_GESTOR" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;CO_MUN_GESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_GESTOR', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="IND_GESTOR" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;IND_GESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES074&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES075": [
        [
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('FL_ARTIGO_PORT', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="FL_ARTIGO_PORT" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;FL_ARTIGO_PORT&quot;" Roundtrip="True"/></FIELD>'),
            ('SQ_JUSTIFICATIVA', 'i4', 'true', '', '', '<FIELD attrname="SQ_JUSTIFICATIVA" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;SQ_JUSTIFICATIVA&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_JUSTIFICATIVA', 'string', 'true', '', '256', '<FIELD attrname="DS_JUSTIFICATIVA" fieldtype="string" required="true" WIDTH="256"><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;DS_JUSTIFICATIVA&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUN_GESTOR', 'string', 'true', '', '6', '<FIELD attrname="CO_MUN_GESTOR" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;CO_MUN_GESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_GESTOR', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="IND_GESTOR" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;IND_GESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES075&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES076": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES076&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES076&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES076&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN_ATENDIDO', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN_ATENDIDO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES076&quot;.&quot;COD_MUN_ATENDIDO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES076&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES076&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES077": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES', 'string', 'true', '', '7', '<FIELD attrname="CNES" fieldtype="string" required="true" WIDTH="7"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;CNES&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES077&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES078": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES078&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES', 'string', 'true', '', '7', '<FIELD attrname="CNES" fieldtype="string" required="true" WIDTH="7"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES078&quot;.&quot;CNES&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME_FANTA', 'string', 'true', '', '60', '<FIELD attrname="NOME_FANTA" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES078&quot;.&quot;NOME_FANTA&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', 'true', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES078&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES078&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES078&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES079": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_ORGPARCEIRA', 'string', 'true', '', '5', '<FIELD attrname="COD_ORGPARCEIRA" fieldtype="string" required="true" WIDTH="5"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;COD_ORGPARCEIRA&quot;" Roundtrip="True"/></FIELD>'),
            ('NOME', 'string', 'true', '', '60', '<FIELD attrname="NOME" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;NOME&quot;" Roundtrip="True"/></FIELD>'),
            ('CNPJ', 'string', '', '', '14', '<FIELD attrname="CNPJ" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;CNPJ&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES', 'string', '', '', '7', '<FIELD attrname="CNES" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;CNES&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_TP_LOGR', 'string', '', '', '3', '<FIELD attrname="CD_TP_LOGR" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;CD_TP_LOGR&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', 'true', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '10', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENTO', 'string', '', '', '60', '<FIELD attrname="COMPLEMENTO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;COMPLEMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRO', 'string', '', '', '60', '<FIELD attrname="BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CEP', 'string', 'true', '', '8', '<FIELD attrname="COD_CEP" fieldtype="string" required="true" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;COD_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', 'true', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('DDD_TEL', 'string', '', '', '3', '<FIELD attrname="DDD_TEL" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;DDD_TEL&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('DDD_FAX', 'string', '', '', '3', '<FIELD attrname="DDD_FAX" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;DDD_FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('FAX', 'string', '', '', '40', '<FIELD attrname="FAX" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_URL', 'string', '', '', '60', '<FIELD attrname="NO_URL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;NO_URL&quot;" Roundtrip="True"/></FIELD>'),
            ('E_MAIL', 'string', '', '', '60', '<FIELD attrname="E_MAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;E_MAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES079&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES080": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_BASE', 'string', 'true', '', '5', '<FIELD attrname="SEQ_BASE" fieldtype="string" required="true" WIDTH="5"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;SEQ_BASE&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_BASE', 'string', 'true', '', '60', '<FIELD attrname="DS_BASE" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;DS_BASE&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_SUBTIPO', 'string', 'true', '', '3', '<FIELD attrname="CD_SUBTIPO" fieldtype="string" required="true" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;CD_SUBTIPO&quot;" Roundtrip="True"/></FIELD>'),
            ('CD_TP_LOGR', 'string', '', '', '3', '<FIELD attrname="CD_TP_LOGR" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;CD_TP_LOGR&quot;" Roundtrip="True"/></FIELD>'),
            ('LOGRADOURO', 'string', 'true', '', '60', '<FIELD attrname="LOGRADOURO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NUMERO', 'string', '', '', '10', '<FIELD attrname="NUMERO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;NUMERO&quot;" Roundtrip="True"/></FIELD>'),
            ('COMPLEMENTO', 'string', '', '', '60', '<FIELD attrname="COMPLEMENTO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;COMPLEMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('BAIRRO', 'string', '', '', '60', '<FIELD attrname="BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CEP', 'string', 'true', '', '8', '<FIELD attrname="COD_CEP" fieldtype="string" required="true" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;COD_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_MUN', 'string', 'true', '', '7', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('DDD_TEL', 'string', '', '', '3', '<FIELD attrname="DDD_TEL" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;DDD_TEL&quot;" Roundtrip="True"/></FIELD>'),
            ('TELEFONE', 'string', '', '', '40', '<FIELD attrname="TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('DDD_FAX', 'string', '', '', '3', '<FIELD attrname="DDD_FAX" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;DDD_FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('FAX', 'string', '', '', '40', '<FIELD attrname="FAX" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;FAX&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_URL', 'string', '', '', '60', '<FIELD attrname="NO_URL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;NO_URL&quot;" Roundtrip="True"/></FIELD>'),
            ('E_MAIL', 'string', '', '', '60', '<FIELD attrname="E_MAIL" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;E_MAIL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATIV', 'date', 'true', '', '', '<FIELD attrname="DATA_ATIV" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;DATA_ATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_DESATIV', 'date', '', '', '', '<FIELD attrname="DATA_DESATIV" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;DATA_DESATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES080&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES081": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID_CENTRAL', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID_CENTRAL" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;UNIDADE_ID_CENTRAL&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_BASE_CENTRAL', 'string', 'true', '', '5', '<FIELD attrname="SEQ_BASE_CENTRAL" fieldtype="string" required="true" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;SEQ_BASE_CENTRAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PLACA', 'string', '', '', '7', '<FIELD attrname="CO_PLACA" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;CO_PLACA&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CHASSI', 'string', '', '', '30', '<FIELD attrname="NU_CHASSI" fieldtype="string" WIDTH="30"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;NU_CHASSI&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PREFIXO_AERONAVE', 'string', '', '', '10', '<FIELD attrname="CO_PREFIXO_AERONAVE" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;CO_PREFIXO_AERONAVE&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_EMBARCA_MARINHA', 'string', '', '', '10', '<FIELD attrname="NU_EMBARCA_MARINHA" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;NU_EMBARCA_MARINHA&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATIV', 'date', 'true', '', '', '<FIELD attrname="DATA_ATIV" fieldtype="date" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;DATA_ATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_DESATIV', 'date', '', '', '', '<FIELD attrname="DATA_DESATIV" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;DATA_DESATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_DESATIV', 'string', '', '', '3', '<FIELD attrname="CO_DESATIV" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;CO_DESATIV&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES081&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES082": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('SQ_ACOLHIMENTO', 'i4', 'true', '', '', '<FIELD attrname="SQ_ACOLHIMENTO" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;SQ_ACOLHIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_ACOLHIMENTO', 'string', 'true', '', '60', '<FIELD attrname="NO_ACOLHIMENTO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NO_ACOLHIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_ACOLHIMENTO', 'string', 'true', '', '10', '<FIELD attrname="NU_ACOLHIMENTO" fieldtype="string" required="true" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NU_ACOLHIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_ACOLHIMENTO', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_ACOLHIMENTO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;TP_ACOLHIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_LOGRADOURO', 'string', '', '', '60', '<FIELD attrname="NO_LOGRADOURO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NO_LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_COMPLEMENTO', 'string', '', '', '60', '<FIELD attrname="DS_COMPLEMENTO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;DS_COMPLEMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_LOGRADOURO', 'string', '', '', '10', '<FIELD attrname="NU_LOGRADOURO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NU_LOGRADOURO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_BAIRRO', 'string', '', '', '60', '<FIELD attrname="NO_BAIRRO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NO_BAIRRO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUNICIPIO', 'string', '', '', '6', '<FIELD attrname="CO_MUNICIPIO" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;CO_MUNICIPIO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CEP', 'string', '', '', '8', '<FIELD attrname="CO_CEP" fieldtype="string" WIDTH="8"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;CO_CEP&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_DDD', 'string', '', '', '3', '<FIELD attrname="CO_DDD" fieldtype="string" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;CO_DDD&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_TELEFONE', 'string', '', '', '40', '<FIELD attrname="NU_TELEFONE" fieldtype="string" WIDTH="40"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NU_TELEFONE&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_ESTRUTURA', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_ESTRUTURA" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;TP_ESTRUTURA&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_PARCERIA_ONG', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_PARCERIA_ONG" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;ST_PARCERIA_ONG&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CNPJ_ONG', 'string', '', '', '14', '<FIELD attrname="NU_CNPJ_ONG" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NU_CNPJ_ONG&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_VAGAS', 'i4', '', '', '', '<FIELD attrname="NU_VAGAS" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;NU_VAGAS&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_ATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;DT_ATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_DESATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;DT_DESATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PROFISSIONAL_SUS', 'string', 'true', '', '16', '<FIELD attrname="CO_PROFISSIONAL_SUS" fieldtype="string" required="true" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;CO_PROFISSIONAL_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CBO', 'string', 'true', '', '6', '<FIELD attrname="CO_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;CO_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINCULACAO', 'string', 'true', '', '6', '<FIELD attrname="IND_VINCULACAO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;IND_VINCULACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_REFERENCIA', 'string', '', '', '7', '<FIELD attrname="CO_CNES_REFERENCIA" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;CO_CNES_REFERENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_UNIDADE_REGIONAL', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_UNIDADE_REGIONAL" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;ST_UNIDADE_REGIONAL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES082&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES083": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES083&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('SQ_ACOLHIMENTO', 'i4', 'true', '', '', '<FIELD attrname="SQ_ACOLHIMENTO" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES083&quot;.&quot;SQ_ACOLHIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUNICIPIO', 'string', 'true', '', '6', '<FIELD attrname="CO_MUNICIPIO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES083&quot;.&quot;CO_MUNICIPIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES083&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES083&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES084": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_ESTRUTURA', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_ESTRUTURA" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;TP_ESTRUTURA&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_PARCERIA_ONG', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_PARCERIA_ONG" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;ST_PARCERIA_ONG&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CNPJ_ONG', 'string', '', '', '14', '<FIELD attrname="NU_CNPJ_ONG" fieldtype="string" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;NU_CNPJ_ONG&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_VAGAS_ACOL_NOTUR', 'i4', '', '', '', '<FIELD attrname="NU_VAGAS_ACOL_NOTUR" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;NU_VAGAS_ACOL_NOTUR&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PROFISSIONAL_SUS', 'string', 'true', '', '16', '<FIELD attrname="CO_PROFISSIONAL_SUS" fieldtype="string" required="true" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;CO_PROFISSIONAL_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CBO', 'string', 'true', '', '6', '<FIELD attrname="CO_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;CO_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINCULACAO', 'string', 'true', '', '6', '<FIELD attrname="IND_VINCULACAO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;IND_VINCULACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_REFERENCIA', 'string', '', '', '7', '<FIELD attrname="CO_CNES_REFERENCIA" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;CO_CNES_REFERENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_UNIDADE_REGIONAL', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_UNIDADE_REGIONAL" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;ST_UNIDADE_REGIONAL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES084&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES085": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES085&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUNICIPIO', 'string', 'true', '', '6', '<FIELD attrname="CO_MUNICIPIO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES085&quot;.&quot;CO_MUNICIPIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES085&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES085&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES086": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_MODULO', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_MODULO" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;TP_MODULO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_VAGAS_EXISTENTES', 'i4', '', '', '', '<FIELD attrname="NU_VAGAS_EXISTENTES" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;NU_VAGAS_EXISTENTES&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_VAGAS_SUS', 'i4', '', '', '', '<FIELD attrname="NU_VAGAS_SUS" fieldtype="i4"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;NU_VAGAS_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_ATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_ATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;DT_ATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_DESATIVACAO', 'date', '', '', '', '<FIELD attrname="DT_DESATIVACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;DT_DESATIVACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PROFISSIONAL_SUS', 'string', 'true', '', '16', '<FIELD attrname="CO_PROFISSIONAL_SUS" fieldtype="string" required="true" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_PROFISSIONAL_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CBO', 'string', 'true', '', '6', '<FIELD attrname="CO_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINCULACAO', 'string', 'true', '', '6', '<FIELD attrname="IND_VINCULACAO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;IND_VINCULACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_CAPS_REF', 'string', '', '', '7', '<FIELD attrname="CO_CNES_CAPS_REF" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_CNES_CAPS_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PROF_SUS_CAPS_REF', 'string', '', '', '16', '<FIELD attrname="CO_PROF_SUS_CAPS_REF" fieldtype="string" WIDTH="16"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_PROF_SUS_CAPS_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CBO_CAPS_REF', 'string', '', '', '6', '<FIELD attrname="CO_CBO_CAPS_REF" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_CBO_CAPS_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS_CAPS_REF', 'string', '', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS_CAPS_REF" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;TP_SUS_NAO_SUS_CAPS_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINCULACAO_CAPS_REF', 'string', '', '', '6', '<FIELD attrname="IND_VINCULACAO_CAPS_REF" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;IND_VINCULACAO_CAPS_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_UNID_BASICA_REF', 'string', '', '', '7', '<FIELD attrname="CO_CNES_UNID_BASICA_REF" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_CNES_UNID_BASICA_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CNES_HOSP_GERAL_REF', 'string', '', '', '7', '<FIELD attrname="CO_CNES_HOSP_GERAL_REF" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;CO_CNES_HOSP_GERAL_REF&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_UNIDADE_REGIONAL', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_UNIDADE_REGIONAL" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;ST_UNIDADE_REGIONAL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES086&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES087": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES087&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_MUNICIPIO', 'string', 'true', '', '6', '<FIELD attrname="CO_MUNICIPIO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES087&quot;.&quot;CO_MUNICIPIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES087&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES087&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES091": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_AVALIACAO', 'string', 'true', '', '2', '<FIELD attrname="CO_AVALIACAO" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;CO_AVALIACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CLASSIFICACAO', 'string', '', '', '2', '<FIELD attrname="CO_CLASSIFICACAO" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;CO_CLASSIFICACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_AVALIACAO', 'date', 'true', '', '', '<FIELD attrname="DT_AVALIACAO" fieldtype="date" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;DT_AVALIACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_AVALIACAO_FINAL', 'date', '', '', '', '<FIELD attrname="DT_AVALIACAO_FINAL" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;DT_AVALIACAO_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_INST_AVALIADORA', 'string', '', '', '2', '<FIELD attrname="CO_INST_AVALIADORA" fieldtype="string" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;CO_INST_AVALIADORA&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES091&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES092": [
        [
            ('NU_CNPJ_ADM', 'string', 'true', '', '14', '<FIELD attrname="NU_CNPJ_ADM" fieldtype="string" required="true" WIDTH="14"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES092&quot;.&quot;NU_CNPJ_ADM&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES092&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_VIGENCIA_INICIAL', 'date', 'true', '', '', '<FIELD attrname="DT_VIGENCIA_INICIAL" fieldtype="date" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES092&quot;.&quot;DT_VIGENCIA_INICIAL&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_VIGENCIA_FINAL', 'date', '', '', '', '<FIELD attrname="DT_VIGENCIA_FINAL" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES092&quot;.&quot;DT_VIGENCIA_FINAL&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES092&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES092&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES095": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_ENDCOMPL', 'string', 'true', '', '5', '<FIELD attrname="COD_ENDCOMPL" fieldtype="string" required="true" WIDTH="5"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;COD_ENDCOMPL&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES095&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES096": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_EMBARCACAO', 'string', 'true', '', '3', '<FIELD attrname="NU_EMBARCACAO" fieldtype="string" required="true" WIDTH="3"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;NU_EMBARCACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_EMBARCACAO', 'string', '', '', '60', '<FIELD attrname="NO_EMBARCACAO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;NO_EMBARCACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_COMUN_ATENDIDA', 'string', '', '', '60', '<FIELD attrname="DS_COMUN_ATENDIDA" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;DS_COMUN_ATENDIDA&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_VEICULO', 'string', '', '', '1', '<FIELD attrname="TP_VEICULO" fieldtype="string" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;TP_VEICULO&quot;" Roundtrip="True"/></FIELD>'),
            ('NO_REGISTRO_VEICULO', 'string', '', '', '10', '<FIELD attrname="NO_REGISTRO_VEICULO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;LFCES096&quot;.&quot;NO_REGISTRO_VEICULO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES097": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('PROF_ID', 'string', 'true', '', '16', '<FIELD attrname="PROF_ID" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;PROF_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_CBO', 'string', 'true', '', '6', '<FIELD attrname="COD_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;COD_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINC', 'string', 'true', '', '6', '<FIELD attrname="IND_VINC" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;IND_VINC&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_SEQ_SOLICITA', 'i4', 'true', '', '', '<FIELD attrname="NU_SEQ_SOLICITA" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;NU_SEQ_SOLICITA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_JUSTIFICATIVA', 'date', 'true', '', '', '<FIELD attrname="DT_JUSTIFICATIVA" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;DT_JUSTIFICATIVA&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_JUSTIFICATIVA', 'string', 'true', '', '256', '<FIELD attrname="DS_JUSTIFICATIVA" fieldtype="string" required="true" WIDTH="256"><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;DS_JUSTIFICATIVA&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES097&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES098": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES098&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_DIA_SEMANA', 'i4', 'true', '', '', '<FIELD attrname="CO_DIA_SEMANA" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES098&quot;.&quot;CO_DIA_SEMANA&quot;" Roundtrip="True"/></FIELD>'),
            ('HR_INICIO_ATENDIMENTO', 'string', 'true', '', '5', '<FIELD attrname="HR_INICIO_ATENDIMENTO" fieldtype="string" required="true" WIDTH="5"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES098&quot;.&quot;HR_INICIO_ATENDIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('HR_FIM_ATENDIMENTO', 'string', 'true', '', '5', '<FIELD attrname="HR_FIM_ATENDIMENTO" fieldtype="string" required="true" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES098&quot;.&quot;HR_FIM_ATENDIMENTO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES098&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES098&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES099": [
        [
            ('NU_CNPJ_ADM', 'string', 'true', '', '14', '<FIELD attrname="NU_CNPJ_ADM" fieldtype="string" required="true" WIDTH="14"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES099&quot;.&quot;NU_CNPJ_ADM&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_BANCO', 'string', 'true', '', '3', '<FIELD attrname="CO_BANCO" fieldtype="string" required="true" WIDTH="3"><PARAM Name="ORIGIN" Value="&quot;LFCES099&quot;.&quot;CO_BANCO&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_AGENCIA', 'string', 'true', '', '5', '<FIELD attrname="NU_AGENCIA" fieldtype="string" required="true" WIDTH="5"><PARAM Name="ORIGIN" Value="&quot;LFCES099&quot;.&quot;NU_AGENCIA&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_CONTA_CORRENTE', 'string', 'true', '', '14', '<FIELD attrname="NU_CONTA_CORRENTE" fieldtype="string" required="true" WIDTH="14"><PARAM Name="ORIGIN" Value="&quot;LFCES099&quot;.&quot;NU_CONTA_CORRENTE&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES099&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES099&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES101": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_COMIS', 'string', 'true', '', '2', '<FIELD attrname="COD_COMIS" fieldtype="string" required="true" WIDTH="2"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;COD_COMIS&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_PROFISSIONAL_SUS', 'string', 'true', '', '16', '<FIELD attrname="CO_PROFISSIONAL_SUS" fieldtype="string" required="true" WIDTH="16"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;CO_PROFISSIONAL_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_CBO', 'string', 'true', '', '6', '<FIELD attrname="CO_CBO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;CO_CBO&quot;" Roundtrip="True"/></FIELD>'),
            ('TP_SUS_NAO_SUS', 'string', 'true', 'FixedChar', '1', '<FIELD attrname="TP_SUS_NAO_SUS" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;TP_SUS_NAO_SUS&quot;" Roundtrip="True"/></FIELD>'),
            ('IND_VINCULACAO', 'string', 'true', '', '6', '<FIELD attrname="IND_VINCULACAO" fieldtype="string" required="true" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;IND_VINCULACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_RESP_TECNICO', 'string', 'true', '', '1', '<FIELD attrname="ST_RESP_TECNICO" fieldtype="string" required="true" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;ST_RESP_TECNICO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES101&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES102": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES102&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_ATIVIDADE_SECUNDARIA', 'string', 'true', '', '3', '<FIELD attrname="CO_ATIVIDADE_SECUNDARIA" fieldtype="string" required="true" WIDTH="3"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES102&quot;.&quot;CO_ATIVIDADE_SECUNDARIA&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES102&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES102&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES103": [
        [
            ('COD_MUN', 'string', 'true', '', '6', '<FIELD attrname="COD_MUN" fieldtype="string" required="true" WIDTH="6"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;COD_MUN&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_AREA', 'string', 'true', '', '4', '<FIELD attrname="COD_AREA" fieldtype="string" required="true" WIDTH="4"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;COD_AREA&quot;" Roundtrip="True"/></FIELD>'),
            ('SEQ_EQUIPE', 'i4', 'true', '', '', '<FIELD attrname="SEQ_EQUIPE" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;SEQ_EQUIPE&quot;" Roundtrip="True"/></FIELD>'),
            ('CO_ALDEIA', 'i4', 'true', '', '', '<FIELD attrname="CO_ALDEIA" fieldtype="i4" required="true"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;CO_ALDEIA&quot;" Roundtrip="True"/></FIELD>'),
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', 'true', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date" required="true"><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES103&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "LFCES105": [
        [
            ('UNIDADE_ID', 'string', 'true', '', '31', '<FIELD attrname="UNIDADE_ID" fieldtype="string" required="true" WIDTH="31"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;UNIDADE_ID&quot;" Roundtrip="True"/></FIELD>'),
            ('DS_SERIE', 'string', 'true', '', '60', '<FIELD attrname="DS_SERIE" fieldtype="string" required="true" WIDTH="60"><PARAM Name="PROVFLAGS" Value="7" Type="i4" Roundtrip="True"/><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;DS_SERIE&quot;" Roundtrip="True"/></FIELD>'),
            ('CODTPEQUIP', 'string', 'true', 'FixedChar', '2', '<FIELD attrname="CODTPEQUIP" fieldtype="string" required="true" SUBTYPE="FixedChar" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;CODTPEQUIP&quot;" Roundtrip="True"/></FIELD>'),
            ('COD_EQUIP', 'string', 'true', '', '2', '<FIELD attrname="COD_EQUIP" fieldtype="string" required="true" WIDTH="2"><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;COD_EQUIP&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_INSTALACAO', 'date', '', '', '', '<FIELD attrname="DT_INSTALACAO" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;DT_INSTALACAO&quot;" Roundtrip="True"/></FIELD>'),
            ('ST_FINANCIADO_MS', 'string', '', 'FixedChar', '1', '<FIELD attrname="ST_FINANCIADO_MS" fieldtype="string" SUBTYPE="FixedChar" WIDTH="1"><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;ST_FINANCIADO_MS&quot;" Roundtrip="True"/></FIELD>'),
            ('DATA_ATU', 'date', '', '', '', '<FIELD attrname="DATA_ATU" fieldtype="date"><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;DATA_ATU&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', 'true', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" required="true" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;LFCES105&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
    "TFCES002": [
        [
            ('COD_MUN_GESTOR', 'string', '', '', '7', '<FIELD attrname="COD_MUN_GESTOR" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;TFCES002&quot;.&quot;COD_MUN_GESTOR&quot;" Roundtrip="True"/></FIELD>'),
            ('CNES_CONSULTA', 'string', '', '', '7', '<FIELD attrname="CNES_CONSULTA" fieldtype="string" WIDTH="7"><PARAM Name="ORIGIN" Value="&quot;TFCES002&quot;.&quot;CNES_CONSULTA&quot;" Roundtrip="True"/></FIELD>'),
            ('COMP_CONSULTA', 'string', '', '', '6', '<FIELD attrname="COMP_CONSULTA" fieldtype="string" WIDTH="6"><PARAM Name="ORIGIN" Value="&quot;TFCES002&quot;.&quot;COMP_CONSULTA&quot;" Roundtrip="True"/></FIELD>'),
            ('DT_HR_CONSULTA', 'dateTime', '', '', '', '<FIELD attrname="DT_HR_CONSULTA" fieldtype="dateTime"><PARAM Name="ORIGIN" Value="&quot;TFCES002&quot;.&quot;DT_HR_CONSULTA&quot;" Roundtrip="True"/></FIELD>'),
            ('NU_VERSAO', 'string', '', '', '10', '<FIELD attrname="NU_VERSAO" fieldtype="string" WIDTH="10"><PARAM Name="ORIGIN" Value="&quot;TFCES002&quot;.&quot;NU_VERSAO&quot;" Roundtrip="True"/></FIELD>'),
            ('USUARIO', 'string', '', '', '60', '<FIELD attrname="USUARIO" fieldtype="string" WIDTH="60"><PARAM Name="ORIGIN" Value="&quot;TFCES002&quot;.&quot;USUARIO&quot;" Roundtrip="True"/></FIELD>'),
        ],
    ],
}

# LFCES021 (vínculos de profissionais): na exportação real do SCNES a tabela é
# LFCES021 (arquivo lfces021.xml), com o mesmo schema do "pack 1" do LFCES004.
SCHEMAS["LFCES021"] = [SCHEMAS["LFCES004"][1]]

METADATA_PARAMS = {
    "CFCES000": ['<PARAMS/>'],
    "LFCES000": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES002": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES004": ['<PARAMS PRIMARY_KEY="1"/>', '<PARAMS PRIMARY_KEY="2 3 4 5 6"/>'],
    "LFCES021": ['<PARAMS PRIMARY_KEY="2 3 4 5 6"/>'],
    "LFCES005": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES006": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES007": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES008": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES009": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES012": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES013": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES014": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES015": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES018": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES019": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES020": ['<PARAMS PRIMARY_KEY="1 2 6"/>'],
    "LFCES023": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES027": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES032": ['<PARAMS PRIMARY_KEY="1 2 3 4 5 6"/>'],
    "LFCES034": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES035": ['<PARAMS/>'],
    "LFCES037": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES038": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES039": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES040": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES041": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES043": ['<PARAMS PRIMARY_KEY="1 2 3 4 5 6"/>'],
    "LFCES044": ['<PARAMS PRIMARY_KEY="1 2 3 4 5"/>'],
    "LFCES045": ['<PARAMS/>'],
    "LFCES046": ['<PARAMS/>'],
    "LFCES047": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES051": ['<PARAMS/>'],
    "LFCES052": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES053": ['<PARAMS/>'],
    "LFCES055": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES056": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES058": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES059": ['<PARAMS PRIMARY_KEY="1 2 3 4 5 6"/>'],
    "LFCES065": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES072": ['<PARAMS/>'],
    "LFCES073": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES074": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES075": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES076": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES077": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES078": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES079": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES080": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES081": ['<PARAMS PRIMARY_KEY="1 8"/>'],
    "LFCES082": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES083": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES084": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES085": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES086": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES087": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES091": ['<PARAMS PRIMARY_KEY="1 2 4"/>'],
    "LFCES092": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES095": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES096": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES097": ['<PARAMS PRIMARY_KEY="1 2 3 4 5 6"/>'],
    "LFCES098": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES099": ['<PARAMS PRIMARY_KEY="1"/>'],
    "LFCES101": ['<PARAMS PRIMARY_KEY="1 2 3"/>'],
    "LFCES102": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "LFCES103": ['<PARAMS PRIMARY_KEY="1 2 3 4"/>'],
    "LFCES105": ['<PARAMS PRIMARY_KEY="1 2"/>'],
    "TFCES002": ['<PARAMS/>'],
}

ORDEM = ["CFCES000","TFCES002","LFCES000","LFCES002","LFCES004","LFCES005","LFCES006",
         "LFCES007","LFCES008","LFCES009","LFCES012","LFCES013","LFCES014","LFCES015",
         "LFCES018","LFCES019","LFCES020","LFCES021","LFCES023","LFCES027","LFCES032",
         "LFCES034","LFCES035","LFCES037","LFCES038","LFCES039","LFCES040","LFCES041",
         "LFCES043","LFCES044","LFCES045","LFCES046","LFCES047","LFCES051","LFCES052",
         "LFCES053","LFCES055","LFCES056","LFCES058","LFCES059","LFCES065","LFCES072",
         "LFCES073","LFCES074","LFCES075","LFCES076","LFCES077","LFCES078","LFCES079",
         "LFCES080","LFCES081","LFCES082","LFCES083","LFCES084","LFCES085","LFCES086",
         "LFCES087","LFCES091","LFCES092","LFCES095","LFCES096","LFCES097","LFCES098",
         "LFCES099","LFCES101","LFCES102","LFCES103","LFCES105"]

# ── Helpers de normalização ──
def _dig(v):    return re.sub(r"\D", "", str(v or ""))
def _num(v, d=""):
    s = re.sub(r"\D", "", str(v or ""))
    return s or d
def _up(v):     return str(v or "").strip().upper()
def _hoje():    return datetime.now().strftime("%Y%m%d")
def _ts():      return int(_time.time())

def _data(v):
    """DD/MM/AAAA ou AAAA-MM-DD ou AAAAMMDD -> AAAAMMDD (formato SCNES)."""
    s = str(v or "").strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}{m.group(2)}{m.group(1)}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    if re.fullmatch(r"\d{8}", s):
        return s
    return ""

def _linha(tabela, pack_idx=0, **valores):
    """Linha da tabela com apenas os campos preenchidos (o SCNES omite campos
    nulos — campos vazios não viram atributos no XML)."""
    return dict(valores)

def _checksum(texto: str) -> str:
    return str(zlib.crc32(texto.encode("latin-1", "replace")) % 10_000_000_000).zfill(10)

def _checksum_hex(texto: str) -> str:
    return "%08X" % (zlib.crc32(texto.encode("latin-1", "replace")) & 0xFFFFFFFF)

# ── Tabelas auxiliares de mapeamento (códigos CNES) ──
CONSELHOS = {
    "CRM":"15","COREN":"66","CRO":"71","CRF":"69","CREFITO":"70","CRP":"77",
    "CRN":"75","CRESS":"25","CREFONO":"29","CRBM":"32","CRBIO":"33","CREF":"78",
}
REJEITO_CODES = {"Resíduos Biológicos":"01","Resíduos Químicos":"02",
                 "Rejeitos Radioativos":"03","Resíduos Comuns":"04","Nenhum":""}
TURNO_CODES = {"MANHÃ":"01","TARDE":"02","MANHÃ E TARDE":"03","24 HORAS":"04"}
COD_LEITO = {
    "leitos_cirurgicos":"40","leitos_obstetricos":"40","leitos_pediatricos":"40",
    "leitos_clinicos":"40","leitos_outras":"40",
    "leitos_hospital_dia":"41","leitos_complementares":"42",
}
# Ficha 6 → LFCES015: (COD_INSTAL, campo_salas, campo_leitos)
COD_INSTAL = {
    "f6_ue_med":            ("01", "f6_ue_med", None),
    "f6_ue_odonto":         ("02", "f6_ue_odonto", None),
    "f6_triagem_ped":       ("12", "f6_triagem_ped", None),
    "f6_triagem_fem":       ("13", "f6_triagem_fem", None),
    "f6_triagem_masc":      ("14", "f6_triagem_masc", None),
    "f6_triagem_indf":      ("15", "f6_triagem_indf", None),
    "f6_ue_curativo":       ("09", "f6_ue_curativo", None),
    "f6_ue_gesso":          ("08", "f6_ue_gesso", None),
    "f6_higienizacao":      ("20", "f6_higienizacao", None),
    "f6_ue_peq_cir":        ("10", "f6_ue_peq_cir", None),
    "f6_repouso_ped":       ("16", "f6_repouso_ped_salas", "f6_repouso_ped_leitos"),
    "f6_repouso_fem":       ("17", "f6_repouso_fem_salas", "f6_repouso_fem_leitos"),
    "f6_repouso_masc":      ("18", "f6_repouso_masc_salas", "f6_repouso_masc_leitos"),
    "f6_repouso_indf":      ("19", "f6_repouso_indf_salas", "f6_repouso_indf_leitos"),
    "f6_amb_basicas":       ("24", "f6_amb_basicas", None),
    "f6_amb_especializadas":("25", "f6_amb_especializadas", None),
    "f6_amb_indf":          ("26", "f6_amb_indf", None),
    "f6_outros_nmed":       ("27", "f6_outros_nmed", None),
    "f6_odonto_amb":        ("28", "f6_odonto_amb", None),
    "f6_peq_cirurgia_amb":  ("29", "f6_peq_cirurgia_amb", None),
    "f6_enfermagem":        ("05", "f6_enfermagem", None),
    "f6_imunizacao":        ("06", "f6_imunizacao", None),
    "f6_nebulizacao":       ("07", "f6_nebulizacao", None),
    "f6_gesso_amb":         ("33", "f6_gesso_amb", None),
    "f6_curativo_amb":      ("34", "f6_curativo_amb", None),
    "f6_cirurgia_amb":      ("35", "f6_cirurgia_amb", None),
    "f6_cirurgia":          ("31", "f6_cirurgia", None),
    "f6_recuperacao":       ("32", "f6_recuperacao", "f6_recuperacao_leitos"),
    "f6_cirurgia_amb_cc":   ("11", "f6_cirurgia_amb_cc", None),
    "f6_preparto":          ("36", "f6_preparto_qtd", "f6_preparto_leitos"),
    "f6_parto_normal":      ("37", "f6_parto_normal", None),
    "f6_curetagem":         ("38", "f6_curetagem", None),
    "f6_cirurgia_co":       ("39", "f6_cirurgia_co", None),
    "f6_leitos_rn_normal":  ("40", "f6_leitos_rn_normal", None),
    "f6_leitos_rn_patologico": ("41", "f6_leitos_rn_patologico", None),
    "f6_leitos_alojamento": ("42", "f6_leitos_alojamento", None),
}

def _xml(v):
    if v is None:
        return ""
    s = str(v)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("'", "&apos;")
    return "".join(ch if ord(ch) < 256 else "?" for ch in s)

def datapacket_xml(tabela: str, linhas: list, pack_idx: int = 0) -> bytes:
    """Monta um DATAPACKET válido (Delphi TClientDataSet) para a tabela."""
    fields = SCHEMAS[tabela][pack_idx]
    # METADATA reproduzido verbatim do original (campos com PARAMs PROVFLAGS/ORIGIN)
    params = METADATA_PARAMS.get(tabela, ["<PARAMS/>"])[pack_idx]
    meta = (f'<DATAPACKET ><METADATA><FIELDS>{"".join(f[5] for f in fields)}</FIELDS>'
            f'{params}</METADATA><ROWDATA>')
    rows = []
    for linha in linhas:
        # escreve apenas os campos presentes na linha (o SCNES omite campos NULL)
        attrs = "".join(f' {nome}="{_xml(linha[nome])}"' for nome, _, _, _, _, _ in fields
                         if nome in linha)
        rows.append(f"<ROW{attrs}/>")
    body = ('<?xml version="1.0" encoding="ISO-8859-1"?>' + " " * 10 +
            meta + "".join(rows) + "</ROWDATA></DATAPACKET>")
    return body.encode("latin-1", "replace")

def _ind_vinculo(estab, empregador):
    """'01 - VÍNCULO EMPREGATÍCIO' + '05 - CELETISTA' -> '010500' (padrão SCNES)."""
    try:
        tipo = int(_dig(estab)[:2])
        sub  = int(_dig(empregador)[:2]) if empregador else 0
        return f"{tipo:02d}{sub:02d}00"
    except Exception:
        return "010500"

def montar_tabelas(d):
    """Converte os dados do formulário JARVIS nas 68 tabelas do SCNES."""
    cnes = _num(d.get("f1_cnes"))
    unidade_id = COD_MUN_GESTOR + cnes
    hoje = _hoje()
    op = str(d.get("f1_operacao") or "")
    statusmov = "4" if "exclu" in op.lower() else "2"
    base = {"UNIDADE_ID": unidade_id, "STATUS": "1", "STATUSMOV": statusmov,
            "DATA_ATU": hoje, "USUARIO": USUARIO}

    t = {nome: [] for nome in ORDEM}
    t["_LFCES004_ESTAB"] = []
    t["_LFCES021_VINC"] = []

    # CFCES000 — versão do sistema
    t["CFCES000"] = [_linha("CFCES000",
        VERSAO=VERSAO, VERSAO_ANT="4.8.30", DT_VERSAO="", DT_ULTIMA_ATU_SIST="",
        FL_LEU_MSG_VERSAO="S", DT_ULTIMO_INFORME="", FL_EXIGIR_CONSISTENCIA="N",
        FL_SCNES_SIMPLIFICADO="N")]

    # SEM salvaguarda de CNES: o cadastro serve para gerar a numeração CNES
    # de estabelecimentos novos, então o .BCK é montado sempre (CNES vazio
    # quando ainda não atribuído).
    cpf = _num(d.get("f1_cnpj"))
    cnpj = cpf if len(cpf) == 14 else ""
    cpf = cpf if len(cpf) == 11 else ""

    # LFCES000 — registro da estação (1 linha mínima)
    t["LFCES000"] = [_linha("LFCES000",
        NU_MAC="", SIGLA_EST=UF, COD_MUN=COD_MUN_GESTOR, REGIAO="", DISTRITO="",
        CNPJSIASUS=cnpj, NOMEGESTOR=GESTOR,
        LOGRADOURO=_up(d.get("f1_endereco")), COMPLEMENT=_up(d.get("f1_complemento")),
        NUMERO=str(d.get("f1_numero") or ""), BAIRRO=_up(d.get("f1_bairro")),
        CEP=_num(d.get("f1_cep")), TELEFONE=str(d.get("f1_telefone") or ""),
        FAX="", EMAIL=str(d.get("f1_email") or ""), INDGESTOR="1", INDCADASTR="1",
        INDEXPORTA="0", EMAIL_GEST="", PREFIXOMAQ="", N_MAQUINA="1", INDTIPOCAD="1",
        RESPONSAVEL="", NO_COMPUTADOR="", NO_SIST_OPER="", NU_VERSAO=VERSAO,
        NU_SERV_PACK="", TP_CPU="", TP_CLOCK="", NU_MEMORIA="", NU_HD="", IN_CD="",
        IN_IMPRESSORA="", TP_REDE="", IN_INTERNET="", NO_USU_COMP="", BANCO="",
        NU_ARQ_ATUA_VIAWEB=0, STATUSMOV=statusmov, DATA_ATU=hoje)]

    # LFCES004 (v1) — identificação do estabelecimento
    t["_LFCES004_ESTAB"] = [_linha("LFCES004", 0,
        UNIDADE_ID=unidade_id, CNES=cnes, CNPJ_MANT=cnpj,
        PFPJ_IND="1" if cpf else "3", NIVEL_DEP="1",
        R_SOCIAL=_up(d.get("f1_nome_empresarial")),
        NOME_FANTA=_up(d.get("f1_fantasia")),
        LOGRADOURO=_up(d.get("f1_endereco")),
        NUMERO=str(d.get("f1_numero") or ""),
        COMPLEMENT=_up(d.get("f1_complemento")),
        BAIRRO=_up(d.get("f1_bairro")),
        COD_CEP=_num(d.get("f1_cep")),
        REG_SAUDE="", MICRO_REG="", DIST_SANIT="", DIST_ADMIN="",
        TELEFONE=str(d.get("f1_telefone") or ""),
        FAX="", E_MAIL=str(d.get("f1_email") or ""),
        CPF=cpf, CNPJ=cnpj,
        COD_ATIV="04", COD_CLIENT="01",
        NUM_ALVARA=str(d.get("f1_alvara") or ""),
        DATA_EXPED=_data(d.get("f1_alvara_data")),
        DT_VAL_LIC_SANI="", TP_LIC_SANI="",
        IND_ORGEXP=str(d.get("f1_alvara_orgao") or ""),
        TP_UNID_ID=_num(d.get("f1_tipo_estab")),
        COD_TURNAT=TURNO_CODES.get(_up(d.get("f2_turno")), "03"),
        SIGESTGEST=UF, CODMUNGEST=COD_MUN_GESTOR,
        STATUS="1", STATUSMOV=statusmov, TP_PRESTADOR="",
        DATA_ATU=hoje, USUARIO=USUARIO, NMUSUARIOEMUSO="",
        CPFDIRETORCLINICO="", REGDIRETORCLINICO=str(d.get("f1_conselho_rt") or ""),
        CD_MOTIVO_DESAB="", DT_VALIDACAO="",
        FL_ADESAO_FILANTROP="", CMPT_VIGENTE="",
        NO_URL="", NU_LATITUDE="", NU_LONGITUDE="", DT_ATU_GEO="", NO_USUARIO_GEO="",
        CO_NATUREZA_JUR="", ST_CNESGERADO_TRANSMISSOR="",
        TP_ESTAB_SEMPRE_ABERTO="N", ST_GERACREDITO_GERENTE_SGIF="",
        ST_NAT_JUR_WEBSERVICE="", ST_DADOS_CADONLINE_WEBSERV="",
        ST_CONEXAOINTERNET="", CO_TIPO_ESTABELECIMENTO="",
        CO_ATIVIDADE_PRINCIPAL="", ST_CONTRATO_FORMALIZADO="N",
        CO_TIPO_ABRANGENCIA="", ST_COWORKING="N")]

    # LFCES005 — mantenedora
    t["LFCES005"] = [_linha("LFCES005",
        CNPJ_MANT=cnpj, COD_BANCO="", NUM_AGENC="",
        R_SOCIAL=_up(d.get("f1_nome_empresarial")),
        LOGRADOURO=_up(d.get("f1_endereco")), NUMERO=str(d.get("f1_numero") or ""),
        COMPLEMENT=_up(d.get("f1_complemento")), BAIRRO=_up(d.get("f1_bairro")),
        COD_CEP=_num(d.get("f1_cep")), COD_MUN=COD_MUN_GESTOR, REG="",
        TELEFONE=str(d.get("f1_telefone") or ""), CONTA_CC="",
        ST_FMS_FES="", NU_CNPJ_FMS_FES="", DT_PREENCH=hoje,
        CO_NATUREZA_JUR="", STATUS="1", STATUS_MOV=statusmov,
        DATA_ATU=hoje, USUARIO=USUARIO, NMUSUARIOEMUSO="")]

    # LFCES006 — atendimento prestado ("01 - INTERNAÇÃO" -> "01")
    for a in (d.get("atendimento_prestado") or []):
        cod = _num(a)[:2]
        if cod:
            t["LFCES006"].append(_linha("LFCES006", **base, CODATPREST=cod))

    # LFCES008 — resíduos
    for r in (d.get("residuos") or []):
        cod = REJEITO_CODES.get(str(r).strip())
        if cod:
            t["LFCES008"].append(_linha("LFCES008", **base, CODREJEITO=cod))

    # LFCES015 — instalações físicas (Ficha 6)
    for chave, (cod, campo_s, campo_l) in COD_INSTAL.items():
        if campo_l:
            salas = _num(d.get(campo_s))
            leitos = _num(d.get(campo_l))
            if (salas and salas != "0") or (leitos and leitos != "0"):
                t["LFCES015"].append(_linha("LFCES015", **base,
                    COD_INSTAL=cod, QTDE_INST=salas or "0", NUM_LEITOS=leitos or "0"))
        else:
            v = _num(d.get(campo_s))
            if v and v != "0":
                t["LFCES015"].append(_linha("LFCES015", **base,
                    COD_INSTAL=cod, QTDE_INST=v, NUM_LEITOS="0"))

    # LFCES015 — leitos (Ficha 19: existente/SUS)
    for grp, cod in COD_LEITO.items():
        obj = d.get(grp) or {}
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except Exception:
                obj = {}
        for esp, v in obj.items():
            if not isinstance(v, dict):
                continue
            ex = _num(v.get("existente"))
            sus = _num(v.get("sus"))
            if (ex and ex != "0") or (sus and sus != "0"):
                t["LFCES015"].append(_linha("LFCES015", **base,
                    COD_INSTAL=cod, QTDE_INST=ex or "0", NUM_LEITOS=sus or "0"))

    # LFCES020 — equipamentos (arrays {possui, qtd})
    for chave, lista, ini, tp in [
            ("eq_diag_imagem", EQUIP_DIAG_IMAGEM, 1,  "1"),
            ("eq_infra",       EQUIP_INFRA,       16, "2"),
            ("eq_opticos",     EQUIP_OPTICOS,     19, "3"),
            ("eq_odonto",      EQUIP_ODONTO,      52, "6"),
            ("eq_outros",      EQUIP_OUTROS,      59, "7"),
            ("eq_audio",       EQUIP_AUDIO,       66, "8")]:
        for i, item in enumerate(d.get(chave) or []):
            if not isinstance(item, dict):
                continue
            qtd = _num(item.get("qtd"), "0")
            if item.get("possui") and qtd != "0":
                t["LFCES020"].append(_linha("LFCES020", **base,
                    COD_EQUIP=f"{ini + i:02d}", QTDE_EXIST=qtd, QTDE_USO=qtd,
                    IND_SUS="S", CODTPEQUIP=tp))

    # LFCES020 — métodos gráficos (36-37) e manutenção da vida (38-51)
    for chave, ini, tp in [("metodos", 36, "4"), ("manutencao", 38, "5")]:
        obj = d.get(chave) or {}
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except Exception:
                obj = {}
        for cod, v in obj.items():
            if not isinstance(v, dict):
                continue
            if v.get("simnao") != "sim":
                continue
            try:
                codnum = ini + int(cod) - 1
            except Exception:
                continue
            t["LFCES020"].append(_linha("LFCES020", **base,
                COD_EQUIP=f"{codnum:02d}",
                QTDE_EXIST=_num(v.get("existente"), "0"),
                QTDE_USO=_num(v.get("uso"), "0"),
                IND_SUS="S", CODTPEQUIP=tp))

    # LFCES014 — comissões (Ficha 4)
    for cod, nome in COMISSOES_F4:
        if str(d.get(f"f4_{cod}")) == "Sim":
            t["LFCES014"].append(_linha("LFCES014", **base,
                COD_COMIS=cod, DT_ATIVACAO=hoje, DT_DESATIVACAO=""))

    # LFCES019 — serviços de apoio (Ficha 7)
    apoio = d.get("apoio") or {}
    if isinstance(apoio, str):
        try:
            apoio = json.loads(apoio)
        except Exception:
            apoio = {}
    for i, nome in enumerate(SERVICOS_APOIO, start=1):
        v = apoio.get(str(i))
        if v and v != "Nao":
            t["LFCES019"].append(_linha("LFCES019", **base,
                CODSERVCOM=f"{i:02d}",
                INDSERVCOM="1" if str(v) == "Proprio" else "2",
                CNPJ="", R_SOCIAL="", COD_MUN=""))

    # LFCES009 — especializações / serviços (Ficha 8)
    for esp in (d.get("especializacoes") or []):
        if not isinstance(esp, dict):
            continue
        svc = str(esp.get("servico") or "").strip()
        if svc:
            t["LFCES009"].append(_linha("LFCES009", **base,
                CODSERVICO=svc, COD_CARACT=str(esp.get("classificacao") or "")))

    # LFCES098 — horários de funcionamento
    horarios = []
    m = re.search(r"(\d{1,2}):?(\d{2})?\s*[h:]\s*[–-]\s*(\d{1,2}):?(\d{2})?\s*h?", str(d.get("f2_horas_func") or ""))
    if not m:
        m = re.search(r"(\d{1,2})\s*h\s*[–-]\s*(\d{1,2})\s*h", str(d.get("f2_horas_func") or ""))
        if m:
            ini, fim = f"{int(m.group(1)):02d}:00", f"{int(m.group(2)):02d}:00"
        else:
            ini, fim = "08:00", "17:00"
    else:
        ini = f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
        fim = f"{int(m.group(3)):02d}:{m.group(4) or '00'}"
    for dia in range(2, 7):
        t["LFCES098"].append(_linha("LFCES098", **base,
            CO_DIA_SEMANA=dia, HR_INICIO_ATENDIMENTO=ini, HR_FIM_ATENDIMENTO=fim))

    # LFCES055 — histórico de exportação
    t["LFCES055"] = [_linha("LFCES055",
        COMPETENCIA=CMPT, COD_MUN_GESTOR=COD_MUN_GESTOR, UNIDADE_ID=unidade_id,
        DESTINO="", CNES=cnes, NOME_FANTA=_up(d.get("f1_fantasia")),
        NM_ARQUIVO_EXP="", STATUS="", NU_MAC="", FL_TRANSMISSAO_DIRETA="",
        USUARIO=USUARIO, DATA_ATU=hoje)]

    # LFCES018 — profissionais + LFCES021 — vínculos
    for p in (d.get("profissionais") or []):
        if not isinstance(p, dict):
            continue
        cpf_p = _num(p.get("cpf"))
        if len(cpf_p) != 11:
            continue
        prof_id = "0000000" + cpf_p[:9]
        nome = _up(p.get("nome"))
        cbo = _num(p.get("profissao"))[:6]
        m_cons = re.match(r"([A-Za-z]+)", str(p.get("conselho") or ""))
        conselho_txt = m_cons.group(1).upper() if m_cons else ""
        conselho_id = CONSELHOS.get(conselho_txt, _num(p.get("conselho")))
        vinculo = _ind_vinculo(p.get("estabelecimento"), p.get("empregador"))
        ch = _num(p.get("ch"), "0")
        t["LFCES018"].append(_linha("LFCES018",
            PROF_ID=prof_id, CPF_PROF=cpf_p, PISPASEP="", NOME_PROF=nome,
            NOME_MAE=_up(p.get("mae")), DATA_NASC="",
            COD_MUN=COD_MUN_GESTOR, SEXO=" ",
            NUM_LIVRO="", NUM_FOLHA="", NUM_TERMO="", CODORGEMIS="", DATA_EMISS="",
            NUM_IDENT="", SIGLA_EST="", DTEMIIDENT="", DATA_ENTRA=hoje,
            CTPS_NUMER="", SERIE="", SIGESTCTPS="", DTEMISCTPS="",
            LOGRADOURO=_up(p.get("endereco")), NUMERO=str(p.get("numero") or ""),
            COMPLEMENT="", BAIRRODIST="", COD_CEP="",
            SIGLA_UF=UF, CODESCOLAR="", COD_CERTID="", IND_NACIO="1",
            NOME_CARTO="", COD_BANCO="", NOME_PAIS="BRASIL", NUM_AGENC="",
            CONTA_CC="", COD_CNS="", D_TERCSIH=" ",
            STATUS="1", STATUSMOV=statusmov, DATA_ATU=hoje, USUARIO=USUARIO,
            NMUSUARIOEMUSO="", CD_RACA="", CO_ETNIA="", NOME_PAI="",
            TELEFONE=str(p.get("telefone") or ""), CD_TP_LOGR="", PORTARIA="",
            DT_NATUR="", CD_PAIS="", COD_MUN_RES="", UF_RES="",
            NO_EMAIL=str(p.get("email") or ""), CO_PAIS_RESID="",
            NU_CARTEIRA_HAB="", DT_EMIS_CARTEIRA_HAB="", UF_CARTEIRA_HAB="",
            ST_NMPROF_CADSUS="", ST_CNS_CORRIGIDO="", NO_SOCIAL=""))
        t["_LFCES021_VINC"].append(_linha("LFCES021", 1,
            CNES=cnes, UNIDADE_ID=unidade_id, PROF_ID=prof_id,
            COD_CBO=cbo, TP_SUS_NAO_SUS="S",
            IND_VINC=vinculo, NU_CNPJ_DET_VINC=_num(p.get("cnpj_pj")),
            D_TERCSIH=" ", CGHORAOUTR="0",
            CG_HORAAMB=ch, CGHORAHOSP="0",
            CONSELHOID=str(conselho_id), N_REGISTRO=_num(p.get("conselho")),
            SG_UF_CRM=UF,
            TP_PRECEPTOR="2", TP_RESIDENTE="2",
            STATUS="1", STATUSMOV=statusmov, DATA_ATU=hoje, USUARIO=USUARIO,
            CHECKSUM=_checksum(f"{unidade_id}|{prof_id}|{cbo}|{vinculo}")))

    return t

# ── Geração do pacote .BCK ──
def _nome_arquivo(nome_base, sufixo):
    return (f"c:\\users\\{USUARIO.lower()}\\appdata\\local\\temp\\"
            f"{nome_base}{sufixo}")

def _nome_transmissao(sufixo):
    agora = datetime.now()
    versao_dig = "".join(d for d in VERSAO if d.isdigit())
    return (f"cnes0{UF.lower()}{COD_MUN_GESTOR}{agora:%d%m%Y%H%M%S}"
            f"{agora:%Y}{versao_dig}{sufixo}")

def _nome_bck():
    """Nome do .BCK no padrão de transmissão do SCNES:
    CNES0{UF}{COD_MUN_GESTOR}{DDMMYYYY}{HHMMSS}{YYYY}{versao}.bck
    (ex.: CNES0RO1100201108202612100720264840.bck)."""
    agora = datetime.now()
    versao_dig = "".join(d for d in VERSAO if d.isdigit())
    return (f"CNES0{UF}{COD_MUN_GESTOR}{agora:%d%m%Y%H%M%S}"
            f"{agora:%Y}{versao_dig}.bck")

def txt_base():
    return f"0\r\n0\r\n2\r\n{UF}\r\n{COD_MUN_GESTOR}\r\n{GESTOR}\r\n{VERSAO}\r\nSCNES COMPLETO\r\n"

def gerar_bck_bytes(dados, caminho_qrp=None):
    """Monta o .BCK completo: 68 tabelas + TXT + (opcional) QRP."""
    tabelas = montar_tabelas(dados)
    entradas = []
    ts = _ts()
    for i, tabela in enumerate(ORDEM):
        if tabela == "LFCES004":
            linhas, pack_idx = tabelas.get("_LFCES004_ESTAB", []), 0
        elif tabela == "LFCES021":
            linhas, pack_idx = tabelas.get("_LFCES021_VINC", []), 0
        else:
            linhas, pack_idx = tabelas.get(tabela, []), 0
        entradas.append({"path": _nome_arquivo(tabela.lower(), ".xml"), "ts": ts,
                         "dados": datapacket_xml(tabela, linhas, pack_idx=pack_idx)})
    nome_tx = _nome_transmissao(".txt")
    txt = (f"0\r\n0\r\n2\r\n{UF}\r\n{COD_MUN_GESTOR}\r\n{GESTOR}\r\n{VERSAO}\r\n"
           f"{_checksum_hex(txt_base())}\r\nSCNES COMPLETO\r\n")
    entradas.append({"path": _nome_arquivo(nome_tx, ""), "ts": ts,
                     "dados": txt.encode("latin-1")})
    if caminho_qrp and os.path.exists(caminho_qrp):
        entradas.append({"path": f"c:\\data sus\\cnes\\exp_{nome_tx[:-4]}.qrp",
                         "ts": ts, "dados": open(caminho_qrp, "rb").read()})
    desc = (f"Exportação de Secretaria Mun P. Gestão para Município P. Gestão "
            f"em {datetime.now():%d/%m/%Y}*CN")
    return escrever_bck(desc, entradas)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

def encontrar_arquivo_local(*nomes):
    for n in nomes:
        p = os.path.join(BASE_DIR, n)
        if os.path.exists(p):
            return p
    return None

# ─────────────────────────────────────────────────────────────
#  HTML TEMPLATE
# ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JARVIS CNES · Cadastro Nacional de Estabelecimentos de Saúde</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ── Reset & Design Tokens ── */
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --azul:#003057;--azul-esc:#001e3c;--azul-lt:#e8f0f8;--azul-md:#cddaeb;
  --verde:#0f6e3f;--vm:#b91c1c;--am:#b45309;
  --borda:#d1d9e6;--borda-lt:#e8edf4;
  --txt:#1a2535;--muted:#5a6a7e;--muted-lt:#8898aa;
  --fundo:#f0f4f8;--fundo-lt:#f7f9fc;--card:#ffffff;
  --radius-lg:14px;--radius-md:8px;--radius-sm:5px;
  --shadow-sm:0 1px 3px rgba(0,0,0,.06);
  --shadow:0 2px 8px rgba(0,0,0,.08);
  --shadow-lg:0 8px 32px -8px rgba(0,0,0,.14);
  --touch:42px;
}
html{scroll-behavior:smooth}
body{background:var(--fundo);font-family:'Inter',sans-serif;color:var(--txt);
     padding:clamp(6px,1.5vw,16px);font-size:13.5px;line-height:1.5}
.app{width:min(100%,1400px);margin:0 auto;background:var(--card);
     border-radius:var(--radius-lg);box-shadow:var(--shadow-lg);overflow:hidden}

/* ── Header ── */
.hdr{background:linear-gradient(135deg,var(--azul) 0%,var(--azul-esc) 100%);
     padding:clamp(12px,1.8vw,22px) clamp(16px,2vw,28px);
     display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}

/* Logo esquerda — sem moldura */
.hdr-logo{display:flex;align-items:center}
.hdr-logo img{max-height:58px;width:auto;object-fit:contain;
              filter:drop-shadow(0 1px 3px rgba(0,0,0,.25))}

/* Logo central */
.hdr-center{text-align:center;color:#fff;display:flex;flex-direction:column;align-items:center;gap:6px}
.hdr-center img{max-height:64px;object-fit:contain;border-radius:10px;
                background:#fff;padding:5px 10px;
                box-shadow:0 2px 8px rgba(0,0,0,.2)}
.hdr-center-text{font-size:.68rem;font-weight:700;opacity:.85;text-transform:uppercase;letter-spacing:.08em}

/* Logo direita — MESMO ESTILO da central */
.hdr-right{display:flex;justify-content:flex-end;align-items:center}
.hdr-right img{max-height:64px;width:auto;object-fit:contain;
               border-radius:10px;background:#fff;
               padding:5px 10px;
               box-shadow:0 2px 8px rgba(0,0,0,.2)}

/* ── Main tabs ── */
.main-tabs{display:flex;background:var(--fundo-lt);border-bottom:2px solid var(--borda);
           padding:0 clamp(8px,1.5vw,20px);gap:0;overflow-x:auto;scrollbar-width:none}
.main-tabs::-webkit-scrollbar{display:none}
.main-tab{background:transparent;border:none;border-bottom:3px solid transparent;
          padding:11px clamp(10px,1.5vw,18px);font-weight:600;font-size:.75rem;
          cursor:pointer;color:var(--muted);white-space:nowrap;
          min-height:var(--touch);transition:all .15s;
          display:inline-flex;align-items:center;gap:5px;letter-spacing:.02em}
.main-tab .tab-icon{font-size:.9rem;opacity:.7}
.main-tab:hover{color:var(--azul);background:var(--azul-lt)}
.main-tab.active{color:var(--azul);border-bottom-color:var(--azul);font-weight:700}
.tab-pane{display:none;padding:clamp(12px,1.8vw,22px)}
.tab-pane.active{display:block}

/* ── Pill sub-tabs ── */
.pill-tabs{display:flex;gap:5px;margin-bottom:14px;flex-wrap:nowrap;
           overflow-x:auto;padding-bottom:2px;scrollbar-width:none}
.pill-tabs::-webkit-scrollbar{display:none}
.pill-tab{flex:0 0 auto;background:var(--fundo);border:1.5px solid var(--borda);
          border-radius:20px;padding:5px 13px;font-size:.71rem;font-weight:600;
          cursor:pointer;color:var(--muted);white-space:nowrap;
          min-height:32px;transition:all .15s;display:inline-flex;align-items:center;gap:4px}
.pill-tab:hover{border-color:var(--azul);color:var(--azul)}
.pill-tab.active{background:var(--azul);border-color:var(--azul);color:#fff;font-weight:700}
.pill-pane{display:none}
.pill-pane.active{display:block}

/* ── Cards ── */
.card{background:var(--card);border-radius:var(--radius-md);border:1px solid var(--borda);
      padding:clamp(12px,1.8vw,18px);margin-bottom:14px;box-shadow:var(--shadow-sm)}
.sec-title{font-size:.75rem;font-weight:800;color:var(--azul);
           border-left:3px solid var(--azul);padding-left:9px;
           margin-bottom:13px;text-transform:uppercase;letter-spacing:.05em;
           display:flex;align-items:center;gap:6px}
.sec-sub{font-size:.68rem;font-weight:700;color:var(--muted);
         margin:13px 0 7px;text-transform:uppercase;letter-spacing:.05em;
         border-bottom:1px solid var(--borda-lt);padding-bottom:3px}

/* ── Form grid ── */
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));
     gap:10px;margin-bottom:10px}
.row-2{grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr))}
.row-3{grid-template-columns:repeat(auto-fit,minmax(min(170px,100%),1fr))}
.row-4{grid-template-columns:repeat(auto-fit,minmax(min(130px,100%),1fr))}
.fg{min-width:0}
.fg label{display:block;font-size:.63rem;font-weight:700;text-transform:uppercase;
          color:var(--muted);margin-bottom:4px;letter-spacing:.04em}
.fg input,.fg select,.fg textarea{
  width:100%;min-height:var(--touch);padding:7px 10px;
  border:1.5px solid var(--borda);border-radius:var(--radius-sm);
  font-size:.8rem;font-family:inherit;background:#fff;
  transition:border-color .15s,box-shadow .15s;color:var(--txt)}
.fg input:focus,.fg select:focus,.fg textarea:focus{
  outline:none;border-color:var(--azul);box-shadow:0 0 0 3px rgba(0,48,87,.08)}
.fg input[type=number]{text-align:center}
.fg textarea{min-height:72px;resize:vertical}
.badge-novo{display:inline-block;background:var(--verde);color:#fff;
            border-radius:4px;padding:1px 6px;font-size:.58rem;
            font-weight:800;letter-spacing:.04em;margin-left:5px;vertical-align:middle}
.badge-obrig{display:inline-block;background:var(--vm);color:#fff;
            border-radius:4px;padding:1px 6px;font-size:.58rem;
            font-weight:800;letter-spacing:.04em;margin-left:5px;vertical-align:middle}
.fg label .badge-obrig{vertical-align:middle;margin-left:4px}
.field-error input,.field-error select,.field-error textarea{
            border-color:var(--vm)!important;box-shadow:0 0 0 3px rgba(185,28,28,.1)!important}
.field-error-msg{color:var(--vm);font-size:.62rem;font-weight:600;margin-top:3px;display:block}

/* ── Checkbox grid ── */
.chk-wrap{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:5px 8px;margin-top:5px}
.chk-wrap label{font-size:.76rem;display:inline-flex;align-items:flex-start;
                gap:6px;cursor:pointer;min-height:26px;line-height:1.35}
.chk-wrap input[type=checkbox]{width:14px;height:14px;margin-top:2px;
                                flex:0 0 auto;accent-color:var(--azul)}

/* ── Tabelas de equipamentos ── */
.eq-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.eq-tbl{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.76rem}
.eq-tbl colgroup col.col-nome{width:auto}
.eq-tbl colgroup col.col-chk{width:80px}
.eq-tbl colgroup col.col-qtd{width:82px}
.eq-tbl colgroup col.col-uso{width:82px}
.eq-tbl thead tr{background:var(--azul)}
.eq-tbl thead th{color:#fff;padding:7px 8px;font-weight:700;font-size:.67rem;text-align:center;
                  white-space:nowrap;border:1px solid rgba(255,255,255,.12)}
.eq-tbl thead th:first-child{text-align:left;border-radius:var(--radius-sm) 0 0 0}
.eq-tbl thead th:last-child{border-radius:0 var(--radius-sm) 0 0}
.eq-tbl tbody tr:nth-child(even){background:var(--fundo-lt)}
.eq-tbl tbody tr:hover{background:var(--azul-lt)}
.eq-tbl tbody td{padding:5px 8px;border-bottom:1px solid var(--borda-lt);vertical-align:middle;font-size:.75rem}
.eq-tbl tbody td:first-child{text-align:left}
.eq-tbl tbody td:not(:first-child){text-align:center}
.eq-tbl input[type=number]{width:58px;min-height:30px;padding:3px 5px;font-size:.76rem;
  text-align:center;border:1.5px solid var(--borda);border-radius:var(--radius-sm);
  font-family:inherit;background:#fff}
.eq-tbl input[type=number]:focus{outline:none;border-color:var(--azul)}
.eq-tbl input[type=checkbox]{width:16px;height:16px;accent-color:var(--azul);cursor:pointer}
.eq-tbl select.sn-sel{width:66px;min-height:28px;padding:3px 4px;font-size:.72rem;
  border:1.5px solid var(--borda);border-radius:var(--radius-sm);background:#fff;
  font-family:inherit;cursor:pointer}

/* ── Comissões chips ── */
.chip-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:7px;margin-bottom:10px}
.chip-item{display:flex;align-items:center;justify-content:space-between;
           background:var(--fundo);border:1px solid var(--borda);border-radius:var(--radius-sm);
           padding:7px 9px;gap:7px;transition:border-color .15s,background .15s}
.chip-item.ativa{border-color:var(--azul);background:var(--azul-lt)}
.chip-item span{font-size:.71rem;font-weight:600;color:var(--txt);flex:1;line-height:1.3}
.chip-item select{width:66px;min-height:28px;padding:2px 5px;font-size:.7rem;
                  border-radius:var(--radius-sm);border:1.5px solid var(--borda);
                  background:#fff;font-family:inherit;font-weight:700;cursor:pointer}
.chip-item select.sim{border-color:var(--azul);color:var(--azul);background:var(--azul-lt)}

/* ── Info row ── */
.info-row{display:flex;flex-wrap:wrap;gap:9px;align-items:flex-end}
.info-row .fg{flex:1 1 130px}
.chk-inline{display:flex;flex-wrap:wrap;gap:7px;align-items:center;padding-bottom:3px}
.chk-inline label{font-size:.72rem;display:flex;align-items:center;gap:5px;cursor:pointer;white-space:nowrap}
.chk-inline input[type=checkbox]{accent-color:var(--azul)}

/* ── Conexão pills ── */
.conexao-grid{display:flex;flex-wrap:wrap;gap:6px;margin-top:5px}
.conexao-grid label{font-size:.71rem;display:flex;align-items:center;gap:4px;cursor:pointer;
                    background:var(--fundo);border:1px solid var(--borda);border-radius:16px;
                    padding:4px 9px;transition:all .13s}
.conexao-grid label:has(input:checked){background:var(--azul);border-color:var(--azul);color:#fff}
.conexao-grid input[type=radio]{display:none}

/* ── Ficha 6 salas ── */
.salas-tbl{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.76rem}
.salas-tbl colgroup col.col-sala{width:auto}
.salas-tbl colgroup col.col-num{width:72px}
.salas-tbl colgroup col.col-num2{width:72px}
.salas-tbl thead th{background:var(--azul);color:#fff;padding:6px 8px;
  font-size:.66rem;font-weight:700;text-align:center;border:1px solid rgba(255,255,255,.12)}
.salas-tbl thead th:first-child{text-align:left;border-radius:var(--radius-sm) 0 0 0}
.salas-tbl thead th:last-child{border-radius:0 var(--radius-sm) 0 0}
.salas-tbl tbody tr:nth-child(even){background:var(--fundo-lt)}
.salas-tbl tbody tr:hover{background:var(--azul-lt)}
.salas-tbl tbody td{padding:5px 8px;border-bottom:1px solid var(--borda-lt);vertical-align:middle;font-size:.75rem}
.salas-tbl tbody td:first-child{text-align:left}
.salas-tbl tbody td:not(:first-child){text-align:center}
.salas-tbl input[type=number]{width:56px;min-height:29px;padding:3px 4px;font-size:.76rem;
  text-align:center;border:1.5px solid var(--borda);border-radius:var(--radius-sm);background:#fff;font-family:inherit}
.salas-tbl input[type=number]:focus{outline:none;border-color:var(--azul)}
.sec-label{font-size:.67rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;
           background:var(--fundo);padding:4px 8px;border-left:3px solid var(--azul-md)}

/* ── Apoio ── */
.apoio-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:7px}
.apoio-item{display:flex;align-items:center;justify-content:space-between;
            background:var(--fundo);border:1px solid var(--borda);
            border-radius:var(--radius-sm);padding:7px 9px;gap:7px}
.apoio-item span{font-size:.73rem;font-weight:600;flex:1;line-height:1.3}
.apoio-item select{width:115px;min-height:30px;padding:3px 5px;font-size:.71rem;
                    border-radius:var(--radius-sm);border:1.5px solid var(--borda);
                    background:#fff;font-family:inherit}

/* ── Leitos ── */
.leitos-tbl{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.76rem}
.leitos-tbl colgroup col.col-esp{width:auto}
.leitos-tbl colgroup col.col-leit{width:90px}
.leitos-tbl thead th{background:var(--azul);color:#fff;padding:7px 8px;font-weight:700;
                      font-size:.66rem;text-align:center;border:1px solid rgba(255,255,255,.12)}
.leitos-tbl thead th:first-child{text-align:left;border-radius:var(--radius-sm) 0 0 0}
.leitos-tbl thead th:last-child{border-radius:0 var(--radius-sm) 0 0}
.leitos-tbl tbody tr:nth-child(even){background:var(--fundo-lt)}
.leitos-tbl tbody tr:hover{background:var(--azul-lt)}
.leitos-tbl tbody td{padding:5px 8px;border-bottom:1px solid var(--borda-lt);vertical-align:middle}
.leitos-tbl tbody td:not(:first-child){text-align:center}
.leitos-tbl tfoot td{padding:6px 8px;font-weight:700;font-size:.73rem;
                      background:var(--azul-lt);border-top:2px solid var(--azul)}
.leitos-tbl tfoot td:not(:first-child){text-align:center;color:var(--azul)}
.leitos-tbl input[type=number]{width:62px;min-height:29px;padding:3px 5px;font-size:.76rem;
  text-align:center;border:1.5px solid var(--borda);border-radius:var(--radius-sm);background:#fff}
.leitos-tbl input[type=number]:focus{outline:none;border-color:var(--azul)}
.leitos-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}

/* ── Profissionais / Especializações ── */
.prof-item,.esp-item{background:var(--fundo-lt);border-radius:var(--radius-md);
                     padding:clamp(12px,1.8vw,16px);margin-bottom:13px;
                     border:1px solid var(--borda);box-shadow:var(--shadow-sm)}
.item-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.item-hdr strong{font-size:.8rem;color:var(--azul);font-weight:700}
.cbo-row{display:flex;align-items:center;gap:7px;margin-bottom:6px}
.cbo-row select{flex:1;min-height:34px}
.btn-rm-cbo{background:none;border:none;color:var(--vm);font-size:1rem;cursor:pointer;
            padding:0 5px;min-height:34px;opacity:.7}
.btn-rm-cbo:hover{opacity:1}

/* ── Botões ── */
.btn{min-height:var(--touch);padding:8px 14px;border-radius:var(--radius-md);
     font-weight:700;font-size:.75rem;border:none;cursor:pointer;
     display:inline-flex;align-items:center;justify-content:center;
     gap:6px;white-space:nowrap;transition:all .15s;letter-spacing:.02em;font-family:inherit}
.btn:hover{filter:brightness(1.07);transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn-primary{background:var(--azul);color:#fff}
.btn-preview{background:#0369a1;color:#fff}
.btn-success{background:var(--verde);color:#fff}
.btn-danger{background:var(--vm);color:#fff}
.btn-warning{background:var(--am);color:#fff}
.btn-secondary{background:var(--fundo);color:var(--azul);border:1.5px solid var(--borda)}
.btn-gov{background:#1351b4;color:#fff}
.btn-sm{min-height:32px;padding:5px 10px;font-size:.7rem;border-radius:var(--radius-sm)}
.btn-full{width:100%}

/* ── Painel de ações ── */
.action-panel{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
              gap:7px;margin-top:14px;background:var(--fundo);
              border:1px solid var(--borda);border-radius:var(--radius-md);padding:11px}

/* ── Info box ── */
.info-box{background:var(--azul-lt);border-left:3px solid var(--azul);
          padding:10px 13px;border-radius:var(--radius-sm);margin:12px 0;font-size:.76rem}
.info-box p{margin:2px 0;color:var(--txt)}

/* ── Progress ── */
.prog-wrap{margin-top:10px;background:#e2e8f0;border-radius:20px;overflow:hidden;display:none}
.prog-bar{width:0%;height:4px;background:var(--verde);transition:width .35s}
.prog-step{font-size:.68rem;color:var(--muted);margin-top:5px;text-align:center}

/* ── Status ── */
.status{margin-top:12px;padding:10px 13px;border-radius:var(--radius-sm);font-size:.78rem;font-weight:500}
.status.ok{background:#dcfce7;color:#14532d;border-left:3px solid var(--verde)}
.status.err{background:#fee2e2;color:#7f1d1d;border-left:3px solid var(--vm)}

/* ── File input ── */
.file-hidden{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
.file-info{color:var(--muted-lt);font-size:.7rem;margin-top:5px}

/* ══════════════════════════════════════════════
   DECLARAÇÃO — compacta
   ══════════════════════════════════════════════ */
.decl-alert{background:#eff6ff;border:1px solid #bfdbfe;border-radius:var(--radius-md);
            padding:8px 12px;margin-bottom:10px;display:flex;align-items:flex-start;
            gap:8px;font-size:.74rem;color:#1e40af;line-height:1.45}
.decl-alert span{font-size:1.1rem;flex-shrink:0;margin-top:1px}

.pontos-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px;margin-bottom:10px}
.ponto{background:var(--fundo-lt);border:1px solid var(--borda);border-radius:var(--radius-md);padding:7px 10px}
.ponto-icon{font-size:1.1rem;margin-bottom:2px}
.ponto-title{font-size:.65rem;font-weight:700;color:var(--muted);text-transform:uppercase;
             letter-spacing:.05em;margin-bottom:3px}
.ponto-text{font-size:.71rem;color:var(--txt);line-height:1.4}

.decl-card{background:var(--card);border:1px solid var(--borda);border-radius:var(--radius-md);
           padding:12px 16px;margin-bottom:10px}
.decl-header{text-align:center;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--borda-lt)}
.decl-header .org1{font-size:.65rem;font-weight:600;color:var(--muted);letter-spacing:.05em;text-transform:uppercase}
.decl-header .org2{font-size:.72rem;font-weight:600;color:var(--txt);margin-top:2px}
.decl-header .titulo{font-size:.95rem;font-weight:700;color:var(--azul);margin-top:6px}

.decl-body{font-size:.79rem;line-height:1.6;color:var(--txt)}
.decl-body p{margin-bottom:6px}
.field-decl{display:inline-block;min-width:120px;border:none;border-bottom:2px solid var(--azul);
            background:transparent;font-size:.8rem;font-family:inherit;color:var(--txt);
            padding:0 4px 1px;outline:none;transition:border-color .15s}
.field-decl:focus{border-bottom-color:#0369a1;background:var(--azul-lt)}
.field-decl.wide{min-width:200px}
.field-decl.medium{min-width:150px}
.field-decl.small{min-width:70px}
.field-decl-sel{display:inline-block;border:none;border-bottom:2px solid var(--azul);
                background:transparent;font-size:.8rem;font-family:inherit;color:var(--txt);
                padding:0 4px 1px;outline:none;cursor:pointer;min-width:120px}
.field-decl-sel:focus{border-bottom-color:#0369a1}

.decl-obs{background:#fffbeb;border-left:3px solid #f59e0b;border-radius:0 var(--radius-sm) var(--radius-sm) 0;
          padding:5px 10px;margin:5px 0;font-size:.72rem;color:#78350f;line-height:1.45}
.decl-highlight{padding:6px 10px;background:var(--azul-lt);
                border-left:3px solid var(--azul);border-radius:0 var(--radius-sm) var(--radius-sm) 0;
                margin-bottom:7px}
.decl-highlight strong{display:block;margin-bottom:3px;font-size:.72rem;color:var(--azul)}

.assin-area{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;
            padding-top:8px;border-top:1px solid var(--borda-lt)}
.assin-item{text-align:center}
.assin-line{border-bottom:1px solid var(--txt);margin-bottom:4px;height:28px}
.assin-label{font-size:.69rem;color:var(--muted);font-style:italic}
.assin-sub{font-size:.63rem;color:var(--muted-lt)}

.data-row{display:flex;gap:6px;align-items:center;font-size:.78rem;margin-top:6px;flex-wrap:wrap}
.data-row label{color:var(--muted);white-space:nowrap;font-size:.75rem}

.checklist{background:var(--fundo-lt);border:1px solid var(--borda);
           border-radius:var(--radius-md);padding:12px 14px;margin-top:10px}
.checklist-title{font-size:.68rem;font-weight:700;color:var(--muted);
                 margin-bottom:8px;text-transform:uppercase;letter-spacing:.05em}
.chk-item{display:flex;align-items:flex-start;gap:8px;font-size:.77rem;
          color:var(--txt);padding:3px 0;line-height:1.4}
.chk-item span.ico{font-size:.9rem;color:var(--verde);margin-top:1px;flex-shrink:0}

.btn-row-decl{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}

/* ── Divisor ── */
.divider{height:1px;background:var(--borda-lt);margin:12px 0}

/* ── MODAL GOV.BR ── */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;
          justify-content:center;z-index:9999;opacity:0;pointer-events:none;transition:opacity .2s}
.modal-bg.open{opacity:1;pointer-events:all}
.modal{background:var(--card);border-radius:var(--radius-lg);border:1px solid var(--borda);
       max-width:520px;width:92%;overflow:hidden;transform:translateY(12px);transition:transform .2s}
.modal-bg.open .modal{transform:translateY(0)}
.modal-head{background:#1351b4;padding:14px 18px;display:flex;align-items:center;gap:10px}
.modal-head .gov-logo{font-size:1.1rem;font-weight:700;color:#fff;letter-spacing:.02em}
.modal-head .gov-sub{font-size:.7rem;color:rgba(255,255,255,.8);margin-top:1px}
.modal-body{padding:16px 18px}
.modal-step{display:flex;gap:10px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--borda-lt)}
.modal-step:last-of-type{border-bottom:none;margin-bottom:0;padding-bottom:0}
.step-num{width:26px;height:26px;border-radius:50%;background:#1351b4;color:#fff;font-size:.7rem;
          font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px}
.step-content .step-title{font-size:.78rem;font-weight:600;color:var(--txt);margin-bottom:2px}
.step-content .step-desc{font-size:.71rem;color:var(--muted);line-height:1.5}
.modal-warn{background:#fef2f2;border:1px solid #fecaca;border-radius:var(--radius-sm);
            padding:10px 12px;margin:12px 0;font-size:.72rem;color:#7f1d1d;display:flex;gap:8px}
.modal-footer{padding:12px 18px;border-top:1px solid var(--borda-lt);display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}
.gov-badge{display:inline-flex;align-items:center;gap:5px;background:#1351b4;color:#fff;
           border-radius:var(--radius-sm);padding:3px 9px;font-size:.66rem;font-weight:700}

/* ── Footer ── */
.footer{background:#0c1f33;color:#cdd8e8;padding:16px;text-align:center;font-size:.72rem}
.footer-inner{max-width:760px;margin:0 auto;display:flex;flex-direction:column;
              gap:3px;align-items:center}
.footer-inner strong{color:#fff;font-size:.75rem}
.dev-credit{color:#7bafd4;margin-top:4px;font-size:.68rem}

/* ── Responsive ── */
@media(max-width:640px){
  .hdr{grid-template-columns:1fr;text-align:center;gap:8px}
  .hdr-logo,.hdr-right{justify-content:center}
  .action-panel{grid-template-columns:1fr 1fr}
  .chip-grid{grid-template-columns:1fr}
  .apoio-grid{grid-template-columns:1fr}
  .assin-area{grid-template-columns:1fr}
  .pontos-grid{grid-template-columns:1fr}
}
@media(max-width:400px){
  .action-panel{grid-template-columns:1fr}
  .main-tab{padding:9px 10px;font-size:.7rem}
}
</style>
</head>
<body>
<div class="app">

  <!-- ── Header ── -->
  <div class="hdr">
    <div class="hdr-logo">
      <img src="/logo-prefeitura" alt="Prefeitura de Porto Velho" onerror="this.style.display='none'">
    </div>
    <div class="hdr-center">
      <img src="/logo-jarvis" alt="JARVIS CNES" onerror="this.style.display='none'">
      <div class="hdr-center-text">Sistema Auxiliar do Cadastro CNES</div>
    </div>
    <div class="hdr-right">
      <img src="/logo-cnes" alt="CNES" onerror="this.style.display='none'">
    </div>
  </div>

  <!-- ── Main tabs ── -->
  <div class="main-tabs">
    <button class="main-tab active" data-main="cadastro"><span class="tab-icon">📋</span>Cadastro</button>
    <button class="main-tab" data-main="infra"><span class="tab-icon">🏥</span>Infraestrutura</button>
    <button class="main-tab" data-main="equip"><span class="tab-icon">🩺</span>Equipamentos</button>
    <button class="main-tab" data-main="pessoas"><span class="tab-icon">👥</span>Pessoas</button>
    <button class="main-tab" data-main="final"><span class="tab-icon">📄</span>Finalização</button>
  </div>

  <!-- ══════ CADASTRO ══════ -->
  <div id="cadastro" class="tab-pane active">
    <div class="pill-tabs">
      <button class="pill-tab active" data-pill="f1">Ficha 1 — Identificação</button>
      <button class="pill-tab" data-pill="f2">Ficha 2 — Caracterização</button>
    </div>

    <!-- Ficha 1 -->
    <div id="f1" class="pill-pane active">
      <div class="card">
        <div class="sec-title">Dados Operacionais e Identificação</div>
        <div class="row row-3">
          <div class="fg"><label>Operação</label>
            <select id="f1_operacao"><option>Inclusão</option><option>Alteração</option><option>Exclusão</option></select>
          </div>
          <div class="fg"><label>Código CNES</label><input id="f1_cnes" placeholder="Apenas para cadastros existentes"></div>
          <div class="fg"><label>Tipo de Estabelecimento</label><input id="f1_tipo_estab"></div>
        </div>
        <div class="row row-3">
          <div class="fg"><label>CNPJ / CPF <span class="badge-obrig">*</span></label><input id="f1_cnpj" placeholder="00.000.000/0000-00"></div>
          <div class="fg"><label>Razão Social / Nome Empresarial <span class="badge-obrig">*</span></label><input id="f1_nome_empresarial"></div>
          <div class="fg"><label>Nome Fantasia <span class="badge-obrig">*</span></label><input id="f1_fantasia"></div>
        </div>
        <div class="sec-sub">Endereço</div>
        <div class="row row-4">
          <div class="fg"><label>CEP <span class="badge-obrig">*</span></label><input id="f1_cep" placeholder="00000-000"></div>
          <div class="fg"><label>Logradouro</label><input id="f1_endereco"></div>
          <div class="fg"><label>Número</label><input id="f1_numero"></div>
          <div class="fg"><label>Complemento</label><input id="f1_complemento"></div>
        </div>
        <div class="row row-3">
          <div class="fg"><label>Bairro</label><input id="f1_bairro"></div>
          <div class="fg"><label>Telefone</label><input id="f1_telefone" placeholder="(69) 99999-9999"></div>
          <div class="fg"><label>E-mail Institucional</label><input id="f1_email" type="email"></div>
        </div>
        <div class="sec-sub">Responsável Técnico (RT)</div>
        <div class="row row-2">
          <div class="fg"><label>Diretor Clínico / Administrador <span class="badge-obrig">*</span></label><input id="f1_administrador"></div>
          <div class="fg"><label>Registro no Conselho <span class="badge-obrig">*</span></label><input id="f1_conselho_rt"></div>
        </div>
        <div class="sec-sub">Vigilância Sanitária <span class="badge-novo">NOVO</span></div>
        <div class="row row-3">
          <div class="fg"><label>Número do Alvará</label><input id="f1_alvara" placeholder="Nº do alvará"></div>
          <div class="fg"><label>Data de Expedição</label><input type="date" id="f1_alvara_data"></div>
          <div class="fg"><label>Órgão Expedidor</label>
            <select id="f1_alvara_orgao">
              <option value="">— Selecione —</option>
              <option>SES - Secretaria Estadual de Saúde</option><option>SMS - Secretaria Municipal de Saúde</option><option>ANVISA</option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Ficha 2 -->
    <div id="f2" class="pill-pane">
      <div class="card">
        <div class="sec-title">Caracterização do Estabelecimento</div>
        <div class="row row-4">
          <div class="fg"><label>Esfera Administrativa</label>
            <select id="f2_esfera"><option>Municipal</option><option>Estadual</option><option>Federal</option></select>
          </div>
          <div class="fg"><label>Ensino / Pesquisa</label>
            <select id="f2_ensino"><option>Sem atividade</option><option>Unidade Universitária</option></select>
          </div>
          <div class="fg"><label>Nível de Hierarquia</label>
            <select id="f2_hierarquia">
              <option>1 - Atenção Básica</option>
              <option>2 - Média Complexidade</option>
              <option>3 - Alta Complexidade</option>
            </select>
          </div>
          <div class="fg"><label>Fluxo de Clientela</label>
            <select id="f2_fluxo_clientela">
              <option>1 - DEMANDA ESPONTÂNEA</option>
              <option>2 - DEMANDA REFERENCIADA</option>
              <option>3 - AMBAS</option>
            </select>
          </div>
        </div>
        <div class="row row-4">
          <div class="fg"><label>Convênio</label>
            <select id="f2_convenio">
              <option>01 - SUS</option><option>02 - PARTICULAR</option>
              <option>05 - PÚBLICO</option><option>06 - PRIVADO</option><option>07 - GRATUIDADE</option>
            </select>
          </div>
          <div class="fg"><label>Turno de Atendimento <span class="badge-obrig">*</span></label>
            <select id="f2_turno">
              <option>Manhã</option><option>Tarde</option>
              <option>Manhã e Tarde</option><option>24 horas</option>
            </select>
          </div>
          <div class="fg"><label>Dias de Funcionamento <span class="badge-obrig">*</span></label><input id="f2_dias_func" placeholder="Ex: Seg–Sex"></div>
          <div class="fg"><label>Horários <span class="badge-obrig">*</span></label><input id="f2_horas_func" placeholder="07h–17h"></div>
        </div>
        <div class="sec-sub">Atendimento Prestado (5.10)</div>
        <div id="atendimento_opcoes"></div>
      </div>
    </div>
  </div>

  <!-- ══════ INFRAESTRUTURA ══════ -->
  <div id="infra" class="tab-pane">
    <div class="pill-tabs">
      <button class="pill-tab active" data-pill="f6">Ficha 6 — Salas</button>
      <button class="pill-tab" data-pill="f4">Ficha 4 — Comissões</button>
      <button class="pill-tab" data-pill="f7">Ficha 7 — Apoio</button>
      <button class="pill-tab" data-pill="res">Resíduos</button>
      <button class="pill-tab" data-pill="f19">Ficha 19 — Leitos</button>
    </div>

    <!-- Ficha 6 -->
    <div id="f6" class="pill-pane active">
      <div class="card">
        <div class="sec-title">Instalações Físicas — Ficha 6</div>
        <div class="pill-tabs" id="f6-subtabs">
          <button class="pill-tab active" data-f6="ue">15.1 — Urgência/Emergência</button>
          <button class="pill-tab" data-f6="amb">15.2 — Ambulatório</button>
          <button class="pill-tab" data-f6="hosp">15.3 — Hospitalar</button>
        </div>

        <!-- 15.1 UE -->
        <div id="f6-ue" class="f6-sec">
          <table class="salas-tbl">
            <colgroup><col class="col-sala"><col class="col-num"></colgroup>
            <thead><tr><th>Sala / Ambiente</th><th>Quantidade</th></tr></thead>
            <tbody>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">Consultórios</td></tr>
              <tr><td>Consultórios Médicos</td><td><input type="number" id="f6_ue_med" value="0" min="0"></td></tr>
              <tr><td>Odontologia — Consultórios</td><td><input type="number" id="f6_ue_odonto" value="0" min="0"></td></tr>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">Sala de Atendimento / Triagem</td></tr>
              <tr><td>Pediátrico</td><td><input type="number" id="f6_triagem_ped" value="0" min="0"></td></tr>
              <tr><td>Feminino</td><td><input type="number" id="f6_triagem_fem" value="0" min="0"></td></tr>
              <tr><td>Masculino</td><td><input type="number" id="f6_triagem_masc" value="0" min="0"></td></tr>
              <tr><td>Indiferenciado</td><td><input type="number" id="f6_triagem_indf" value="0" min="0"></td></tr>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">Demais Salas</td></tr>
              <tr><td>Sala de Curativo</td><td><input type="number" id="f6_ue_curativo" value="0" min="0"></td></tr>
              <tr><td>Sala de Gesso</td><td><input type="number" id="f6_ue_gesso" value="0" min="0"></td></tr>
              <tr><td>Sala de Higienização</td><td><input type="number" id="f6_higienizacao" value="0" min="0"></td></tr>
              <tr><td>Sala de Pequena Cirurgia</td><td><input type="number" id="f6_ue_peq_cir" value="0" min="0"></td></tr>
            </tbody>
          </table>
          <div style="margin-top:12px">
            <table class="salas-tbl">
              <colgroup><col class="col-sala"><col class="col-num"><col class="col-num2"></colgroup>
              <thead><tr><th>Sala de Repouso / Observação</th><th>Salas</th><th>Leitos</th></tr></thead>
              <tbody>
                <tr><td>Pediátrico</td>
                  <td><input type="number" id="f6_repouso_ped_salas" value="0" min="0"></td>
                  <td><input type="number" id="f6_repouso_ped_leitos" value="0" min="0"></td></tr>
                <tr><td>Feminino</td>
                  <td><input type="number" id="f6_repouso_fem_salas" value="0" min="0"></td>
                  <td><input type="number" id="f6_repouso_fem_leitos" value="0" min="0"></td></tr>
                <tr><td>Masculino</td>
                  <td><input type="number" id="f6_repouso_masc_salas" value="0" min="0"></td>
                  <td><input type="number" id="f6_repouso_masc_leitos" value="0" min="0"></td></tr>
                <tr><td>Indiferenciado</td>
                  <td><input type="number" id="f6_repouso_indf_salas" value="0" min="0"></td>
                  <td><input type="number" id="f6_repouso_indf_leitos" value="0" min="0"></td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 15.2 Ambulatório -->
        <div id="f6-amb" class="f6-sec" style="display:none">
          <table class="salas-tbl">
            <colgroup><col class="col-sala"><col class="col-num"></colgroup>
            <thead><tr><th>Sala / Ambiente</th><th>Quantidade</th></tr></thead>
            <tbody>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">Consultórios Médicos</td></tr>
              <tr><td>Clínicas Básicas</td><td><input type="number" id="f6_amb_basicas" value="0" min="0"></td></tr>
              <tr><td>Clínicas Especializadas</td><td><input type="number" id="f6_amb_especializadas" value="0" min="0"></td></tr>
              <tr><td>Indiferenciado</td><td><input type="number" id="f6_amb_indf" value="0" min="0"></td></tr>
              <tr><td>Outros Consultórios (Não Médicos)</td><td><input type="number" id="f6_outros_nmed" value="0" min="0"></td></tr>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">Odontologia e Outras Salas</td></tr>
              <tr><td>Odontologia — Consultórios</td><td><input type="number" id="f6_odonto_amb" value="0" min="0"></td></tr>
              <tr><td>Sala de Pequena Cirurgia</td><td><input type="number" id="f6_peq_cirurgia_amb" value="0" min="0"></td></tr>
              <tr><td>Sala de Enfermagem</td><td><input type="number" id="f6_enfermagem" value="0" min="0"></td></tr>
              <tr><td>Sala de Imunização</td><td><input type="number" id="f6_imunizacao" value="0" min="0"></td></tr>
              <tr><td>Sala de Nebulização</td><td><input type="number" id="f6_nebulizacao" value="0" min="0"></td></tr>
              <tr><td>Sala de Gesso</td><td><input type="number" id="f6_gesso_amb" value="0" min="0"></td></tr>
              <tr><td>Sala de Curativo</td><td><input type="number" id="f6_curativo_amb" value="0" min="0"></td></tr>
              <tr><td>Sala de Cirurgia Ambulatorial</td><td><input type="number" id="f6_cirurgia_amb" value="0" min="0"></td></tr>
            </tbody>
          </table>
          <div style="margin-top:12px">
            <table class="salas-tbl">
              <colgroup><col class="col-sala"><col class="col-num"><col class="col-num2"></colgroup>
              <thead><tr><th>Repouso / Observação</th><th>Salas</th><th>Leitos</th></tr></thead>
              <tbody>
                <tr><td>Pediátrico</td>
                  <td><input type="number" id="f6_amb_rep_ped_s" value="0" min="0"></td>
                  <td><input type="number" id="f6_amb_rep_ped_l" value="0" min="0"></td></tr>
                <tr><td>Feminino</td>
                  <td><input type="number" id="f6_amb_rep_fem_s" value="0" min="0"></td>
                  <td><input type="number" id="f6_amb_rep_fem_l" value="0" min="0"></td></tr>
                <tr><td>Masculino</td>
                  <td><input type="number" id="f6_amb_rep_masc_s" value="0" min="0"></td>
                  <td><input type="number" id="f6_amb_rep_masc_l" value="0" min="0"></td></tr>
                <tr><td>Indiferenciado</td>
                  <td><input type="number" id="f6_amb_rep_indf_s" value="0" min="0"></td>
                  <td><input type="number" id="f6_amb_rep_indf_l" value="0" min="0"></td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 15.3 Hospitalar -->
        <div id="f6-hosp" class="f6-sec" style="display:none">
          <table class="salas-tbl">
            <colgroup><col class="col-sala"><col class="col-num"></colgroup>
            <thead><tr><th>Sala / Ambiente</th><th>Quantidade</th></tr></thead>
            <tbody>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">15.3.1 — Centro Cirúrgico</td></tr>
              <tr><td>Sala de Cirurgia</td><td><input type="number" id="f6_cirurgia" value="0" min="0"></td></tr>
              <tr><td>Sala de Cirurgia Ambulatorial (CC)</td><td><input type="number" id="f6_cirurgia_amb_cc" value="0" min="0"></td></tr>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">15.3.2 — Centro Obstétrico</td></tr>
              <tr><td>Sala de Parto Normal</td><td><input type="number" id="f6_parto_normal" value="0" min="0"></td></tr>
              <tr><td>Sala de Curetagem</td><td><input type="number" id="f6_curetagem" value="0" min="0"></td></tr>
              <tr><td>Sala de Cirurgia (CO)</td><td><input type="number" id="f6_cirurgia_co" value="0" min="0"></td></tr>
              <tr class="sec-label-row"><td colspan="2" class="sec-label">15.3.3 — Unidade Neonatal</td></tr>
              <tr><td>Leitos RN Normal</td><td><input type="number" id="f6_leitos_rn_normal" value="0" min="0"></td></tr>
              <tr><td>Leitos RN Patológico</td><td><input type="number" id="f6_leitos_rn_patologico" value="0" min="0"></td></tr>
              <tr><td>Leitos Alojamento Conjunto</td><td><input type="number" id="f6_leitos_alojamento" value="0" min="0"></td></tr>
            </tbody>
          </table>
          <div style="margin-top:12px">
            <table class="salas-tbl">
              <colgroup><col class="col-sala"><col class="col-num"><col class="col-num2"></colgroup>
              <thead><tr><th>Salas com Dupla Contagem</th><th>Salas</th><th>Leitos</th></tr></thead>
              <tbody>
                <tr><td>Sala de Recuperação</td>
                  <td><input type="number" id="f6_recuperacao" value="0" min="0"></td>
                  <td><input type="number" id="f6_recuperacao_leitos" value="0" min="0"></td></tr>
                <tr><td>Sala de Pré-parto</td>
                  <td><input type="number" id="f6_preparto_qtd" value="0" min="0"></td>
                  <td><input type="number" id="f6_preparto_leitos" value="0" min="0"></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Ficha 4 -->
    <div id="f4" class="pill-pane">
      <div class="card">
        <div class="sec-title">Comissões — Ficha 4 (9.1)</div>
        <div class="chip-grid" id="comissoes_grid"></div>
        <div class="sec-sub">9.2 — Avaliação PNASS</div>
        <div class="info-row">
          <div class="fg" style="flex:0 1 130px"><label>Foi avaliado?</label>
            <select id="f4_pnass_avaliado"><option>Não</option><option>Sim</option></select>
          </div>
          <div class="fg" style="flex:0 1 155px"><label>Data de Avaliação</label>
            <input type="date" id="f4_pnass_data">
          </div>
          <div class="chk-inline">
            <label><input type="checkbox" id="f4_pnass_nao_atendeu"> Não atendeu padrões</label>
            <label><input type="checkbox" id="f4_pnass_nivel1"> Nível 1</label>
            <label><input type="checkbox" id="f4_pnass_nivel2"> Nível 2</label>
            <label><input type="checkbox" id="f4_pnass_nivel3"> Nível 3</label>
          </div>
        </div>
        <div class="sec-sub">9.3 — Acreditação Hospitalar</div>
        <div class="info-row">
          <div class="fg" style="flex:0 1 130px"><label>Foi Acreditado?</label>
            <select id="f4_acreditado"><option>Não</option><option>Sim</option></select>
          </div>
          <div class="fg" style="flex:0 1 155px"><label>Data de Acreditação</label>
            <input type="date" id="f4_acreditacao_data">
          </div>
          <div class="fg" style="flex:0 1 175px"><label>9.4 — Prog. Filantrópico</label>
            <select id="f4_adesao_filantropico"><option>Não</option><option>Sim</option></select>
          </div>
        </div>
        <div class="sec-sub">8 — Comunicação e Informática</div>
        <div class="info-row" style="align-items:flex-start">
          <div class="fg" style="flex:0 1 120px"><label>Internet (8.1.1) <span class="badge-obrig">*</span></label>
            <select id="f4_internet"><option>Não</option><option>Sim</option></select>
          </div>
          <div class="fg" style="flex:1 1 260px"><label>Tipo de Conexão (8.1.2) <span class="badge-obrig">*</span></label>
            <div class="conexao-grid">
              <label><input type="radio" name="conexao" value="Discado">Discado</label>
              <label><input type="radio" name="conexao" value="ADSL">ADSL</label>
              <label><input type="radio" name="conexao" value="Link dedicado">Link Dedicado</label>
              <label><input type="radio" name="conexao" value="Rádio">Rádio</label>
              <label><input type="radio" name="conexao" value="Satélite">Satélite</label>
              <label><input type="radio" name="conexao" value="Cabo Modem">Cabo Modem</label>
              <label><input type="radio" name="conexao" value="3G">3G / 4G</label>
              <label><input type="radio" name="conexao" value="Fibra Ótica">Fibra Ótica</label>
            </div>
          </div>
          <div class="fg" style="flex:0 1 120px"><label>Telefonia Fixa (8.2.1) <span class="badge-obrig">*</span></label>
            <select id="f4_telefonia_fixa"><option>Não</option><option>Sim</option></select>
          </div>
          <div class="fg" style="flex:0 1 120px"><label>Telefonia Móvel (8.2.2) <span class="badge-obrig">*</span></label>
            <select id="f4_telefonia_movel"><option>Não</option><option>Sim</option></select>
          </div>
        </div>
      </div>
    </div>

    <!-- Ficha 7 -->
    <div id="f7" class="pill-pane">
      <div class="card">
        <div class="sec-title">Serviços de Apoio — Ficha 7</div>
        <div class="apoio-grid" id="servicos_apoio"></div>
      </div>
    </div>

    <!-- Resíduos -->
    <div id="res" class="pill-pane">
      <div class="card">
        <div class="sec-title">Resíduos / Rejeitos — Seção 30</div>
        <div id="residuos_opcoes"></div>
        <div class="fg" style="margin-top:11px"><label>Especificações adicionais</label>
          <textarea id="f17_outros_res" rows="3"></textarea>
        </div>
      </div>
    </div>

    <!-- Ficha 19 — Leitos -->
    <div id="f19" class="pill-pane">
      <div class="card">
        <div class="sec-title">Quantidade de Leitos por Especialidade — Ficha 19</div>
        <div class="pill-tabs" id="f19-pills">
          <button class="pill-tab active" data-f19="cir">Cirúrgicos</button>
          <button class="pill-tab" data-f19="obs">Obstétricos / Ped.</button>
          <button class="pill-tab" data-f19="clin">Clínicos</button>
          <button class="pill-tab" data-f19="out">Outras Espec.</button>
          <button class="pill-tab" data-f19="hd">Hospital Dia</button>
          <button class="pill-tab" data-f19="comp">Complementares</button>
        </div>
        <div id="f19-cir" class="f19-sec"><div class="leitos-wrap"><table class="leitos-tbl" id="tbl_leitos_cirurgicos"></table></div></div>
        <div id="f19-obs" class="f19-sec" style="display:none">
          <div class="leitos-wrap"><table class="leitos-tbl" id="tbl_leitos_obstetricos"></table></div>
          <div class="leitos-wrap" style="margin-top:14px"><table class="leitos-tbl" id="tbl_leitos_pediatricos"></table></div>
        </div>
        <div id="f19-clin" class="f19-sec" style="display:none"><div class="leitos-wrap"><table class="leitos-tbl" id="tbl_leitos_clinicos"></table></div></div>
        <div id="f19-out"  class="f19-sec" style="display:none"><div class="leitos-wrap"><table class="leitos-tbl" id="tbl_leitos_outras"></table></div></div>
        <div id="f19-hd"   class="f19-sec" style="display:none"><div class="leitos-wrap"><table class="leitos-tbl" id="tbl_leitos_hospital_dia"></table></div></div>
        <div id="f19-comp" class="f19-sec" style="display:none"><div class="leitos-wrap"><table class="leitos-tbl" id="tbl_leitos_complementares"></table></div></div>
      </div>
    </div>
  </div>

  <!-- ══════ EQUIPAMENTOS ══════ -->
  <div id="equip" class="tab-pane">
    <div class="pill-tabs">
      <button class="pill-tab active" data-pill="eq13">Ficha 13 — Diagnóstico / Infra</button>
      <button class="pill-tab" data-pill="eq14">Ficha 14 — Ópticos</button>
      <button class="pill-tab" data-pill="eq15">Ficha 15 — Gráficos / Vida</button>
      <button class="pill-tab" data-pill="eq16">Ficha 16 — Odontologia</button>
      <button class="pill-tab" data-pill="eq17">Ficha 17 — Audiologia</button>
    </div>
    <div id="eq13" class="pill-pane active">
      <div class="card"><div class="sec-title">29.1 — Diagnóstico por Imagem</div><div class="eq-wrap"><table class="eq-tbl" id="eq_diag"></table></div></div>
      <div class="card"><div class="sec-title">29.2 — Infraestrutura</div><div class="eq-wrap"><table class="eq-tbl" id="eq_infra"></table></div></div>
    </div>
    <div id="eq14" class="pill-pane">
      <div class="card"><div class="sec-title">29.3 — Métodos Ópticos</div><div class="eq-wrap"><table class="eq-tbl" id="eq_opticos"></table></div></div>
    </div>
    <div id="eq15" class="pill-pane">
      <div class="card"><div class="sec-title">29.4 — Métodos Gráficos</div><div class="eq-wrap"><table class="eq-tbl" id="metodos_graficos"></table></div></div>
      <div class="card"><div class="sec-title">29.5 — Manutenção da Vida</div><div class="eq-wrap"><table class="eq-tbl" id="manutencao_vida"></table></div></div>
    </div>
    <div id="eq16" class="pill-pane">
      <div class="card"><div class="sec-title">29.6 — Odontologia</div><div class="eq-wrap"><table class="eq-tbl" id="eq_odonto"></table></div></div>
      <div class="card"><div class="sec-title">29.7 — Outros Equipamentos</div><div class="eq-wrap"><table class="eq-tbl" id="eq_outros"></table></div></div>
    </div>
    <div id="eq17" class="pill-pane">
      <div class="card"><div class="sec-title">29.8 — Audiologia</div><div class="eq-wrap"><table class="eq-tbl" id="eq_audio"></table></div></div>
    </div>
  </div>

  <!-- ══════ PESSOAS ══════ -->
  <div id="pessoas" class="tab-pane">
    <div class="pill-tabs">
      <button class="pill-tab active" data-pill="f8">Ficha 8 — Especializações</button>
      <button class="pill-tab" data-pill="prof">Fichas 20/21 — Profissionais</button>
    </div>
    <div id="f8" class="pill-pane active">
      <div id="especializacoes_lista"></div>
      <button class="btn btn-primary" onclick="adicionarEspecializacao()">+ Adicionar Especialização</button>
    </div>
    <div id="prof" class="pill-pane">
      <div id="profissionais_lista"></div>
      <button class="btn btn-primary" onclick="adicionarProfissional()">+ Adicionar Profissional</button>
    </div>
  </div>

  <!-- ══════ FINALIZAÇÃO ══════ -->
  <div id="final" class="tab-pane">
    <div class="pill-tabs">
      <button class="pill-tab active" data-pill="fin_envio">📤 Envio e Anexos</button>
      <button class="pill-tab" data-pill="fin_decl">📝 Declaração</button>
    </div>

    <!-- Envio -->
    <div id="fin_envio" class="pill-pane active">
      <div class="card">
        <div class="sec-title">Anexos e Envio</div>
        <div class="info-box">
          <p>Preencha todas as fichas e anexe o extrato CNES extraído de <strong>https://cnes.datasus.gov.br/</strong></p>
          <p>Após o envio, o extrato PDF será encaminhado para <strong>gecav.semusa@portovelho.ro.gov.br</strong></p>
          <p>O arquivo .BCK para o SCNES é gerado automaticamente e segue anexo, com acesso restrito à GECAV.</p>
          <p>Dúvidas: (69) 3901-3174 · gecav.semusa@portovelho.ro.gov.br</p>
        </div>
        <div class="fg" style="margin-top:10px">
          <label>Anexos — Extrato CNES e documentos complementares</label>
          <input class="file-hidden" type="file" id="anexos" multiple accept=".pdf,.png,.jpg,.jpeg">
          <div class="file-info" id="anexosInfo">Nenhum arquivo selecionado.</div>
        </div>
        <div class="action-panel">
          <button class="btn btn-preview" id="btnPreview">🔍 Pré-visualizar PDF</button>
          <button class="btn btn-warning" id="btnAnexos">📎 Adicionar Anexos</button>
          <button class="btn btn-primary" id="btnPDF">⬇ Baixar PDF</button>
          <button class="btn btn-success" id="btnEmail">✉ Enviar para GECAV</button>
        </div>
        <div class="prog-wrap" id="progWrap"><div class="prog-bar" id="progBar"></div></div>
        <div class="prog-step" id="progStep"></div>
        <div id="statusMsg"></div>
      </div>
    </div>

    <!-- Declaração -->
    <div id="fin_decl" class="pill-pane">
      <div class="decl-alert">
        <span>ℹ️</span>
        <div>Preencha a declaração abaixo, gere o PDF e depois <strong>autentique o extrato CNES no GOV.br</strong> para dar validade jurídica ao cadastro. O PDF gerado pelo sistema é auxiliar — o documento oficial é o extrato autenticado via portal do Ministério da Saúde.</div>
      </div>

      <div class="sec-title" style="margin-bottom:10px">Requisitos obrigatórios — pontos críticos do cadastro</div>
      <div class="pontos-grid">
        <div class="ponto"><div class="ponto-icon">🏥</div><div class="ponto-title">Espaço físico permanente</div><div class="ponto-text">O estabelecimento deve ter localização física delimitada e permanente — tendas, barracas ou mutirões em locais abertos não são aceitos.</div></div>
        <div class="ponto"><div class="ponto-icon">👤</div><div class="ponto-title">Responsabilidade técnica</div><div class="ponto-text">Obrigatório indicar pessoa física legalmente habilitada como RT. Espaços desativados ou em construção não são cadastráveis.</div></div>
        <div class="ponto"><div class="ponto-icon">🪪</div><div class="ponto-title">CNPJ/CPF obrigatório</div><div class="ponto-text">PJ com mais de um estabelecimento: cada unidade precisa de CNPJ próprio (matriz/filial). PJ privada que administra unidade pública: usar campo "Gerente/Administrador Terceiro".</div></div>
        <div class="ponto"><div class="ponto-icon">🕐</div><div class="ponto-title">Atualização mensal obrigatória</div><div class="ponto-text">Portaria 1.646/2015: manutenção do cadastro deve ocorrer minimamente todo mês ou imediatamente após qualquer alteração. O cadastro precede o alvará de funcionamento.</div></div>
        <div class="ponto"><div class="ponto-icon">📋</div><div class="ponto-title">Documentos da empresa</div><div class="ponto-text">CNPJ atualizado, alvará de funcionamento, alvará Vigilância Sanitária, contrato social, declaração de tipo de estabelecimento (Port. GM 2.022/2017) e horários de funcionamento.</div></div>
        <div class="ponto"><div class="ponto-icon">🩺</div><div class="ponto-title">Documentos dos profissionais</div><div class="ponto-text">Diploma, RG, CPF, carteira do conselho (RO), comprovante de residência, contrato de trabalho com carga horária semanal e registro de especialização (se houver).</div></div>
      </div>

      <div class="divider"></div>

      <div class="sec-title" style="margin-bottom:10px">Declaração — Pessoa Jurídica e/ou Física</div>
      <div class="decl-card">
        <div class="decl-header">
          <div class="org1">À Secretaria Municipal de Saúde – SEMUSA</div>
          <div class="org2">Departamento de Regulação Avaliação e Controle – DRAC &nbsp;·&nbsp; Cadastro Nacional de Estabelecimento de Saúde – CNES</div>
          <div class="titulo">Modelo de Declaração para Pessoa Jurídica e/ou Física</div>
        </div>

        <div class="decl-body">
          <p>
            Declaramos que, para os devidos fins que a
            <input class="field-decl wide" id="d_razao" placeholder="NOME / RAZÃO SOCIAL">
            inscrita no CNPJ Nº
            <input class="field-decl medium" id="d_cnpj" placeholder="00.000.000/0000-00">
            (<input class="field-decl medium" id="d_fantasia" placeholder="NOME FANTASIA">)
            estabelecida à Rua
            <input class="field-decl wide" id="d_rua" placeholder="logradouro, nº">
            Bairro:
            <input class="field-decl medium" id="d_bairro" placeholder="bairro">
            CEP:
            <input class="field-decl small" id="d_cep" placeholder="00000-000">
            Porto Velho – RO,
          </p>
          <p>
            neste ato representada(o) por Titular/Administrador/Responsável Técnico,
            Sr./Sra.
            <input class="field-decl wide" id="d_rt_nome" placeholder="nome completo do RT">
            brasileiro(a), profissão
            <input class="field-decl medium" id="d_profissao" placeholder="profissão">
            portador do RG Nº
            <input class="field-decl small" id="d_rg" placeholder="RG">
            expedida em
            <input class="field-decl small" id="d_rg_orgao" placeholder="SSP/RO">
            e CPF
            <input class="field-decl medium" id="d_cpf" placeholder="000.000.000-00">
            Nº, Registro de Conselho Nº
            <input class="field-decl medium" id="d_conselho" placeholder="nº do conselho">
          </p>
          <p>
            baseado(a) na Portaria GM N. 2.022, de 7 de agosto de 2017, e no Anexo XV da Portaria de Consolidação Nº 1, de 28 de setembro de 2017, <strong>Item III – Classificação dos Tipos de Estabelecimentos de Saúde</strong>, declaramos que o(a) mesmo(a) enquadra-se no tipo de estabelecimento:
          </p>

          <div class="decl-highlight">
            <strong>Tipo de Estabelecimento:</strong>
            <select class="field-decl-sel" id="d_tipo_estab" style="min-width:260px">
              <option value="">— selecione o tipo —</option>
              <option>Centro de Parto Normal</option>
              <option>Centro de Saúde / Unidade Básica de Saúde</option>
              <option>Clínica Especializada / Ambulatório Especializado</option>
              <option>Consultório</option><option>Farmácia</option>
              <option>Hospital Dia</option><option>Hospital Especializado</option>
              <option>Hospital Geral</option><option>Policlínica</option>
              <option>Posto de Saúde</option>
              <option>Pronto Socorro Especializado</option>
              <option>Pronto Socorro Geral</option>
              <option>Unidade Autorizadora</option>
              <option>Unidade de Saúde da Família</option>
              <option>Unidade de Serviço de Apoio de Diagnose e Terapia (SADT)</option>
              <option>Unidade de Vigilância Sanitária</option>
              <option>Unidade Mista</option>
              <option>Unidade Móvel de Nível Pré-Hospitalar (Urgência/Emergência)</option>
              <option>Unidade Móvel Fluvial</option>
              <option>Unidade Terrestre Móvel</option>
              <option>Serviço Residencial Terapêutico (SRT) Tipo I</option>
              <option>Serviço Residencial Terapêutico (SRT) Tipo II</option>
            </select>
            <br><br>
            <strong>Atividade Principal:</strong><br>
            <input class="field-decl" id="d_atv_principal" placeholder="descreva a atividade principal" style="min-width:320px">
            <br><br>
            <strong>Atividades Secundárias:</strong><br>
            <input class="field-decl" id="d_atv_sec" placeholder="descreva as atividades secundárias (se houver)" style="min-width:320px">
          </div>

          <div class="decl-obs">
            <strong>OBS 01:</strong> Informar os horários e dias da semana em que o estabelecimento irá funcionar:<br>
            <input class="field-decl" id="d_horarios" placeholder="ex: segunda à sexta das 08:00 às 18:00; fecha para almoço" style="min-width:340px;margin-top:4px">
          </div>
          <div class="decl-obs">
            <strong>OBS 02:</strong> Favor não colocar as atividades econômicas contidas no CNPJ. Colocar de acordo com a <strong>Portaria 2022 do Ministério da Saúde</strong>.
          </div>

          <p style="margin-top:6px">Por ser verdade, firmo a presente.</p>

          <div class="data-row">
            <label>Porto Velho/RO,</label>
            <input type="number" class="field-decl small" id="d_dia" placeholder="dia" min="1" max="31" style="width:52px">
            <label>de</label>
            <select class="field-decl-sel" id="d_mes" style="min-width:110px">
              <option value="">— mês —</option>
              <option>Janeiro</option><option>Fevereiro</option><option>Março</option>
              <option>Abril</option><option>Maio</option><option>Junho</option>
              <option>Julho</option><option>Agosto</option><option>Setembro</option>
              <option>Outubro</option><option>Novembro</option><option>Dezembro</option>
            </select>
            <label>de</label>
            <input type="number" class="field-decl small" id="d_ano" placeholder="2025" style="width:72px" min="2024" max="2030">
          </div>
        </div>

        <div class="assin-area">
          <div class="assin-item">
            <div class="assin-line"></div>
            <div class="assin-label">Titular / Administrador / Responsável Técnico</div>
            <div class="assin-sub">Pode ser assinatura GOV.br</div>
          </div>
          <div class="assin-item">
            <div class="assin-line"></div>
            <div class="assin-label">Carimbo do Estabelecimento</div>
            <div class="assin-sub">CNPJ / CRM / CRO / COREN</div>
          </div>
        </div>
      </div>

      <div class="btn-row-decl">
        <button class="btn btn-primary" onclick="preencherDeclaracaoAutomatico()">🪄 Preencher com dados do cadastro</button>
        <button class="btn btn-warning" onclick="limparDeclaracao()">🗑 Limpar campos</button>
        <button class="btn btn-gov" onclick="abrirModalGov()">🛡 Autenticar no GOV.br</button>
      </div>

      <div class="checklist">
        <div class="checklist-title">✅ Checklist de documentos obrigatórios antes do envio</div>
        <div class="chk-item"><span class="ico">✔</span> CNPJ atualizado — comprovante de situação cadastral na Receita Federal</div>
        <div class="chk-item"><span class="ico">✔</span> Alvará de Funcionamento (Fazenda) — original ou protocolo</div>
        <div class="chk-item"><span class="ico">✔</span> Alvará da Vigilância Sanitária Estadual/Municipal — atualizado ou protocolo</div>
        <div class="chk-item"><span class="ico">✔</span> Contrato Social ou Estatuto da pessoa jurídica</div>
        <div class="chk-item"><span class="ico">✔</span> Declaração de tipo de estabelecimento e atividades (Port. GM 2.022/2017) — este documento</div>
        <div class="chk-item"><span class="ico">✔</span> Planilha/declaração com horário de funcionamento</div>
        <div class="chk-item"><span class="ico">✔</span> Fichas CNES preenchidas, assinadas e carimbadas pelo diretor</div>
        <div class="chk-item"><span class="ico">✔</span> Profissionais: diploma, RG, CPF, carteira do conselho (RO), contrato de trabalho com CH semanal</div>
        <div class="chk-item"><span class="ico">✔</span> Extrato CNES extraído de <strong>cnes.datasus.gov.br</strong> e autenticado no GOV.br</div>
      </div>
    </div>
  </div>

  <footer class="footer">
    <div class="footer-inner">
      <strong>SEMUSA — Secretaria Municipal de Saúde de Porto Velho</strong>
      <span>Avenida Campos Sales, nº 2283, Centro — Porto Velho / RO</span>
      <span>gecav.semusa@portovelho.ro.gov.br</span>
      <span class="dev-credit">Desenvolvido por Cristian Marques</span>
    </div>
  </footer>
</div>

<!-- ══ MODAL GOV.BR ══ -->
<div class="modal-bg" id="modalGovBg" role="dialog" aria-modal="true" aria-labelledby="modal-gov-titulo">
  <div class="modal">
    <div class="modal-head">
      <div>
        <div class="gov-logo">🇧🇷 GOV.BR</div>
        <div class="gov-sub">Portal do Governo Federal</div>
      </div>
    </div>
    <div class="modal-body">
      <p id="modal-gov-titulo" style="font-size:.9rem;font-weight:600;color:var(--txt);margin-bottom:12px">
        Autentique o extrato CNES para validade jurídica
      </p>
      <div class="modal-warn">
        <span style="font-size:1.1rem;flex-shrink:0">⚠️</span>
        <div><strong>Atenção:</strong> O PDF gerado por este sistema é um <strong>documento auxiliar de apoio ao cadastramento</strong>. Para ter <strong>validade jurídica oficial</strong>, o extrato do CNES precisa ser extraído diretamente do portal do Ministério da Saúde e autenticado via GOV.br.</div>
      </div>
      <div class="modal-step">
        <div class="step-num">1</div>
        <div class="step-content">
          <div class="step-title">Acesse o portal CNES/DATASUS</div>
          <div class="step-desc">Entre em <strong>cnes.datasus.gov.br</strong> e localize seu estabelecimento pelo código CNES ou CNPJ.</div>
        </div>
      </div>
      <div class="modal-step">
        <div class="step-num">2</div>
        <div class="step-content">
          <div class="step-title">Extraia o extrato oficial</div>
          <div class="step-desc">Gere o extrato do seu estabelecimento diretamente no portal. Este extrato contém os dados oficialmente cadastrados no sistema nacional.</div>
        </div>
      </div>
      <div class="modal-step">
        <div class="step-num">3</div>
        <div class="step-content">
          <div class="step-title">Autentique com sua conta GOV.br</div>
          <div class="step-desc">Faça login com CPF e senha GOV.br (nível Prata ou Ouro recomendado). A assinatura digital via GOV.br dá validade jurídica ao documento, conforme Decreto nº 10.543/2020.</div>
        </div>
      </div>
      <div class="modal-step">
        <div class="step-num">4</div>
        <div class="step-content">
          <div class="step-title">Encaminhe à SEMUSA com os demais documentos</div>
          <div class="step-desc">Junte o extrato autenticado às fichas CNES preenchidas e carimbadas, e envie para <strong>gecav.semusa@portovelho.ro.gov.br</strong> ou presencialmente na Av. Campos Sales, 2283, Centro.</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;font-size:.7rem;color:var(--muted);margin-top:8px">
        <span class="gov-badge">🛡 Assinatura GOV.br</span>
        <span>aceita como substituta à assinatura física — Decreto 10.543/2020</span>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary btn-sm" onclick="fecharModalGov()">✕ Fechar</button>
      <button class="btn btn-gov btn-sm" onclick="window.open('https://cnes.datasus.gov.br','_blank')">🔗 Ir para CNES/DATASUS</button>
      <button class="btn btn-gov btn-sm" onclick="window.open('https://www.gov.br/pt-br/servicos/assinatura-eletronica','_blank')">🛡 Assinar no GOV.br</button>
    </div>
  </div>
</div>

<script>
// ── Dados injetados pelo Flask ────────────────────────────────────────────────
const equipDiag      = {{ EQUIP_DIAG_IMAGEM|tojson }};
const equipInfra     = {{ EQUIP_INFRA|tojson }};
const equipOpticos   = {{ EQUIP_OPTICOS|tojson }};
const equipOdonto    = {{ EQUIP_ODONTO|tojson }};
const equipOutros    = {{ EQUIP_OUTROS|tojson }};
const equipAudio     = {{ EQUIP_AUDIO|tojson }};
const metGraficos    = {{ METODOS_GRAFICOS|tojson }};
const manutVida      = {{ MANUTENCAO_VIDA|tojson }};
const servicosApoio  = {{ SERVICOS_APOIO|tojson }};
const residuosOpcoes = {{ OPCOES_REJEITOS|tojson }};
const leitosCir      = {{ LEITOS_CIRURGICOS|tojson }};
const leitosObs      = {{ LEITOS_OBSTETRICOS|tojson }};
const leitosPed      = {{ LEITOS_PEDIATRICOS|tojson }};
const leitosClin     = {{ LEITOS_CLINICOS|tojson }};
const leitosOut      = {{ LEITOS_OUTRAS|tojson }};
const leitosHD       = {{ LEITOS_HOSPITAL_DIA|tojson }};
const leitosComp     = {{ LEITOS_COMPLEMENTARES|tojson }};
const servicosCBO    = {{ SERVICOS_CBO|tojson }};
const cboMap         = {{ CBO_DICT|tojson }};
const comissoesF4    = {{ COMISSOES_F4|tojson }};
const cboOptions     = Object.entries(cboMap).map(([c,d]) => ({c, d}));

let profissionais = [], especializacoes = [];
const g  = id => document.getElementById(id)?.value  ?? '';
const gc = id => document.getElementById(id)?.checked ?? false;

// ── Render Equipamentos ───────────────────────────────────────────────────────
function renderEquip(tblId, lista, key) {
  const tbl = document.getElementById(tblId);
  tbl.innerHTML = `
    <colgroup>
      <col class="col-nome"><col class="col-chk"><col class="col-qtd"><col class="col-uso">
    </colgroup>
    <thead><tr>
      <th style="text-align:left">Equipamento</th>
      <th>Possui?</th><th>Qtd Existente</th><th>Qtd em Uso</th>
    </tr></thead>
    <tbody>${lista.map((nome,i) => `<tr>
      <td>${nome}</td>
      <td><input type="checkbox" class="eq-possui" data-key="${key}" data-idx="${i}"></td>
      <td><input type="number" class="eq-qtd" data-key="${key}" data-idx="${i}" value="0" min="0"></td>
      <td><input type="number" class="eq-uso" data-key="${key}" data-idx="${i}" value="0" min="0"></td>
    </tr>`).join('')}</tbody>`;
}

function renderMetodos(tblId, lista, tipo) {
  const tbl = document.getElementById(tblId);
  tbl.innerHTML = `
    <colgroup>
      <col class="col-nome"><col class="col-chk"><col class="col-qtd"><col class="col-uso">
    </colgroup>
    <thead><tr>
      <th style="text-align:left">Equipamento</th>
      <th>Possui?</th><th>Qtd Existente</th><th>Qtd em Uso</th>
    </tr></thead>
    <tbody>${lista.map(([cod,nome]) => `<tr>
      <td>${nome}</td>
      <td><select class="sn-sel metodo-sn" data-tipo="${tipo}" data-cod="${cod}">
        <option value="nao">Não</option><option value="sim">Sim</option></select></td>
      <td><input type="number" class="metodo-ex" data-tipo="${tipo}" data-cod="${cod}" value="0" min="0"></td>
      <td><input type="number" class="metodo-us" data-tipo="${tipo}" data-cod="${cod}" value="0" min="0"></td>
    </tr>`).join('')}</tbody>`;
}

// ── Leitos ────────────────────────────────────────────────────────────────────
function renderLeitos(tblId, lista, label) {
  const tbl = document.getElementById(tblId);
  tbl.innerHTML = `
    <colgroup><col class="col-esp"><col class="col-leit"><col class="col-leit"></colgroup>
    <caption style="font-size:.68rem;font-weight:800;color:var(--azul);text-align:left;
      padding:0 0 5px;text-transform:uppercase;letter-spacing:.05em">${label}</caption>
    <thead><tr>
      <th style="text-align:left">Especialidade</th>
      <th>Existente</th><th>SUS</th>
    </tr></thead>
    <tbody>${lista.map(esp => {
      const esc = esp.replace(/"/g,'&quot;');
      return `<tr>
        <td>${esp}</td>
        <td><input type="number" class="leito-ex"  data-leito="${esc}" data-tbl="${tblId}" value="0" min="0"></td>
        <td><input type="number" class="leito-sus" data-leito="${esc}" data-tbl="${tblId}" value="0" min="0"></td>
      </tr>`;
    }).join('')}</tbody>
    <tfoot><tr>
      <td>TOTAL</td>
      <td id="${tblId}_tot_ex">0</td>
      <td id="${tblId}_tot_sus">0</td>
    </tr></tfoot>`;
  tbl.querySelectorAll('.leito-ex,.leito-sus').forEach(inp =>
    inp.addEventListener('input', () => calcTotal(tblId, lista))
  );
}

function calcTotal(tblId, lista) {
  const tbl = document.getElementById(tblId);
  let ex = 0, sus = 0;
  lista.forEach(esp => {
    const eEl = [...tbl.querySelectorAll('.leito-ex')].find(e => e.dataset.leito === esp);
    const sEl = [...tbl.querySelectorAll('.leito-sus')].find(e => e.dataset.leito === esp);
    ex  += parseInt(eEl?.value  || 0);
    sus += parseInt(sEl?.value || 0);
  });
  const et = document.getElementById(`${tblId}_tot_ex`);
  const st = document.getElementById(`${tblId}_tot_sus`);
  if (et) et.textContent = ex;
  if (st) st.textContent = sus;
}

// ── Comissões ─────────────────────────────────────────────────────────────────
function renderComissoes() {
  document.getElementById('comissoes_grid').innerHTML = comissoesF4.map(([cod,nome]) => `
    <div class="chip-item" id="chip_${cod}">
      <span>${cod} — ${nome}</span>
      <select id="f4_${cod}" class="chip-sel" onchange="
        this.classList.toggle('sim', this.value==='Sim');
        document.getElementById('chip_${cod}').classList.toggle('ativa', this.value==='Sim')">
        <option value="Não">Não</option>
        <option value="Sim">Sim</option>
      </select>
    </div>`).join('');
}

// ── Apoio ─────────────────────────────────────────────────────────────────────
function renderApoio() {
  document.getElementById('servicos_apoio').innerHTML = servicosApoio.map((s,i) => `
    <div class="apoio-item">
      <span>${s}</span>
      <select id="apoio_${i}">
        <option value="Nao">Não possui</option>
        <option value="Proprio">Próprio</option>
        <option value="Terceirizado">Terceirizado</option>
      </select>
    </div>`).join('');
}

// ── Resíduos ──────────────────────────────────────────────────────────────────
function renderResiduos() {
  document.getElementById('residuos_opcoes').innerHTML =
    '<div class="chk-wrap">' +
    residuosOpcoes.map(r => `<label><input type="checkbox" class="residuo" value="${r}"> ${r}</label>`).join('') +
    '</div>';
}

// ── Atendimento prestado ──────────────────────────────────────────────────────
function renderAtendimento() {
  const opts = [
    "01 - INTERNAÇÃO","02 - AMBULATORIAL","03 - SADT",
    "04 - URGÊNCIA","05 - OUTROS","06 - VIGILÂNCIA EM SAÚDE","07 - REGULAÇÃO"
  ];
  document.getElementById('atendimento_opcoes').innerHTML =
    '<div class="chk-wrap">' +
    opts.map(o => `<label><input type="checkbox" class="atendimento" value="${o}"> ${o}</label>`).join('') +
    '</div>';
}

// ── Vínculos Empregatícios ────────────────────────────────────────────────────
const empOpts = {
  "01 - VÍNCULO EMPREGATÍCIO": ["00 - NÃO SE APLICA","01 - ESTATUTÁRIO EFETIVO","02 - EMPREGADO PÚBLICO CELETISTA","03 - CONTRATADO TEMPORÁRIO","04 - CARGO COMISSIONADO","05 - CELETISTA"],
  "02 - AUTÔNOMO":             ["00 - NÃO SE APLICA","01 - INTERMEDIADO POR OS","02 - INTERMEDIADO ORG SOCIEDADE CIVIL","03 - INTERMEDIADO POR ONG","04 - INTERMEDIADO ENTIDADE FILANTRÓPICA","05 - INTERMEDIADO POR EMPRESA PRIVADA","06 - CONSULTORIA","07 - SEM INTERMEDIAÇÃO (RPA)","08 - INTERMEDIADO POR COOPERATIVA","09 - PESSOA JURÍDICA","10 - PESSOA FÍSICA","11 - COOPERADO"],
  "03 - COOPERATIVA":          ["00 - NÃO SE APLICA"],
  "04 - OUTROS":               ["01 - BOLSA","02 - CONTRATO VERBAL/INFORMAL","03 - PROPRIETÁRIO"],
  "05 - RESIDÊNCIA":           ["00 - NÃO SE APLICA","01 - RESIDENTE"],
  "06 - ESTÁGIO":              ["00 - NÃO SE APLICA","01 - ESTAGIÁRIO"],
  "07 - BOLSA":                ["01 - BOLSISTA"],
  "08 - INTERMEDIADO":         ["01 - EMPREGADO PÚBLICO CELETISTA","02 - CONTRATADO TEMPORÁRIO","03 - CARGO COMISSIONADO","04 - CELETISTA","05 - AUTÔNOMO","06 - COOPERADO","07 - SERVIDOR PÚBLICO"],
  "09 - INFORMAL":             ["01 - CONTRATADO VERBALMENTE","02 - VOLUNTARIADO"],
};

// ── Profissionais ─────────────────────────────────────────────────────────────
function renderProfissionais() {
  const cont = document.getElementById('profissionais_lista');
  cont.innerHTML = '';
  profissionais.forEach((p, idx) => {
    const div = document.createElement('div');
    div.className = 'prof-item';
    let selCbo = `<select class="prof-profissao" data-idx="${idx}"><option value="">— Selecione CBO —</option>`;
    cboOptions.forEach(o => {
      selCbo += `<option value="${o.c}" ${p.profissao===o.c?'selected':''}>${o.c} — ${o.d}</option>`;
    });
    selCbo += '</select>';
    div.innerHTML = `
      <div class="item-hdr">
        <strong>Profissional ${idx+1}</strong>
        <button class="btn btn-danger btn-sm" onclick="removerProfissional(${idx})">Remover</button>
      </div>
      <div class="row row-3">
        <div class="fg"><label>Nome Completo</label><input class="prof-nome" data-idx="${idx}" value="${p.nome||''}"></div>
        <div class="fg"><label>CPF <span class="badge-obrig">*</span></label><input class="prof-cpf" data-idx="${idx}" value="${p.cpf||''}"></div>
        <div class="fg"><label>Nome da Mãe</label><input class="prof-mae" data-idx="${idx}" value="${p.mae||''}"></div>
      </div>
      <div class="row row-3">
        <div class="fg"><label>Logradouro</label><input class="prof-end" data-idx="${idx}" value="${p.endereco||''}"></div>
        <div class="fg"><label>Número</label><input class="prof-num" data-idx="${idx}" value="${p.numero||''}"></div>
        <div class="fg"><label>Telefone</label><input class="prof-tel" data-idx="${idx}" value="${p.telefone||''}"></div>
      </div>
      <div class="row row-3">
        <div class="fg"><label>E-mail</label><input class="prof-email" data-idx="${idx}" value="${p.email||''}"></div>
        <div class="fg"><label>Conselho / Registro <span class="badge-obrig">*</span></label><input class="prof-cons" data-idx="${idx}" value="${p.conselho||''}"></div>
        <div class="fg"><label>CBO (Profissão) <span class="badge-obrig">*</span></label>${selCbo}
      </div>
      <div class="row row-3">
        <div class="fg"><label>C.H. Semanal (h) <span class="badge-obrig">*</span></label><input class="prof-ch" data-idx="${idx}" value="${p.ch||''}"></div>
        <div class="fg"><label>Vínculo com Estabelecimento <span class="badge-obrig">*</span></label>
          <select class="prof-estab" data-idx="${idx}">
            <option value="">— Selecione —</option>
            ${Object.keys(empOpts).map(v=>`<option value="${v}" ${p.estabelecimento===v?'selected':''}>${v}</option>`).join('')}
          </select>
        </div>
        <div class="fg"><label>Vínculo com Empregador</label>
          <select class="prof-empreg" data-idx="${idx}"><option value="">— Selecione —</option></select>
        </div>
      </div>
      <div class="row row-2">
        <div class="fg"><label>CNPJ da PJ</label><input class="prof-cnpj" data-idx="${idx}" value="${p.cnpj_pj||''}"></div>
        <div class="fg"><label>Detalhamento</label><input class="prof-det" data-idx="${idx}" value="${p.detalhamento||''}"></div>
      </div>`;
    cont.appendChild(div);
  });

  function updateEmpregador(idx) {
    const estab  = document.querySelector(`.prof-estab[data-idx="${idx}"]`);
    const empreg = document.querySelector(`.prof-empreg[data-idx="${idx}"]`);
    if (!estab || !empreg) return;
    const opts = empOpts[estab.value] || [];
    empreg.innerHTML = '<option value="">— Selecione —</option>' +
      opts.map(o => `<option value="${o}" ${profissionais[idx]?.empregador===o?'selected':''}>${o}</option>`).join('');
  }

  document.querySelectorAll('.prof-estab').forEach(sel => {
    updateEmpregador(sel.dataset.idx);
    sel.addEventListener('change', e => {
      profissionais[e.target.dataset.idx].estabelecimento = e.target.value;
      updateEmpregador(e.target.dataset.idx);
    });
  });
  document.querySelectorAll('.prof-empreg').forEach(sel =>
    sel.addEventListener('change', e => profissionais[e.target.dataset.idx].empregador = e.target.value)
  );
  document.querySelectorAll('.prof-profissao').forEach(sel =>
    sel.addEventListener('change', e => profissionais[e.target.dataset.idx].profissao = e.target.value)
  );

  const bind = (cls, field) => document.querySelectorAll(`.${cls}`).forEach(el =>
    el.addEventListener('input', e => profissionais[e.target.dataset.idx][field] = e.target.value)
  );
  bind('prof-nome','nome');     bind('prof-cpf','cpf');       bind('prof-mae','mae');
  bind('prof-end','endereco');  bind('prof-num','numero');     bind('prof-tel','telefone');
  bind('prof-email','email');   bind('prof-cons','conselho');  bind('prof-ch','ch');
  bind('prof-cnpj','cnpj_pj'); bind('prof-det','detalhamento');
}

function adicionarProfissional() { profissionais.push({}); renderProfissionais(); }
function removerProfissional(i)  { profissionais.splice(i, 1); renderProfissionais(); }

// ── Especializações ───────────────────────────────────────────────────────────
function renderEspecializacoes() {
  const cont = document.getElementById('especializacoes_lista');
  cont.innerHTML = '';
  especializacoes.forEach((esp, idx) => {
    const div = document.createElement('div');
    div.className = 'esp-item';
    let selServ = `<select class="esp-serv" data-idx="${idx}"><option value="">— Selecione Serviço —</option>`;
    for (const cod in servicosCBO) {
      const label = `${cod} — ${servicosCBO[cod].desc}`;
      selServ += `<option value="${label}" ${esp.servico===label?'selected':''}>${label}</option>`;
    }
    selServ += '</select>';
    let cbosHtml = `<div class="cbo-list" id="cbo-list-${idx}">`;
    (esp.cbos_selecionados || []).forEach((cv, ci) => {
      cbosHtml += `<div class="cbo-row">
        <select class="esp-cbo" data-eidx="${idx}" data-cidx="${ci}">
          <option value="">— Selecione CBO —</option>
          ${cboOptions.map(o => `<option value="${o.c}" ${o.c===cv?'selected':''}>${o.c} — ${o.d}</option>`).join('')}
        </select>
        <button class="btn-rm-cbo" data-eidx="${idx}" data-cidx="${ci}" title="Remover CBO">✕</button>
      </div>`;
    });
    cbosHtml += '</div>';
    div.innerHTML = `
      <div class="item-hdr">
        <strong>Especialização ${idx+1}</strong>
        <button class="btn btn-danger btn-sm" onclick="removerEspecializacao(${idx})">Remover</button>
      </div>
      <div class="row row-2">
        <div class="fg"><label>Serviço</label>${selServ}</div>
        <div class="fg"><label>Classificação</label>
          <select class="esp-class" data-idx="${idx}"><option value="">— Selecione —</option></select>
        </div>
      </div>
      <div class="fg"><label>CBOs Associados</label>
        ${cbosHtml}
        <button class="btn btn-secondary btn-sm btn-add-cbo btn-full" data-idx="${idx}" style="margin-top:7px">+ Adicionar CBO</button>
      </div>`;
    cont.appendChild(div);

    const servSel  = div.querySelector('.esp-serv');
    const classSel = div.querySelector('.esp-class');

    function atualizarClass() {
      const cod = servSel.value.split(' — ')[0];
      classSel.innerHTML = '<option value="">— Selecione —</option>';
      if (cod && servicosCBO[cod]) {
        for (const cc in servicosCBO[cod].classificacoes) {
          const label = `${cc} — ${servicosCBO[cod].classificacoes[cc].desc}`;
          classSel.innerHTML += `<option value="${label}" ${esp.classificacao===label?'selected':''}>${label}</option>`;
        }
      }
    }
    atualizarClass();
    servSel.addEventListener('change', () => { especializacoes[idx].servico = servSel.value; atualizarClass(); });
    classSel.addEventListener('change', () => { especializacoes[idx].classificacao = classSel.value; });
    div.addEventListener('change', e => {
      if (e.target.classList.contains('esp-cbo')) {
        especializacoes[idx].cbos_selecionados =
          Array.from(div.querySelectorAll('.esp-cbo')).map(s => s.value).filter(Boolean);
      }
    });
    div.addEventListener('click', e => {
      if (e.target.classList.contains('btn-rm-cbo')) {
        especializacoes[idx].cbos_selecionados.splice(parseInt(e.target.dataset.cidx), 1);
        renderEspecializacoes();
      }
      if (e.target.classList.contains('btn-add-cbo')) {
        especializacoes[idx].cbos_selecionados.push('');
        renderEspecializacoes();
      }
    });
  });
}

function adicionarEspecializacao() {
  especializacoes.push({ servico:'', classificacao:'', cbos_selecionados:[] });
  renderEspecializacoes();
}
function removerEspecializacao(i) { especializacoes.splice(i, 1); renderEspecializacoes(); }

// ── Declaração — preencher automático ─────────────────────────────────────────
function preencherDeclaracaoAutomatico() {
  const m = {
    d_razao:    g('f1_nome_empresarial'),
    d_cnpj:     g('f1_cnpj'),
    d_fantasia: g('f1_fantasia'),
    d_rua:      g('f1_endereco') + (g('f1_numero') ? ', nº ' + g('f1_numero') : ''),
    d_bairro:   g('f1_bairro'),
    d_cep:      g('f1_cep'),
    d_rt_nome:  g('f1_administrador'),
    d_conselho: g('f1_conselho_rt'),
    d_horarios: (g('f2_dias_func') + ' ' + g('f2_horas_func')).trim(),
  };
  for (const [id, val] of Object.entries(m)) {
    const el = document.getElementById(id);
    if (el && val) el.value = val;
  }
}

function limparDeclaracao() {
  ['d_razao','d_cnpj','d_fantasia','d_rua','d_bairro','d_cep',
   'd_rt_nome','d_profissao','d_rg','d_rg_orgao','d_cpf','d_conselho',
   'd_atv_principal','d_atv_sec','d_horarios'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('d_tipo_estab').selectedIndex = 0;
}

// ── Modal GOV.br ──────────────────────────────────────────────────────────────
function abrirModalGov()  { document.getElementById('modalGovBg').classList.add('open'); }
function fecharModalGov() { document.getElementById('modalGovBg').classList.remove('open'); }

// ── Coleta de dados ───────────────────────────────────────────────────────────
function coletarLeitos(tblId, lista) {
  const obj = {};
  const tbl = document.getElementById(tblId);
  lista.forEach(esp => {
    const exEl  = tbl ? [...tbl.querySelectorAll('.leito-ex')].find(e  => e.dataset.leito === esp) : null;
    const susEl = tbl ? [...tbl.querySelectorAll('.leito-sus')].find(e => e.dataset.leito === esp) : null;
    obj[esp] = { existente: exEl?.value||'0', sus: susEl?.value||'0' };
  });
  return obj;
}

function coletarDados() {
  const dados = {
    // Ficha 1
    f1_operacao: g('f1_operacao'), f1_cnes: g('f1_cnes'), f1_tipo_estab: g('f1_tipo_estab'),
    f1_cnpj: g('f1_cnpj'), f1_nome_empresarial: g('f1_nome_empresarial'), f1_fantasia: g('f1_fantasia'),
    f1_cep: g('f1_cep'), f1_endereco: g('f1_endereco'), f1_numero: g('f1_numero'),
    f1_complemento: g('f1_complemento'), f1_bairro: g('f1_bairro'), f1_telefone: g('f1_telefone'),
    f1_email: g('f1_email'), f1_administrador: g('f1_administrador'), f1_conselho_rt: g('f1_conselho_rt'),
    f1_alvara: g('f1_alvara'), f1_alvara_data: g('f1_alvara_data'), f1_alvara_orgao: g('f1_alvara_orgao'),
    // Ficha 2
    f2_esfera: g('f2_esfera'), f2_ensino: g('f2_ensino'), f2_hierarquia: g('f2_hierarquia'),
    f2_fluxo_clientela: g('f2_fluxo_clientela'), f2_convenio: g('f2_convenio'), f2_turno: g('f2_turno'),
    f2_dias_func: g('f2_dias_func'), f2_horas_func: g('f2_horas_func'),
    // Ficha 6 — UE
    f6_ue_med: g('f6_ue_med'), f6_ue_odonto: g('f6_ue_odonto'),
    f6_triagem_ped: g('f6_triagem_ped'), f6_triagem_fem: g('f6_triagem_fem'),
    f6_triagem_masc: g('f6_triagem_masc'), f6_triagem_indf: g('f6_triagem_indf'),
    f6_ue_curativo: g('f6_ue_curativo'), f6_ue_gesso: g('f6_ue_gesso'),
    f6_higienizacao: g('f6_higienizacao'), f6_ue_peq_cir: g('f6_ue_peq_cir'),
    f6_repouso_ped_salas: g('f6_repouso_ped_salas'), f6_repouso_ped_leitos: g('f6_repouso_ped_leitos'),
    f6_repouso_fem_salas: g('f6_repouso_fem_salas'), f6_repouso_fem_leitos: g('f6_repouso_fem_leitos'),
    f6_repouso_masc_salas: g('f6_repouso_masc_salas'), f6_repouso_masc_leitos: g('f6_repouso_masc_leitos'),
    f6_repouso_indf_salas: g('f6_repouso_indf_salas'), f6_repouso_indf_leitos: g('f6_repouso_indf_leitos'),
    // Ficha 6 — Ambulatório
    f6_amb_basicas: g('f6_amb_basicas'), f6_amb_especializadas: g('f6_amb_especializadas'),
    f6_amb_indf: g('f6_amb_indf'), f6_outros_nmed: g('f6_outros_nmed'),
    f6_odonto_amb: g('f6_odonto_amb'), f6_peq_cirurgia_amb: g('f6_peq_cirurgia_amb'),
    f6_enfermagem: g('f6_enfermagem'), f6_imunizacao: g('f6_imunizacao'),
    f6_nebulizacao: g('f6_nebulizacao'), f6_gesso_amb: g('f6_gesso_amb'),
    f6_curativo_amb: g('f6_curativo_amb'), f6_cirurgia_amb: g('f6_cirurgia_amb'),
    // Ficha 6 — Hospitalar
    f6_cirurgia: g('f6_cirurgia'), f6_recuperacao: g('f6_recuperacao'),
    f6_recuperacao_leitos: g('f6_recuperacao_leitos'), f6_cirurgia_amb_cc: g('f6_cirurgia_amb_cc'),
    f6_preparto_qtd: g('f6_preparto_qtd'), f6_preparto_leitos: g('f6_preparto_leitos'),
    f6_parto_normal: g('f6_parto_normal'), f6_curetagem: g('f6_curetagem'),
    f6_cirurgia_co: g('f6_cirurgia_co'),
    f6_leitos_rn_normal: g('f6_leitos_rn_normal'), f6_leitos_rn_patologico: g('f6_leitos_rn_patologico'),
    f6_leitos_alojamento: g('f6_leitos_alojamento'),
    // Ficha 4
    f4_pnass_avaliado: g('f4_pnass_avaliado'), f4_pnass_data: g('f4_pnass_data'),
    f4_pnass_nao_atendeu: gc('f4_pnass_nao_atendeu'),
    f4_pnass_nivel1: gc('f4_pnass_nivel1'), f4_pnass_nivel2: gc('f4_pnass_nivel2'),
    f4_pnass_nivel3: gc('f4_pnass_nivel3'),
    f4_acreditado: g('f4_acreditado'), f4_acreditacao_data: g('f4_acreditacao_data'),
    f4_adesao_filantropico: g('f4_adesao_filantropico'),
    f4_internet: g('f4_internet'),
    f4_tipo_conexao: (document.querySelector('input[name="conexao"]:checked')?.value) || '',
    f4_telefonia_fixa: g('f4_telefonia_fixa'), f4_telefonia_movel: g('f4_telefonia_movel'),
    f17_outros_res: g('f17_outros_res'),
    // Listas
    atendimento_prestado: [...document.querySelectorAll('.atendimento:checked')].map(c => c.value),
    residuos: [...document.querySelectorAll('.residuo:checked')].map(c => c.value),
    // Declaração
    d_razao: g('d_razao'), d_cnpj: g('d_cnpj'), d_fantasia: g('d_fantasia'),
    d_rua: g('d_rua'), d_bairro: g('d_bairro'), d_cep: g('d_cep'),
    d_rt_nome: g('d_rt_nome'), d_profissao: g('d_profissao'),
    d_rg: g('d_rg'), d_rg_orgao: g('d_rg_orgao'), d_cpf: g('d_cpf'),
    d_conselho: g('d_conselho'), d_tipo_estab: g('d_tipo_estab'),
    d_atv_principal: g('d_atv_principal'), d_atv_sec: g('d_atv_sec'),
    d_horarios: g('d_horarios'), d_dia: g('d_dia'), d_mes: g('d_mes'), d_ano: g('d_ano'),
    // Complexos
    apoio: {}, eq_diag_imagem: [], eq_infra: [], eq_opticos: [],
    eq_odonto: [], eq_outros: [], eq_audio: [],
    metodos: {}, manutencao: {},
    leitos_cirurgicos: {}, leitos_obstetricos: {}, leitos_pediatricos: {},
    leitos_clinicos: {}, leitos_outras: {}, leitos_hospital_dia: {}, leitos_complementares: {},
    profissionais, especializacoes,
  };

  // Comissões
  comissoesF4.forEach(([cod]) => { dados[`f4_${cod}`] = g(`f4_${cod}`); });

  // Apoio
  servicosApoio.forEach((_, i) => {
    const s = document.getElementById(`apoio_${i}`);
    if (s) dados.apoio[i+1] = s.value;
  });

  // Equipamentos
  function colEquip(key, lista) {
    return lista.map((_, i) => ({
      possui: document.querySelector(`.eq-possui[data-key="${key}"][data-idx="${i}"]`)?.checked || false,
      qtd:    parseInt(document.querySelector(`.eq-qtd[data-key="${key}"][data-idx="${i}"]`)?.value || 0),
    }));
  }
  dados.eq_diag_imagem = colEquip('diag',    equipDiag);
  dados.eq_infra       = colEquip('infra',   equipInfra);
  dados.eq_opticos     = colEquip('opticos', equipOpticos);
  dados.eq_odonto      = colEquip('odonto',  equipOdonto);
  dados.eq_outros      = colEquip('outros',  equipOutros);
  dados.eq_audio       = colEquip('audio',   equipAudio);

  // Métodos
  document.querySelectorAll('.metodo-sn').forEach(sel => {
    const tipo = sel.dataset.tipo, cod = sel.dataset.cod;
    const ex = document.querySelector(`.metodo-ex[data-tipo="${tipo}"][data-cod="${cod}"]`)?.value || 0;
    const us = document.querySelector(`.metodo-us[data-tipo="${tipo}"][data-cod="${cod}"]`)?.value || 0;
    if (tipo === 'graficos')   dados.metodos[cod]    = { simnao: sel.value, existente: ex, uso: us };
    if (tipo === 'manutencao') dados.manutencao[cod] = { simnao: sel.value, existente: ex, uso: us };
  });

  // Leitos
  dados.leitos_cirurgicos     = coletarLeitos('tbl_leitos_cirurgicos',     leitosCir);
  dados.leitos_obstetricos    = coletarLeitos('tbl_leitos_obstetricos',    leitosObs);
  dados.leitos_pediatricos    = coletarLeitos('tbl_leitos_pediatricos',    leitosPed);
  dados.leitos_clinicos       = coletarLeitos('tbl_leitos_clinicos',       leitosClin);
  dados.leitos_outras         = coletarLeitos('tbl_leitos_outras',         leitosOut);
  dados.leitos_hospital_dia   = coletarLeitos('tbl_leitos_hospital_dia',   leitosHD);
  dados.leitos_complementares = coletarLeitos('tbl_leitos_complementares', leitosComp);

  return dados;
}

// ── Submit helpers ────────────────────────────────────────────────────────────
function formDataFromDados(dados) {
  const fd = new FormData();
  for (const k in dados) {
    if (Array.isArray(dados[k]) || (typeof dados[k] === 'object' && dados[k] !== null))
      fd.append(k, JSON.stringify(dados[k]));
    else
      fd.append(k, dados[k]);
  }
  for (const f of document.getElementById('anexos').files) fd.append('anexos', f);
  return fd;
}

function mostrarStatus(msg, ok) {
  document.getElementById('statusMsg').innerHTML =
    `<div class="status ${ok?'ok':'err'}">${msg}</div>`;
}

// ── CEP auto-fill via ViaCEP ─────────────────────────────────────────────────
function setupCepAutoFill() {
  const cepEl = document.getElementById('f1_cep');
  if (!cepEl) return;
  cepEl.addEventListener('blur', async function() {
    const cep = this.value.replace(/\D/g, '');
    if (cep.length !== 8) return;
    try {
      const resp = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
      const data = await resp.json();
      if (data.erro) return;
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el && val) el.value = val;
      };
      setVal('f1_endereco', data.logradouro);
      setVal('f1_bairro', data.bairro);
      setVal('f1_complemento', data.complemento);
    } catch(e) { /* ViaCEP indisponível — ignora */ }
  });
}

// ── Validação de campos obrigatórios ────────────────────────────────────────
function limparErros() {
  document.querySelectorAll('.field-error').forEach(el => el.classList.remove('field-error'));
  document.querySelectorAll('.field-error-msg').forEach(el => el.remove());
}

function marcarErro(campoId, msg) {
  const el = document.getElementById(campoId);
  if (!el) return;
  const fg = el.closest('.fg');
  if (fg) {
    fg.classList.add('field-error');
    if (msg && !fg.querySelector('.field-error-msg')) {
      const span = document.createElement('span');
      span.className = 'field-error-msg';
      span.textContent = msg;
      fg.appendChild(span);
    }
  }
}

function validarCamposObrigatorios() {
  limparErros();
  const erros = [];

  // 1. CNPJ/CPF
  const cnpj = g('f1_cnpj').trim();
  if (!cnpj) { marcarErro('f1_cnpj', 'Obrigatório'); erros.push('CNPJ/CPF'); }

  // 2. Nome Empresarial e Fantasia
  const nomeEmp = g('f1_nome_empresarial').trim();
  if (!nomeEmp) { marcarErro('f1_nome_empresarial', 'Obrigatório'); erros.push('Nome Empresarial'); }
  const fantasia = g('f1_fantasia').trim();
  if (!fantasia) { marcarErro('f1_fantasia', 'Obrigatório'); erros.push('Nome Fantasia'); }

  // 3. CEP
  const cep = g('f1_cep').replace(/\D/g, '').trim();
  if (!cep || cep.length < 8) { marcarErro('f1_cep', 'Obrigatório'); erros.push('CEP'); }

  // 4. Administrador/RT e Registro Conselho
  const admin = g('f1_administrador').trim();
  if (!admin) { marcarErro('f1_administrador', 'Obrigatório'); erros.push('Administrador/RT'); }
  const conselhoRt = g('f1_conselho_rt').trim();
  if (!conselhoRt) { marcarErro('f1_conselho_rt', 'Obrigatório'); erros.push('Registro do Conselho do RT'); }

  // 5. Turno, Dias e Horários
  const turno = g('f2_turno');
  if (!turno) { marcarErro('f2_turno', 'Obrigatório'); erros.push('Turno de Atendimento'); }
  const dias = g('f2_dias_func').trim();
  if (!dias) { marcarErro('f2_dias_func', 'Obrigatório'); erros.push('Dias de Funcionamento'); }
  const horas = g('f2_horas_func').trim();
  if (!horas) { marcarErro('f2_horas_func', 'Obrigatório'); erros.push('Horários'); }

  // 6. Ambulatório — pelo menos um tipo de sala com quantidade > 0
  const ambIds = ['f6_amb_basicas','f6_amb_especializadas','f6_amb_indf','f6_outros_nmed',
                  'f6_odonto_amb','f6_peq_cirurgia_amb','f6_enfermagem','f6_imunizacao',
                  'f6_nebulizacao','f6_gesso_amb','f6_curativo_amb','f6_cirurgia_amb'];
  const temAmb = ambIds.some(id => parseInt(document.getElementById(id)?.value || 0) > 0);
  if (!temAmb) {
    erros.push('Ambulatório (Ficha 6): informe ao menos um tipo de sala com quantidade > 0');
    // Highlight the first amb field
    for (const id of ambIds) {
      const el = document.getElementById(id);
      if (el) { el.style.borderColor = 'var(--vm)'; el.style.boxShadow = '0 0 0 3px rgba(185,28,28,.1)'; }
    }
  }

  // 7. Comunicação e Informática
  const internet = g('f4_internet');
  if (!internet) { marcarErro('f4_internet', 'Obrigatório'); erros.push('Internet'); }
  const conexao = document.querySelector('input[name="conexao"]:checked');
  if (!conexao) {
    const fgConexao = document.querySelector('.conexao-grid')?.closest('.fg');
    if (fgConexao) fgConexao.classList.add('field-error');
    erros.push('Tipo de Conexão');
  }
  const telFixa = g('f4_telefonia_fixa');
  if (!telFixa) { marcarErro('f4_telefonia_fixa', 'Obrigatório'); erros.push('Telefonia Fixa'); }
  const telMovel = g('f4_telefonia_movel');
  if (!telMovel) { marcarErro('f4_telefonia_movel', 'Obrigatório'); erros.push('Telefonia Móvel'); }

  // 8. SAME (Serviço de Apoio #1)
  const sameEl = document.getElementById('apoio_0');
  if (sameEl && sameEl.value === 'Nao') {
    marcarErro('apoio_0', 'SAME deve ser informado');
    erros.push('SAME (Ficha 7)');
  }

  // 9. Resíduos/Rejeitos — ao menos um tipo
  const residuos = [...document.querySelectorAll('.residuo:checked')].map(c => c.value).filter(v => v !== 'Nenhum');
  if (residuos.length === 0) {
    const residuosDiv = document.getElementById('residuos_opcoes');
    if (residuosDiv) residuosDiv.style.outline = '2px solid var(--vm)';
    erros.push('Resíduos/Rejeitos (Seção 30)');
  }

  // 10. Centrais de Ar Condicionado — equip infra deve ter ao menos 'Controle Ambiental/Ar-condicionado Central'
  const arCondPossui = document.querySelector('.eq-possui[data-key="infra"][data-idx="0"]');
  if (arCondPossui && !arCondPossui.checked) {
    erros.push('Centrais de Ar Condicionado (Ficha 29.2)');
    arCondPossui.style.outline = '2px solid var(--vm)';
  }

  // 11. Profissionais — CPF, Registro Conselho, CH, CBO, Vínculo
  profissionais.forEach((p, idx) => {
    const idxStr = String(idx);
    const cpf = (document.querySelector(`.prof-cpf[data-idx="${idxStr}"]`)?.value || '').trim();
    if (!cpf) { marcarErro(null); const el = document.querySelector(`.prof-cpf[data-idx="${idxStr}"]`); if (el) { el.style.borderColor = 'var(--vm)'; } erros.push(`Profissional ${idx+1}: CPF`); }
    const cons = (document.querySelector(`.prof-cons[data-idx="${idxStr}"]`)?.value || '').trim();
    if (!cons) { const el = document.querySelector(`.prof-cons[data-idx="${idxStr}"]`); if (el) { el.style.borderColor = 'var(--vm)'; } erros.push(`Profissional ${idx+1}: Registro Conselho`); }
    const ch = (document.querySelector(`.prof-ch[data-idx="${idxStr}"]`)?.value || '').trim();
    if (!ch) { const el = document.querySelector(`.prof-ch[data-idx="${idxStr}"]`); if (el) { el.style.borderColor = 'var(--vm)'; } erros.push(`Profissional ${idx+1}: C.H. Semanal`); }
    const cbo = (document.querySelector(`.prof-profissao[data-idx="${idxStr}"]`)?.value || '').trim();
    if (!cbo) { const el = document.querySelector(`.prof-profissao[data-idx="${idxStr}"]`); if (el) { el.style.borderColor = 'var(--vm)'; } erros.push(`Profissional ${idx+1}: CBO`); }
    const vinculo = (document.querySelector(`.prof-estab[data-idx="${idxStr}"]`)?.value || '').trim();
    if (!vinculo) { const el = document.querySelector(`.prof-estab[data-idx="${idxStr}"]`); if (el) { el.style.borderColor = 'var(--vm)'; } erros.push(`Profissional ${idx+1}: Vínculo com Estabelecimento`); }
  });

  return erros;
}

async function gerarPDF() {
  const erros = validarCamposObrigatorios();
  if (erros.length > 0) {
    mostrarStatus('⚠️ Preencha os campos obrigatórios: ' + erros.slice(0, 8).join(', ') + (erros.length > 8 ? ` e mais ${erros.length - 8}...` : ''), false);
    return;
  }
  const fd = formDataFromDados(coletarDados());
  const r  = await fetch('/gerar-pdf', { method: 'POST', body: fd });
  if (r.ok) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await r.blob());
    a.download = 'extrato_cnes.pdf';
    a.click();
    mostrarStatus('PDF gerado e baixado com sucesso.', true);
  } else {
    const ct = r.headers.get('content-type') || '';
    let msg = 'Erro ao gerar PDF';
    if (ct.includes('application/json')) { const j = await r.json(); msg = j.status || msg; }
    else { msg += ': ' + (await r.text()); }
    mostrarStatus('⚠️ ' + msg, false);
  }
}

async function previewPDF() {
  const erros = validarCamposObrigatorios();
  if (erros.length > 0) {
    mostrarStatus('⚠️ Preencha os campos obrigatórios: ' + erros.slice(0, 8).join(', ') + (erros.length > 8 ? ` e mais ${erros.length - 8}...` : ''), false);
    return;
  }
  const fd = formDataFromDados(coletarDados());
  const r  = await fetch('/gerar-pdf', { method: 'POST', body: fd });
  if (r.ok) { window.open(URL.createObjectURL(await r.blob()), '_blank'); }
  else {
    const ct = r.headers.get('content-type') || '';
    let msg = 'Erro na pré-visualização';
    if (ct.includes('application/json')) { const j = await r.json(); msg = j.status || msg; }
    mostrarStatus('⚠️ ' + msg, false);
  }
}

async function enviarEmail() {
  const erros = validarCamposObrigatorios();
  if (erros.length > 0) {
    mostrarStatus('⚠️ Preencha os campos obrigatórios: ' + erros.slice(0, 8).join(', ') + (erros.length > 8 ? ` e mais ${erros.length - 8}...` : ''), false);
    return;
  }
  const fd = formDataFromDados(coletarDados());
  const pw = document.getElementById('progWrap');
  const pb = document.getElementById('progBar');
  const ps = document.getElementById('progStep');
  pw.style.display = 'block'; pb.style.width = '0%';
  const passos = ['Preparando dados…','Gerando PDF…','Anexando arquivos…','Conectando…','Enviando…','Concluído!'];
  for (const [i, txt] of passos.slice(0,-1).entries()) {
    ps.textContent = txt; pb.style.width = ((i+1)*16) + '%';
    await new Promise(r => setTimeout(r, 320));
  }
  const resp = await fetch('/enviar-email', { method: 'POST', body: fd });
  const ct   = resp.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    const res = await resp.json();
    const ok  = res.status.includes('sucesso');
    ps.textContent = ok ? passos[5] : 'Erro no envio.';
    pb.style.width = ok ? '100%' : '80%';
    mostrarStatus(res.status, ok);
  } else {
    mostrarStatus('Resposta inesperada do servidor.', false);
  }
  setTimeout(() => { pw.style.display='none'; pb.style.width='0%'; ps.textContent=''; }, 4500);
}

// ── Inicialização ─────────────────────────────────────────────────────────────
function initDataDeclaracao() {
  const today = new Date();
  const meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                 'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  document.getElementById('d_dia').value = today.getDate();
  document.getElementById('d_ano').value = today.getFullYear();
  const mesEl = document.getElementById('d_mes');
  for (let i = 0; i < mesEl.options.length; i++) {
    if (mesEl.options[i].text === meses[today.getMonth()]) { mesEl.selectedIndex = i; break; }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  initDataDeclaracao();
  setupCepAutoFill();

  // Renderizações iniciais
  renderEquip('eq_diag',    equipDiag,    'diag');
  renderEquip('eq_infra',   equipInfra,   'infra');
  renderEquip('eq_opticos', equipOpticos, 'opticos');
  renderEquip('eq_odonto',  equipOdonto,  'odonto');
  renderEquip('eq_outros',  equipOutros,  'outros');
  renderEquip('eq_audio',   equipAudio,   'audio');
  renderMetodos('metodos_graficos', metGraficos, 'graficos');
  renderMetodos('manutencao_vida',  manutVida,   'manutencao');
  renderApoio(); renderResiduos(); renderAtendimento(); renderComissoes();

  renderLeitos('tbl_leitos_cirurgicos',     leitosCir,  '32.1 — Leitos Cirúrgicos');
  renderLeitos('tbl_leitos_obstetricos',    leitosObs,  '32.2 — Leitos Obstétricos');
  renderLeitos('tbl_leitos_pediatricos',    leitosPed,  '32.3 — Leitos Pediátricos');
  renderLeitos('tbl_leitos_clinicos',       leitosClin, '32.4 — Leitos Clínicos');
  renderLeitos('tbl_leitos_outras',         leitosOut,  '32.5 — Outras Especialidades');
  renderLeitos('tbl_leitos_hospital_dia',   leitosHD,   '32.6 — Hospital Dia');
  renderLeitos('tbl_leitos_complementares', leitosComp, '33 — Leitos Complementares');

  renderProfissionais(); renderEspecializacoes();
  if (!profissionais.length)   adicionarProfissional();
  if (!especializacoes.length) adicionarEspecializacao();

  // Modal GOV.br
  document.getElementById('modalGovBg').addEventListener('click', function(e) {
    if (e.target === this) fecharModalGov();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') fecharModalGov(); });

  // Main tabs
  const mainBtns  = [...document.querySelectorAll('.main-tab')];
  const mainPanes = [...document.querySelectorAll('.tab-pane')];
  mainBtns.forEach(btn => btn.addEventListener('click', () => {
    mainBtns.forEach(b  => b.classList.remove('active'));
    mainPanes.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.main)?.classList.add('active');
    const firstPill = document.querySelector(`#${btn.dataset.main} > .pill-tabs > .pill-tab`);
    if (firstPill) firstPill.click();
  }));

  // Pill tabs genéricos
  document.querySelectorAll('.tab-pane').forEach(pane => {
    const pills = [...pane.querySelectorAll(':scope > .pill-tabs > .pill-tab')];
    pills.forEach(btn => btn.addEventListener('click', () => {
      pills.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      pane.querySelectorAll(':scope > .pill-pane').forEach(p => p.classList.remove('active'));
      document.getElementById(btn.dataset.pill)?.classList.add('active');
    }));
  });

  // Ficha 6 sub-tabs
  const f6Btns = [...document.querySelectorAll('#f6-subtabs .pill-tab')];
  f6Btns.forEach(btn => btn.addEventListener('click', () => {
    f6Btns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.f6-sec').forEach(s => s.style.display = 'none');
    const sec = document.getElementById(`f6-${btn.dataset.f6}`);
    if (sec) sec.style.display = 'block';
  }));

  // Ficha 19 sub-tabs
  const f19Btns = [...document.querySelectorAll('#f19-pills .pill-tab')];
  f19Btns.forEach(btn => btn.addEventListener('click', () => {
    f19Btns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.f19-sec').forEach(s => s.style.display = 'none');
    const sec = document.getElementById(`f19-${btn.dataset.f19}`);
    if (sec) sec.style.display = 'block';
  }));

  // Botões de ação
  document.getElementById('btnPreview').onclick = previewPDF;
  document.getElementById('btnAnexos').onclick  = () => document.getElementById('anexos').click();
  document.getElementById('btnPDF').onclick     = gerarPDF;
  document.getElementById('btnEmail').onclick   = enviarEmail;
  document.getElementById('anexos').addEventListener('change', e =>
    document.getElementById('anexosInfo').textContent = `${e.target.files.length} arquivo(s) selecionado(s).`
  );
});
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────────────────────
#  PARSE FORM
# ─────────────────────────────────────────────────────────────
JSON_KEYS = {
    'eq_diag_imagem','eq_infra','eq_opticos','eq_odonto','eq_outros','eq_audio',
    'metodos','manutencao','leitos_cirurgicos','leitos_obstetricos','leitos_pediatricos',
    'leitos_clinicas','leitos_outras','leitos_hospital_dia','leitos_complementares',
    'profissionais','especializacoes','apoio','leitos_clinicos',
}

def _parse_form(request):
    dados = {}
    for key in request.form:
        if key in JSON_KEYS:
            try:
                dados[key] = json.loads(request.form[key])
            except:
                dados[key] = {}
        else:
            dados[key] = request.form[key]
    for lst in ('atendimento_prestado', 'residuos'):
        v = dados.get(lst)
        if isinstance(v, str):
            try:
                dados[lst] = json.loads(v)
            except:
                dados[lst] = []
        elif lst not in dados:
            dados[lst] = []
    return dados

def _salvar_anexos(request):
    paths = []
    for f in request.files.getlist('anexos'):
        if f and f.filename:
            p = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename))
            f.save(p)
            paths.append(p)
    return paths


# ─────────────────────────────────────────────────────────────
#  VALIDAÇÃO SERVER-SIDE
# ─────────────────────────────────────────────────────────────
def _validar_dados(dados):
    """Valida campos obrigatórios no servidor. Retorna lista de erros vazia se OK."""
    erros = []
    _s = lambda v: str(v or '').strip()

    # 1. CNPJ/CPF
    if not _s(dados.get('f1_cnpj')):
        erros.append('CNPJ/CPF')

    # 2. Nome Empresarial e Fantasia
    if not _s(dados.get('f1_nome_empresarial')):
        erros.append('Nome Empresarial')
    if not _s(dados.get('f1_fantasia')):
        erros.append('Nome Fantasia')

    # 3. CEP
    cep = re.sub(r'\D', '', _s(dados.get('f1_cep')))
    if len(cep) < 8:
        erros.append('CEP')

    # 4. Administrador/RT e Registro Conselho
    if not _s(dados.get('f1_administrador')):
        erros.append('Administrador/RT')
    if not _s(dados.get('f1_conselho_rt')):
        erros.append('Registro do Conselho do RT')

    # 5. Turno, Dias e Horários
    if not _s(dados.get('f2_turno')):
        erros.append('Turno de Atendimento')
    if not _s(dados.get('f2_dias_func')):
        erros.append('Dias de Funcionamento')
    if not _s(dados.get('f2_horas_func')):
        erros.append('Horários')

    # 6. Ambulatório — ao menos um tipo de sala > 0
    amb_ids = ['f6_amb_basicas','f6_amb_especializadas','f6_amb_indf',
               'f6_outros_nmed','f6_odonto_amb','f6_peq_cirurgia_amb',
               'f6_enfermagem','f6_imunizacao','f6_nebulizacao',
               'f6_gesso_amb','f6_curativo_amb','f6_cirurgia_amb']
    tem_amb = any(int(dados.get(k, 0) or 0) > 0 for k in amb_ids)
    if not tem_amb:
        erros.append('Ambulatório (Ficha 6: ao menos uma sala)')

    # 7. Comunicação e Informática
    if not _s(dados.get('f4_internet')):
        erros.append('Internet')
    if not _s(dados.get('f4_tipo_conexao')):
        erros.append('Tipo de Conexão')
    if not _s(dados.get('f4_telefonia_fixa')):
        erros.append('Telefonia Fixa')
    if not _s(dados.get('f4_telefonia_movel')):
        erros.append('Telefonia Móvel')

    # 8. SAME (Serviço de Apoio #1)
    apoio = dados.get('apoio', {})
    if isinstance(apoio, dict):
        same_val = _s(apoio.get('1', apoio.get(1, '')))
        if same_val in ('', 'Nao', 'Não'):
            erros.append('SAME (Ficha 7)')

    # 9. Resíduos/Rejeitos — ao menos um tipo (excluindo 'Nenhum')
    residuos = dados.get('residuos', [])
    if isinstance(residuos, list):
        residuos_validos = [r for r in residuos if r and r != 'Nenhum']
        if not residuos_validos:
            erros.append('Resíduos/Rejeitos (Seção 30)')

    # 10. Centrais de Ar Condicionado — eq_infra[0].possui deve ser True
    eq_infra = dados.get('eq_infra', [])
    if isinstance(eq_infra, list) and len(eq_infra) > 0:
        ar_cond = eq_infra[0]
        if isinstance(ar_cond, dict) and not ar_cond.get('possui'):
            erros.append('Centrais de Ar Condicionado (Ficha 29.2)')
    else:
        erros.append('Centrais de Ar Condicionado (Ficha 29.2)')

    # 11. Profissionais — CPF, Registro Conselho, CH, CBO, Vínculo
    profs = dados.get('profissionais', [])
    if isinstance(profs, list):
        for i, p in enumerate(profs, 1):
            if not isinstance(p, dict):
                continue
            if not _s(p.get('cpf')):
                erros.append(f'Profissional {i}: CPF')
            if not _s(p.get('conselho')):
                erros.append(f'Profissional {i}: Registro Conselho')
            if not _s(p.get('ch')):
                erros.append(f'Profissional {i}: C.H. Semanal')
            if not _s(p.get('profissao')):
                erros.append(f'Profissional {i}: CBO')
            if not _s(p.get('estabelecimento')):
                erros.append(f'Profissional {i}: Vínculo com Estabelecimento')

    return erros


# ─────────────────────────────────────────────────────────────
#  ROTAS FLASK
# ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE,
        EQUIP_DIAG_IMAGEM=EQUIP_DIAG_IMAGEM, EQUIP_INFRA=EQUIP_INFRA,
        EQUIP_OPTICOS=EQUIP_OPTICOS,          EQUIP_ODONTO=EQUIP_ODONTO,
        EQUIP_OUTROS=EQUIP_OUTROS,            EQUIP_AUDIO=EQUIP_AUDIO,
        METODOS_GRAFICOS=METODOS_GRAFICOS,    MANUTENCAO_VIDA=MANUTENCAO_VIDA,
        SERVICOS_APOIO=SERVICOS_APOIO,        OPCOES_REJEITOS=OPCOES_REJEITOS,
        LEITOS_CIRURGICOS=LEITOS_CIRURGICOS,  LEITOS_OBSTETRICOS=LEITOS_OBSTETRICOS,
        LEITOS_PEDIATRICOS=LEITOS_PEDIATRICOS,LEITOS_CLINICOS=LEITOS_CLINICOS,
        LEITOS_OUTRAS=LEITOS_OUTRAS,          LEITOS_HOSPITAL_DIA=LEITOS_HOSPITAL_DIA,
        LEITOS_COMPLEMENTARES=LEITOS_COMPLEMENTARES,
        SERVICOS_CBO=SERVICOS_CBO,            CBO_DICT=cbo_dict,
        COMISSOES_F4=COMISSOES_F4,            datetime=datetime,
    )

@app.route('/logo-prefeitura')
def logo_prefeitura():
    p = encontrar_arquivo_local('logo_prefeitura.png','logo_prefeitura.jpg','logo_prefeitura.jpeg')
    return send_file(p) if p else ('', 404)

@app.route('/logo-jarvis')
def logo_jarvis():
    p = encontrar_arquivo_local('logo_jarvis.png','logo_jarvis.jpg','logo_jarvis.jpeg')
    return send_file(p) if p else ('', 404)

@app.route('/logo-cnes')
def logo_cnes():
    p = encontrar_arquivo_local('logo_cnes.png','logo_cnes.jpg','logo_cnes.jpeg')
    return send_file(p) if p else ('', 404)

@app.route('/gerar-pdf', methods=['POST'])
def rota_gerar_pdf():
    dados  = _parse_form(request)
    # Validação server-side
    erros = _validar_dados(dados)
    if erros:
        msg = 'Campos obrigatórios não preenchidos: ' + ', '.join(erros[:8])
        if len(erros) > 8:
            msg += f' e mais {len(erros) - 8}...'
        return jsonify({'status': msg}), 400
    anexos = _salvar_anexos(request)
    fd, path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    try:
        gerar_pdf_completo(dados, path, anexos)
        return send_file(path, as_attachment=True, download_name='extrato_cnes.pdf')
    finally:
        for a in anexos:
            try: os.unlink(a)
            except: pass

# ── Rate limit de envio (anti-spam: intervalo mínimo + teto por hora) ──
_ENVIOS_RECENTES = []


def _rate_limit_ok():
    """Limita envios: intervalo mínimo entre e-mails e teto por hora.
    Leitura via env a cada chamada (facilita teste e ajuste sem reiniciar)."""
    if os.environ.get("JARVIS_RATE_LIMIT", "1") != "1":
        return True
    intervalo = float(os.environ.get("JARVIS_INTERVALO_MIN", "5"))
    teto = int(os.environ.get("JARVIS_LIMITE_HORA", "30"))
    agora = _time.time()
    while _ENVIOS_RECENTES and agora - _ENVIOS_RECENTES[0] > 3600:
        _ENVIOS_RECENTES.pop(0)
    if len(_ENVIOS_RECENTES) >= teto:
        return False
    if _ENVIOS_RECENTES and agora - _ENVIOS_RECENTES[-1] < intervalo:
        return False
    _ENVIOS_RECENTES.append(agora)
    return True


@app.route('/enviar-email', methods=['POST'])
def rota_enviar_email():
    if not _rate_limit_ok():
        return jsonify({"status": "Limite de envios atingido — aguarde alguns minutos e tente novamente."}), 429
    dados  = _parse_form(request)
    # Validação server-side
    erros = _validar_dados(dados)
    if erros:
        msg = 'Campos obrigatórios não preenchidos: ' + ', '.join(erros[:8])
        if len(erros) > 8:
            msg += f' e mais {len(erros) - 8}...'
        return jsonify({'status': msg}), 400
    anexos = _salvar_anexos(request)
    fd, path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    bck_path = None
    try:
        gerar_pdf_completo(dados, path, anexos)
        # .BCK SEMPRE gerado em oculto e anexado automaticamente (acesso apenas
        # da GECAV) — o cadastro serve justamente para gerar a numeração CNES
        # de estabelecimentos novos, então não se exige CNES preenchido.
        bfd, bck_path = tempfile.mkstemp(suffix='.bck')
        os.close(bfd)
        with open(bck_path, 'wb') as f:
            f.write(gerar_bck_bytes(dados))
        ok, msg = enviar_email_com_pdf(dados, path, anexos, bck_path)
        if ok:
            status = msg   # ex.: "E-mail enviado com sucesso (com .BCK 34 KB para a GECAV)"
        else:
            status = f"Falha no envio: {msg}"
    except Exception as e:
        status = f"Erro interno: {e}"
        import traceback; traceback.print_exc()
    finally:
        try: os.unlink(path)
        except: pass
        if bck_path:
            try: os.unlink(bck_path)
            except: pass
        for a in anexos:
            try: os.unlink(a)
            except: pass
    return jsonify({"status": status})


# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    host  = os.environ.get("JARVIS_HOST", "127.0.0.1")
    porta = int(os.environ.get("JARVIS_PORT", "5000"))
    try:
        # Load the optional dependency dynamically so static analysis does not
        # require waitress to be installed in the current environment.
        import importlib
        serve = importlib.import_module("waitress").serve
        serve(app, host=host, port=porta)
    except ImportError:
        # sem waitress: dev server SEM debug (nunca expor o debugger na rede)
        app.run(host=host, port=porta, debug=False)

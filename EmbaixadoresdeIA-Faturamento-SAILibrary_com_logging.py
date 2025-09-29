#########################
# Importação de Pacotes #
#########################
import os
import json
import logging
import requests
import numpy as np
import pandas as pd
from tqdm import tqdm
from io import StringIO
from dotenv import load_dotenv

#####################
# Início do logging #
#####################
logging.basicConfig(
    filename='execucao_faturamento_sailibrary.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Início da execução do script.')

#######################################
# Função de Chamada da API do SAI APP #
#######################################
def calling_sai_api(api_key, prompt):

    url = "https://sai-library.saiapplications.com"
    headers = {"X-Api-Key": api_key}
    data = {
        "inputs": {
            "texto": prompt,
        }
    }
    
    response = requests.post(f"{url}/api/templates/68bafc2db10f56ceab913ac8/execute", json=data, headers=headers)

    return response.text

###############################
# Função de Criação de Prompt #
###############################
def generate_prompt(first_day_period, last_day_period, observation, holiday_calendar):
    
    prompt = f"""
    
    Considere o período de análise que começa no dia {first_day_period} e termina no dia {last_day_period}. Ambos os dias estão no formato "dia/mês/ano".
    
    Você vai receber um texto de observação que se encontra entre colchetes duplos [[...]] logo abaixo:
    [[{observation}]]
    
    Esse texto contém informações sobre a ausência de um trabalhador, por exemplo, férias, atestado médico, começo e fim de jornada de trabalho, podendo apresentar um determinado perído de dias e/ou apenas uma data.
    
    Para a sua informação:
        - férias: período de ausência do trabalaho que o trabalhador tem direito.
        - atestado: dia ou período de ausência do trabalhador por motivo de doença.
        - último dia: significa o último dia que o trabalhador trabalhou na empresa.
        - iniciou (ou qualquer variação da palavra início): significa o primeiro dia de trabalho do trabalhador.
    
    Sua função é identificar quantos dias úteis o trabalhador não trabalhou no período de análise, desde o primeiro dia ({first_day_period}) até o último dia ({last_day_period}).
    Considere as seguintes definições:
        - Os dias úteis são segundas, terças, quartas, quintas e sextas, exceto feriados.
        - Os sábados e domingos não são dias úteis.
        - Caso algum dia esteja no calendário abaixo de feriados você deve considerar esse dia como não sendo dia útil.

    Calendário de feriados que você deve considerar na sua análise, no formato CSV com separador "|": {holiday_calendar}
    
    Para a sua análise considere o seguinte raciocínio:
        - Identifique todos os dias úteis que há no período de análise entre os dias {first_day_period} e {last_day_period};
        - Identifique todos os dias que o trabalhador não trabalhou no texto de observação.
        - Dos dias que o trabalhador não trabalhou no texto de observação identifique os dias úteis que o trabalhador não trabalhou.
        - Dos dias úteis que o trabalhador não trabalhou, conte o total de dias úteis que o trabalhador não trabalhou no período de análise.
    
    Sua resposta deve ser no formato JSON, com os seguintes campos:
        - justificativa: escreva aqui o raciocínio que você considerou para a sua resposta
        - quant_dias_uteis: quantidade total de dias úteis que você calculou descontados do trabalhador    
             
    Muito importante: retorne apenas o JSON com os campos especificados. Não retorne outra informação indesejada.  
    """
    
    return prompt

#############
# Principal #
#############
def main():

    #####################################
    # Leitura das Variáveis de Ambiente #
    #####################################
    load_dotenv('variáveis-ambiente.env') 
    
    ################################
    # Leitura dos Dados de Entrada #
    ################################
    essential_columns = [
        'NOME',
        'PRIMEIRO DIA',
        'ÚLTIMO DIA',
        'HORA DIA',
        'OBSERVAÇÃO']
    
    df_essential_columns = pd.DataFrame({'colunas_essenciais': essential_columns})
    
    header = 0
    reading_success_condition = False

    logging_text = 'Tentativa de leitura do arquivo de entrada Excel.'
    logging.info(logging_text)
    print('\n')
    print(logging_text)
    
    while reading_success_condition == False:
        
        df = pd.read_excel(  
            os.getenv('NOME_ARQUIVO'),
            sheet_name=0,
            header=header)
    
        df.columns = [str(col).replace('\n', ' ').strip() for col in df.columns]
    
        if False not in df_essential_columns['colunas_essenciais'].isin(df.columns).values:
            logging.info('Todas as colunas essenciais foram encontradas no arquivo de entrada.')
            reading_success_condition = True
            logging_text = 'Leitura do arquivo de entrada feita com sucesso!'
            logging.info(logging_text)
            print('\n')
            print(logging_text)
    
        header += 1
    
    ##############################
    # Conversão da Colunas Horas #
    ##############################
    logging_text = 'Conversão das colunas Horas.'
    logging.info(logging_text)
    print('\n')
    print(logging_text)
    
    df['HORA DIA'] = df['HORA DIA'].dt.total_seconds() / 3600
    df['HORAS PREVISTAS MÊS'] = df['HORAS PREVISTAS MÊS'].dt.total_seconds() / 3600

    #################################################################
    # Relação de Feriados e Pontos Facultativos do Distrito Federal #
    #################################################################
    logging_text = 'Criação de calendário de feriados de Brasília.'
    logging.info(logging_text)
    print('\n')
    print(logging_text)
    
    prompt_holidays = f"""
    Eu quero a relação de feriados e pontos facultativos do Distrito Federal (Brasil) para o ano de {df['PRIMEIRO DIA'].unique()[0].year}.
    
    Quero esta relação no formato CSV, com separador "|", contendo os seguintes campos:
        - Data: data no formato YYYY-MM-DD
        - Dia da semana: domingo, segunda-feira, terça-feira, ..., sábado
        - Feriado: nome do feriado, por exemplo, Independência do Brasil
    
    Muito importante: somente retorne o CSV pedido. Não retorne qualquer outra informação não solicitada.
    """
    csv_brasilia_holiday_calendar = calling_sai_api(
        api_key=os.getenv('SAI_API_KEY'),
        prompt=prompt_holidays)
    
    ###########################################
    # Estimativa de Dias Úteis para Descontar #
    ###########################################
    logging_text = 'Processamento das observações utilizando o SAI App.'
    logging.info(logging_text)
    print('\n')
    print(logging_text)
    
    for index in tqdm(df.index):
    
        first_day_period = df.loc[index, 'PRIMEIRO DIA']
        last_day_period = df.loc[index, 'ÚLTIMO DIA']
        observation = df.loc[index, 'OBSERVAÇÃO']
    
        if (observation is None) or (observation is np.nan):
            justification = 'Nenhum dia para ser descontado.'
            number_days_to_discount = 0
    
        else:
            prompt = generate_prompt(
                first_day_period.strftime('%d/%m/%Y'),
                last_day_period.strftime('%d/%m/%Y'),
                observation,
                holiday_calendar=csv_brasilia_holiday_calendar)
    
            logging.info('Requisição HTTP.')
            response_ai_agent = calling_sai_api(
                api_key=os.getenv('SAI_API_KEY'),
                prompt=prompt)
    
            response_ai_agent = json.loads(response_ai_agent.replace("```json", '').replace("\n", '').replace("```", ''))
    
            justification = response_ai_agent['justificativa']
            number_days_to_discount = response_ai_agent['quant_dias_uteis']
    
        df.loc[index, 'JUSTIFICATIVA DOS DESCONTOS'] = justification
        df.loc[index, 'QUANTIDADE DIAS ÚTEIS PARA DESCONTAR'] = number_days_to_discount
    
    #############################################
    # Estimativa das Horas Úteis para Descontar #
    #############################################
    df['QUANTIDADE HORAS ÚTEIS PARA DESCONTAR'] = df['QUANTIDADE DIAS ÚTEIS PARA DESCONTAR'] * df['HORA DIA']

    ###################################################################
    # Descontando as horas não trabalhadas das horas pervistas do mês # 
    ###################################################################
    df['QTD HORAS (NORMAIS)'] = df['HORAS PREVISTAS MÊS'] - df['QUANTIDADE HORAS ÚTEIS PARA DESCONTAR']
    
    ##########################
    # Salvando os Resultados #
    ##########################
    logging.info('Salvando tabela de resultados.')
    df.to_excel('resultados_faturamento.xlsx', index=False)

    ####################################################################################################
    # Salvando a Relação de Feriados e Pontos Facultativos do Distrito Federal Considerados na Análise #
    ####################################################################################################    
    logging.info('Salvando tabela de calendário de feriados de Brasília.')
    csv_io = StringIO(csv_brasilia_holiday_calendar)
    df_brasilia_holiday_calendar = pd.read_csv(csv_io, sep="|")
    df_brasilia_holiday_calendar['Data'] = pd.to_datetime(df_brasilia_holiday_calendar['Data']).dt.strftime("%d/%m/%Y")
    df_brasilia_holiday_calendar.to_excel(f'calendário_considerado_de_feriados_e_pontos_faultativos_brasília_{df['PRIMEIRO DIA'].unique()[0].year}.xlsx', index=False)
    
    logging_text = 'Faturamento e calendário de feriados salvos com sucesso.'
    logging.info(logging_text)
    print('\n')
    print(logging_text)
    
#########################
# Execução do Principal #
#########################
try:
    main()
    print('\n')
    input('Programa executado com sucesso! Aperte qualquer tecla para sair.')
except Exception as error:
    print('\n')
    print("Ocorreu o seguinte erro:", error)
    print('\n')
    input('Aperte qualquer tecla para sair.')
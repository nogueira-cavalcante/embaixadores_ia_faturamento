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
def generate_prompt(first_day_period, last_day_period, observation):

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
    Considere os dias úteis todas as segundas, terças, quartas, quintas e sextas. Apenas os sábados e domingos não são dias úteis.

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
    
    ################################
    # Conversão da Coluna HORA DIA #
    ################################
    logging_text = 'Conversão da coluna HORA DIA.'
    logging.info(logging_text)
    print('\n')
    print(logging_text)
    
    df['HORA DIA'] = df['HORA DIA'].dt.total_seconds() / 3600
    
    ###########################################
    # Estimativa de Dias Úteis para Descontar #
    ###########################################
    logging_text = 'Processamento das observações utilizando o SAI App.'
    logging.info(logging_text)
    print(logging_text)
    print('\n')
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
                observation)
    
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
    
    ##########################
    # Salvando os Resultados #
    ##########################
    logging.info('Processamento de arquivo: resultados_faturamento.xlsx')
    df.to_excel('resultados_faturamento.xlsx', index=False)
    
    logging_text = 'Faturamento salvo com sucesso.'
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
# Forest CRM - Módulo Comercial

> ⚠️ **AVISO LEGAL E DE DIREITOS AUTORAIS - PROPRIEDADE EXCLUSIVA** ⚠️
> 
> Todo o código-fonte, arquitetura, design estrutural e lógicas de negócio contidos neste repositório são de **PROPRIEDADE EXCLUSIVA**. 
> 
> Este é um repositório de código fechado (Closed Source). **NENHUMA LICENÇA É CONCEDIDA** para o uso deste material. 
> 
> É terminantemente **PROIBIDO**:
> - Copiar, clonar ou reproduzir qualquer parte deste código.
> - Modificar, adaptar ou criar obras derivadas.
> - Distribuir, compartilhar ou comercializar o software.
> - Utilizar o código para fins pessoais, acadêmicos ou comerciais.
> 
> Qualquer uso, leitura ou execução deste sistema sem a **autorização prévia, expressa e por escrito** do proprietário constitui violação de propriedade intelectual e direitos autorais.

---

## 🌲 Sobre o Sistema
Sistema interno de gestão de funil comercial (CRM), arquitetado para a operação de captação e onboarding de propriedades da Forest. Interface desenvolvida em Streamlit atuando como front-end para um banco de dados relacional operado via Google Sheets API.

## ⚙️ Stack Tecnológica
- **Front-end:** Python / Streamlit
- **Back-end / Database:** Google Sheets (via `gspread`)
- **Integração:** Google Cloud Platform (GCP Service Accounts)

## 🔒 Segurança de Deploy
Este repositório não contém e não deve receber chaves de API, credenciais do Google Cloud ou variáveis de ambiente sensíveis. Todas as integrações são geridas estritamente no ambiente de servidor (Streamlit Secrets) com isolamento total da base de código.

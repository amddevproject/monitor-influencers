# Use a imagem base
FROM mcr.microsoft.com/playwright:v1.54.0-jammy

# Garantir que o pip esteja atualizado
RUN apt-get update && apt-get install -y python3-pip

# Definir o diretório de trabalho no contêiner
WORKDIR /app

# Copiar o arquivo de requisitos
COPY requirements.txt ./

# Instalar as dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Copiar o restante do seu código
COPY . .

# Expor a porta que o Streamlit usa
EXPOSE 8501

# Comando para iniciar a aplicação
CMD ["streamlit", "run", "app.py"]
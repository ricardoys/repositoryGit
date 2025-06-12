# Use uma imagem base Python
FROM python:3.11-slim-buster

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de requisitos e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação
COPY . .

# Expõe a porta que a aplicação Django vai escutar
EXPOSE 8000

# Comando padrão para rodar a aplicação (pode ser sobrescrito pelo docker-compose)
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
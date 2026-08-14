# Dockerfile — RailPulse Chainlit app, deployable on Render (or any Docker host)

FROM python:3.12-slim

# --- Install the ODBC Driver 18 for SQL Server (needed by pyodbc to reach Azure SQL) ---
RUN apt-get update && apt-get install -y curl gnupg apt-transport-https && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render provides the port to bind to via the $PORT environment variable
EXPOSE 8000
CMD chainlit run app.py --host 0.0.0.0 --port $PORT --headless
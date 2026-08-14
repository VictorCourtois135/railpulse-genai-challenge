# Dockerfile — RailPulse Chainlit app, deployable on Render (or any Docker host)

FROM python:3.12-slim

# --- Install the ODBC Driver 18 for SQL Server (needed by pyodbc to reach Azure SQL) ---
RUN apt-get update && apt-get install -y curl gnupg2 apt-transport-https unixodbc-dev && \
    curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render provides the port to bind to via the $PORT environment variable
EXPOSE 8000
CMD chainlit run app.py --host 0.0.0.0 --port $PORT --headless
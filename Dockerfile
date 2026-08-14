# Dockerfile — RailPulse Chainlit app, deployable on Render (or any Docker host)

FROM python:3.12-slim

# --- Install the ODBC Driver 18 for SQL Server (needed by pyodbc to reach Azure SQL) ---
#
# NOTE: as of Feb 2026, Microsoft's own Debian 12 repo signing key still uses SHA-1,
# which Debian's stricter signature policy (effective 2026-02-01) rejects by default.
# This is a known, currently unresolved issue on Microsoft's side:
# https://github.com/microsoft/linux-package-repositories/issues/306
# Workaround: explicitly allow this specific repo despite the failed signature check
# (the download itself still happens over HTTPS from packages.microsoft.com).
# Remove the --allow-unauthenticated / AllowInsecureRepositories flags once Microsoft
# rotates their signing key.
RUN apt-get update && apt-get install -y curl gnupg2 apt-transport-https unixodbc-dev && \
    curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update \
        -o Acquire::AllowInsecureRepositories=true \
        -o Acquire::AllowDowngradeToInsecureRepositories=true && \
    ACCEPT_EULA=Y apt-get install -y --allow-unauthenticated msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render provides the port to bind to via the $PORT environment variable
EXPOSE 8000
CMD chainlit run app.py --host 0.0.0.0 --port $PORT --headless
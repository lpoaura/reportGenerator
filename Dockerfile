FROM python:3.13-slim AS poetry

ENV OUTOUT_DIR=/home/user/output

RUN apt update && apt install gdal-bin -y 

RUN apt install -y curl && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry


FROM poetry AS builder
WORKDIR /src
COPY . /src
RUN cd /src && poetry install && poetry build -f wheel
RUN ls dist

FROM qgis/qgis:3.40


ENV PGSERVICEFILE=/config/pg_service.conf
ENV QT_QPA_PLATFORM=offscreen

COPY --from=builder /src/dist/*.whl /tmp/
RUN apt update && apt install -y python3-pip python3-venv
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install /tmp/*.whl && rm /tmp/*.whl


# ---Création des utilisateurs ----------------
RUN useradd -ms /bin/bash user && chown -R user:user /home/user
# ---Création des répertoires ----------------
RUN mkdir -p /home/user/output 
RUN mkdir -p /home/user/logs && chown -R user:user /home/user/logs
# --- Important dans le dossier il faut penser a donner les droits à l'utilisateur ----------------
    # Dans bash à l'endroit du output logs lancer la commande :  docker run --rm --entrypoint id lpoaura/importgenerator:latest
    # Puis lancer la commande en changeant les XXXX en fonction du résultat précédant : sudo chown -R XXXX:XXXX output logs


# --- Bascule vers un utilisateur non-root ----------------
USER user

VOLUME ["/output", "/config"]

# COPY ["docker/entrypoint.sh", "/entrypoint.sh"]

ENTRYPOINT ["reportgenerator"]


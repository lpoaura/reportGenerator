# Create a poetry image
FROM python:3.13-slim AS poetry

RUN apt update && apt install gdal-bin curl -y && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry


# Build step
FROM poetry AS builder
WORKDIR /src
COPY . /src
RUN cd /src && poetry install && poetry build -f wheel

# App image
FROM qgis/qgis:3.40

# Custom build args
ARG UID=1000
ARG GID=1000
ARG USERNAME=app
ARG HOME_DIR=/app

# Env
ENV OUTPUT_DIR=${HOME_DIR}/output
ENV PGSERVICEFILE=/config/pg_service.conf
ENV QT_QPA_PLATFORM=offscreen

# Install app
COPY --from=builder /src/dist/*.whl /tmp/

RUN apt update &&\
    apt install -y python3-pip python3-venv &&\
    rm -rf /var/lib/apt/lists/*


RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

RUN pip install /tmp/*.whl && rm /tmp/*.whl

# Install custom fonts
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY --from=builder /src/src/reportgenerator/templates/fonts/*.otf /usr/share/fonts/truetype/custom/
RUN chmod 644 /usr/share/fonts/truetype/custom/* && \
    fc-cache -fv

# ---Création des utilisateurs ----------------
RUN set -eux; \
    if ! getent group "${GID}" >/dev/null; then \
        groupadd --gid "${GID}" "${USERNAME}"; \
    fi; \
    \
    if ! getent passwd "${UID}" >/dev/null; then \
        useradd \
            --uid "${UID}" \
            --gid "${GID}" \
            --home-dir "${HOME_DIR}" \
            --create-home \
            --shell /bin/bash \
            "${USERNAME}"; \
    fi; \
    \
    mkdir -p "${HOME_DIR}" "${OUTPUT_DIR}" "${HOME_DIR}/logs"; \
    chown -R "${UID}:${GID}" "${HOME_DIR}" "${OUTPUT_DIR}"

USER ${UID}:${GID}

VOLUME ["/output", "/config"]

ENTRYPOINT ["reportgenerator"]


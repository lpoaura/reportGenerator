FROM python:3.13-slim AS poetry


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
COPY --from=builder /src/dist/*.whl /tmp/
RUN apt update && apt install -y python3-pip python3-venv
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install /tmp/*.whl && rm /tmp/*.whl
VOLUME /output

ENTRYPOINT ["reportgenerator"]


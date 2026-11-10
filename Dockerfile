FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
RUN useradd --create-home productmesh && chown -R productmesh:productmesh /app
USER productmesh

EXPOSE 8080
CMD ["python", "-m", "productmesh.cli", "serve"]

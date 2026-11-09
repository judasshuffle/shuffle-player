FROM python:3.12-slim
WORKDIR /app
COPY web/control_server.py /app/control_server.py
COPY web/shufflizer/index.html /app/visualizer/index.html
COPY web/shufflizer/css /app/visualizer/css
COPY web/shufflizer/js /app/visualizer/js
COPY preview/server.py /app/preview.py
COPY preview/library_setup.py preview/setup.html /app/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65534:65534
EXPOSE 8092
CMD ["python", "-B", "/app/preview.py"]

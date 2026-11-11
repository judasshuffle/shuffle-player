FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache ffmpeg
RUN pip install --no-cache-dir mutagen==1.47.0
COPY synology/server.py synology/index.html synology/app.js /app/
COPY synology/palette.js /app/palette.js
COPY synology/radio.py synology/station.js /app/
COPY synology/dr-screen.html synology/dr-screen.js synology/dr-screen-entity.js /app/
COPY synology/dr-remote.html synology/dr-remote.js synology/dr-dj.js synology/owner.js synology/sha256.js synology/sha256-LICENSE.txt /app/
COPY web/shufflizer/index.html /app/visualizer/index.html
COPY web/shufflizer/css /app/visualizer/css
COPY web/shufflizer/js /app/visualizer/js
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1026:100
EXPOSE 8080 8081
CMD ["python", "-B", "server.py"]

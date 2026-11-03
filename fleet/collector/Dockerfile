# 수집기 컨테이너 — 호스트 파이썬 대신 컨테이너로 띄우고 싶을 때 (장애 주입 --fault collector 가 docker stop/start 로 죽였다 살린다)
#   빌드 컨텍스트는 fleet/ (docker-compose.yml 의 collector 서비스 참고)
#   실행:  docker compose -f fleet/docker-compose.yml --profile collector up -d
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY collector/ collector/
COPY db/ db/
# 시작할 때 마이그레이션(새 표·컬럼)을 먼저 적용하고 수집기를 띄운다
CMD ["sh", "-c", "python3 db/migrate.py --db $DB_DSN && exec python3 collector/collector.py --broker $BROKER --db $DB_DSN --qos ${COLLECTOR_QOS:-0}"]

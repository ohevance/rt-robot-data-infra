#!/usr/bin/env python3
"""DB 마이그레이션 — 이미 떠 있는 DB 에 새 표/컬럼을 추가한다.

왜 필요한가
  init.sql 은 컨테이너가 "처음" 뜰 때 한 번만 실행된다. 그 뒤에 스키마가 바뀌면(OTA 표, 수집기 내성 컬럼)
  데이터는 그대로 두고 바뀐 부분만 적용해야 한다. 현장에서도 같은 문제라 보통 이렇게 번호 붙인 SQL 파일로 관리한다.

동작
  fleet/db/migrations/NNN_*.sql 을 번호 순서로 읽어, schema_migrations 표에 없는 것만 실행하고 기록한다.
  두 번 실행해도 안전하다 (이미 적용된 것은 건너뜀. SQL 자체도 IF NOT EXISTS 로 써서 이중 안전).

사용:  python3 fleet/db/migrate.py            # 기본 DSN
       python3 fleet/db/migrate.py --db postgresql://fleet:fleet@localhost:5432/fleet
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(HERE, "migrations")


def list_migrations():
    """migrations/ 의 .sql 파일을 이름순(번호순)으로"""
    names = []
    for name in os.listdir(MIGRATIONS_DIR):
        if name.endswith(".sql"):
            names.append(name)
    names.sort()
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="postgresql://fleet:fleet@localhost:5432/fleet")
    a = ap.parse_args()

    import psycopg
    conn = psycopg.connect(a.db, autocommit=True)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
    cur.execute("SELECT name FROM schema_migrations")
    applied = set(row[0] for row in cur.fetchall())

    count = 0
    for name in list_migrations():
        if name in applied:
            print(f"skip   {name} (이미 적용)")
            continue
        with open(os.path.join(MIGRATIONS_DIR, name), encoding="utf-8") as f:
            sql = f.read()
        cur.execute(sql)
        cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
        print(f"apply  {name}")
        count += 1
    conn.close()
    print(f"done: {count} applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())

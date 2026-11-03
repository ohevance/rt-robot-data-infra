#!/usr/bin/env python3
"""가짜 psycopg — DB 없이 수집기의 "DB 가 죽었다/살았다" 흐름을 테스트하기 위한 최소 흉내 (테스트 전용).

흉내 내는 것 (collector.py 가 쓰는 부분만)
  - connect(dsn, **kw) → FakeConn.   FAIL["connect"] = True 면 OperationalError
  - conn.cursor() 컨텍스트 매니저, cur.execute(sql, params), cur.copy(sql) 컨텍스트 매니저 + write_row
  - FAIL["write"] = True 면 execute/copy 가 OperationalError → 수집기가 backlog 로 돌아가야 한다
  - 들어온 행은 STORE 에 쌓인다 (테스트가 세어 본다)

쓰는 법:
    import fake_psycopg
    fake_psycopg.install()      # sys.modules["psycopg"] 교체 (collector 의 connect_db 가 import 할 때 이것을 얻는다)
"""
import sys
import types

FAIL = {"connect": False, "write": False, "schema_old": False}
STORE = {"telemetry": [], "events": [], "devices": {}, "collector_stats": [], "executed": []}


class Error(Exception):
    pass


class OperationalError(Error):
    pass


def reset():
    FAIL["connect"] = False
    FAIL["write"] = False
    FAIL["schema_old"] = False
    STORE["telemetry"] = []
    STORE["events"] = []
    STORE["devices"] = {}
    STORE["collector_stats"] = []
    STORE["executed"] = []


class FakeCopy:
    def __init__(self):
        self.rows = []

    def __enter__(self):
        if FAIL["write"]:
            raise OperationalError("connection lost (fake)")
        return self

    def write_row(self, row):
        self.rows.append(row)

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            STORE["telemetry"].extend(self.rows)
        return False


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        if FAIL["write"]:
            raise OperationalError("connection lost (fake)")
        STORE["executed"].append(sql)
        if sql.startswith("SELECT backlog_rows"):
            if FAIL["schema_old"]:
                raise Error('column "backlog_rows" does not exist (fake)')
            return
        if sql.startswith("INSERT INTO devices"):
            STORE["devices"][params[0]] = params
        elif sql.startswith("INSERT INTO events"):
            STORE["events"].append(params)
        elif sql.startswith("INSERT INTO collector_stats"):
            STORE["collector_stats"].append(params)

    def copy(self, sql):
        return FakeCopy()

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeConn:
    def __init__(self):
        self.closed = False
        self.commits = 0

    def cursor(self):
        return FakeCursor()

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def connect(dsn, **kwargs):
    if FAIL["connect"]:
        raise OperationalError("connection refused (fake)")
    return FakeConn()


def install():
    module = types.ModuleType("psycopg")
    module.connect = connect
    module.Error = Error
    module.OperationalError = OperationalError
    sys.modules["psycopg"] = module
    return module

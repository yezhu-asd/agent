"""尝试通过 Milvus HTTP API 实时更新配置"""
import json
import urllib.request

MILVUS_API = "http://localhost:9091/api/v1"

def try_update_config():
    # 尝试不同的 API 路径和参数格式
    attempts = [
        # Milvus 2.4.x 可能的配置 API
        {"url": f"{MILVUS_API}/milvus/configurations", "method": "PATCH",
         "data": {"common.maximumQueryResultWindow": 1000000}},
        {"url": f"{MILVUS_API}/config", "method": "PUT",
         "data": {"common.maximumQueryResultWindow": 1000000}},
        {"url": f"{MILVUS_API}/configs", "method": "PUT",
         "data": {"common.maximumQueryResultWindow": 1000000}},
    ]

    for attempt in attempts:
        try:
            data = json.dumps(attempt["data"]).encode("utf-8")
            req = urllib.request.Request(
                attempt["url"],
                data=data,
                method=attempt["method"],
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=5)
            print(f"[{attempt['method']}] {attempt['url']}: {resp.status}")
            print(resp.read().decode("utf-8")[:200])
            return True
        except Exception as e:
            err = str(e)[:100]
            print(f"[{attempt['method']}] {attempt['url']}: {err}")

    # 尝试 GET 看有哪些 API 可用
    for path in ["/api/v1", "/api/v2", "/"]:
        try:
            req = urllib.request.Request(f"http://localhost:9091{path}")
            resp = urllib.request.urlopen(req, timeout=5)
            print(f"GET {path}: {resp.status}")
            print(resp.read().decode("utf-8")[:300])
        except Exception as e:
            print(f"GET {path}: {str(e)[:80]}")

    return False

try_update_config()

import http.client

from autoincc_mcp.config import get_config

connection = http.client.HTTPConnection("127.0.0.1", get_config().mcp_port, timeout=5)
try:
    connection.request("GET", "/health")
    raise SystemExit(0 if connection.getresponse().status == 200 else 1)
except OSError:
    raise SystemExit(1) from None
finally:
    connection.close()

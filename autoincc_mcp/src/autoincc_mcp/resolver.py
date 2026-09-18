import re

_PATH_PATTERNS = [
    (r"/api/v1/incc/latest", "Índice INCC recente"),
    (r"/api/v1/incc/history", "Histórico INCC"),
    (r"/api/v1/incc/correction", "Correção monetária INCC"),
    (r"/api/v1/incc/overview", "Panorama INCC"),
    (r"/api/v1/incc/compare", "Comparação INCC"),
    (r"/api/v1/incc/analytics/seasonality", "Sazonalidade INCC"),
    (r"/api/v1/incc/analytics/stats", "Estatísticas INCC"),
    (r"/api/v1/incc/metadata", "Metadados INCC"),
]


def resolve_resource(path: str) -> str:
    for pattern, name in _PATH_PATTERNS:
        if re.fullmatch(pattern, path):
            return name
    return "recurso"

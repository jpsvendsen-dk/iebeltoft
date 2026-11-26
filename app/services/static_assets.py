"""Cache public calendar assets; versioned URLs change when their content changes."""
from urllib.parse import parse_qs
from fastapi.staticfiles import StaticFiles


class CalendarStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.replace("\\", "/").startswith("jul2026/") and response.status_code in (200, 206, 304):
            version = parse_qs(scope.get("query_string", b"").decode("ascii", errors="ignore")).get("v", [""])[0]
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if version.isdecimal() else "public, max-age=3600"
        return response

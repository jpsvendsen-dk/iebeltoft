"""Best-effort client metadata. These values describe a request, not an identity."""
import os
from ipaddress import ip_address


def valid_ip(raw):
    try:
        if not raw or len(raw) > 45 or "%" in raw:
            return None
        return str(ip_address(raw.strip()))
    except ValueError:
        return None


def client_ip(request):
    # Render's public ingress is Cloudflare-backed. Never trust these headers
    # on the local server or arbitrary direct deployments.
    if os.getenv("RENDER", "").lower() == "true":
        for name in ("cf-connecting-ip", "true-client-ip"):
            value = valid_ip(request.headers.get(name, ""))
            if value:
                return value
        # Resolve an appended proxy chain from the right, skipping private hops.
        for candidate in reversed(request.headers.get("x-forwarded-for", "").split(",")):
            value = valid_ip(candidate)
            if value and ip_address(value).is_global:
                return value
    return valid_ip(request.client.host) if request.client else None


def client_metadata(request):
    ua = request.headers.get("user-agent", "")[:512]
    text = ua.lower()
    if not text:
        return {"ip_address": client_ip(request), "device_type": None, "user_agent": None}
    if any(word in text for word in ("bot", "crawler", "spider")):
        device = "Robot"
    elif "iphone" in text or "ipod" in text:
        device = "iPhone" if "iphone" in text else "iPod"
    elif "ipad" in text or ("macintosh" in text and "mobile" in text):
        device = "iPad"
    elif "android" in text:
        device = "Android-mobil" if "mobile" in text else "Android-tablet"
    elif "windows" in text:
        device = "Windows-computer"
    elif "macintosh" in text or "mac os x" in text:
        device = "Mac"
    elif "linux" in text:
        device = "Linux-computer"
    else:
        device = "Ukendt enhed"
    if any(word in text for word in ("edg/", "edgios/", "edga/")):
        browser = "Edge"
    elif "crios/" in text or "chrome/" in text:
        browser = "Chrome"
    elif "fxios/" in text or "firefox/" in text:
        browser = "Firefox"
    elif "safari/" in text:
        browser = "Safari"
    else:
        browser = None
    return {"ip_address": client_ip(request), "device_type": device + (" · " + browser if browser else ""), "user_agent": ua}

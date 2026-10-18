#!/usr/bin/env python3
"""Publicador de Instagram de TOROTE (Instagram API with Instagram Login).

Lee ig/queue.json y publica lo que ya venció, solo si "aprobado": true.
Los archivos se sirven desde GitHub Pages ({SITE_URL}/ig/...).
Guarda lo publicado en ig/published.json (el workflow lo commitea).

Tipos en la cola:
  post      -> 1 imagen en el feed
  carrusel  -> 2 a 10 imágenes (o videos) en el feed
  reel      -> 1 video .mp4 (9:16, 3-90 s) en Reels y en el feed
  story     -> 1 imagen o 1 video .mp4 en historias

Modos:
  python ig_publish.py check     -> verifica el token y la cuota (no publica)
  python ig_publish.py publish   -> publica lo vencido y aprobado
  python ig_publish.py refresh   -> renueva el token largo (60 días) e imprime cuántos días le quedan
  python ig_publish.py validate  -> revisa la cola (archivos, fechas, captions) sin llamar a la API
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://graph.instagram.com"
SITE = (os.environ.get("SITE_URL") or "https://torotegymwear.github.io").rstrip("/")
TOKEN = os.environ.get("IG_TOKEN", "").strip()
USER_ID = os.environ.get("IG_USER_ID", "").strip()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "ig", "queue.json")
DONE = os.path.join(ROOT, "ig", "published.json")
MAX_POR_CORRIDA = int(os.environ.get("IG_MAX_POR_CORRIDA", "6"))
VIDEO_EXT = (".mp4", ".mov")


def call(method, path, params=None, base=API, token=None):
    params = dict(params or {})
    params["access_token"] = token or TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = path if path.startswith("http") else f"{base}/{path}"
    req = urllib.request.Request(url + "?" + data.decode()) if method == "GET" else urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if TOKEN:
            body = body.replace(TOKEN, "***")
        raise RuntimeError(f"Error {e.code} en {path.split('?')[0]}: {body}")


def wait_ready(cid, video=False):
    tries = 60 if video else 24
    for _ in range(tries):
        st = call("GET", cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Contenedor {cid} falló: {st}")
        time.sleep(10 if video else 5)
    raise RuntimeError(f"Contenedor {cid} no terminó a tiempo")


def url_of(f):
    return f if f.startswith("http") else f"{SITE}/ig/{urllib.parse.quote(f)}"


def is_video(f):
    return f.lower().endswith(VIDEO_EXT)


def media_params(f, extra=None):
    p = {"video_url": url_of(f)} if is_video(f) else {"image_url": url_of(f)}
    p.update(extra or {})
    return p


def publish(item):
    kind = item.get("tipo", "post").lower()
    files = item["archivos"]
    caption = item.get("caption", "")
    if kind == "story":
        p = media_params(files[0], {"media_type": "STORIES"})
        cid = call("POST", f"{USER_ID}/media", p)["id"]
        wait_ready(cid, is_video(files[0]))
    elif kind == "reel":
        p = {"media_type": "REELS", "video_url": url_of(files[0]), "caption": caption, "share_to_feed": "true"}
        if item.get("portada_ms") is not None:
            p["thumb_offset"] = str(item["portada_ms"])
        if item.get("portada"):
            p["cover_url"] = url_of(item["portada"])
        cid = call("POST", f"{USER_ID}/media", p)["id"]
        wait_ready(cid, True)
    elif kind == "carrusel" or len(files) > 1:
        kids = []
        for f in files[:10]:
            extra = {"is_carousel_item": "true"}
            if is_video(f):
                extra["media_type"] = "VIDEO"
            kids.append(call("POST", f"{USER_ID}/media", media_params(f, extra))["id"])
        for k, f in zip(kids, files):
            wait_ready(k, is_video(f))
        cid = call("POST", f"{USER_ID}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": caption})["id"]
        wait_ready(cid)
    else:
        cid = call("POST", f"{USER_ID}/media", media_params(files[0], {"caption": caption}))["id"]
        wait_ready(cid, is_video(files[0]))
    return call("POST", f"{USER_ID}/media_publish", {"creation_id": cid})["id"]


def load_queue():
    q = json.load(open(QUEUE, encoding="utf-8"))
    for it in q:  # compatibilidad con la cola de Bataká ("imagenes")
        if "archivos" not in it and "imagenes" in it:
            it["archivos"] = it["imagenes"]
    return q


def validate():
    q = load_queue()
    ids, problems = set(), []
    for it in q:
        pid = it.get("id")
        if pid in ids:
            problems.append(f"{pid}: id repetido")
        ids.add(pid)
        try:
            datetime.fromisoformat(it["fecha"])
        except Exception:
            problems.append(f"{pid}: fecha inválida {it.get('fecha')}")
        for f in it.get("archivos", []):
            if not f.startswith("http") and not os.path.exists(os.path.join(ROOT, "ig", f)):
                problems.append(f"{pid}: falta ig/{f}")
        if it.get("tipo") == "reel" and not is_video(it["archivos"][0]):
            problems.append(f"{pid}: un reel necesita un .mp4")
        if len(it.get("caption", "")) > 2200:
            problems.append(f"{pid}: caption de más de 2200 caracteres")
        if it.get("caption", "").count("#") > 30:
            problems.append(f"{pid}: más de 30 hashtags")
    aprob = sum(1 for it in q if it.get("aprobado"))
    print(f"{len(q)} elementos en cola · {aprob} aprobados · {len(problems)} problemas")
    for p in problems:
        print("  -", p)
    return not problems


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "publish"
    if mode == "validate":
        sys.exit(0 if validate() else 1)
    if not TOKEN or not USER_ID:
        raise SystemExit("Faltan los secretos IG_TOKEN o IG_USER_ID")

    if mode == "check":
        me = call("GET", "me", {"fields": "user_id,username,account_type"})
        lim = call("GET", f"{USER_ID}/content_publishing_limit", {"fields": "quota_usage,config"})
        print("Token OK ->", me.get("username"), me.get("account_type"), "| cuota 24 h:", json.dumps(lim.get("data", lim)))
        return

    if mode == "refresh":
        r = call("GET", "refresh_access_token", {"grant_type": "ig_refresh_token"})
        new, days = r.get("access_token", ""), int(r.get("expires_in", 0)) // 86400
        print(f"Token renovado. Vence en {days} días.")
        out = os.environ.get("GITHUB_OUTPUT")
        if out and new:
            print(f"::add-mask::{new}")
            with open(out, "a") as fh:
                fh.write(f"token={new}\n")
        return

    queue = load_queue()
    done = json.load(open(DONE, encoding="utf-8")) if os.path.exists(DONE) else {}
    now = datetime.now(timezone.utc)
    pend = [it for it in queue if it["id"] not in done and it.get("aprobado") and datetime.fromisoformat(it["fecha"]) <= now]
    pend.sort(key=lambda it: it["fecha"])
    if not pend:
        print("Nada que publicar ahora.")
        return
    errores = 0
    for item in pend[:MAX_POR_CORRIDA]:
        pid = item["id"]
        print(f"Publicando {pid} ({item.get('tipo', 'post')}) programado para {item['fecha']}…")
        try:
            media_id = publish(item)
        except RuntimeError as e:
            errores += 1
            print(f"  ✗ {e}")
            continue
        done[pid] = {"media_id": media_id, "publicado": now.isoformat(timespec="seconds")}
        json.dump(done, open(DONE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"  ok -> media {media_id}")
        time.sleep(20)
    if len(pend) > MAX_POR_CORRIDA:
        print(f"Quedan {len(pend) - MAX_POR_CORRIDA} para la próxima corrida.")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()

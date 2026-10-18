# TOROTE · catálogo y publicación automática en Instagram

Este repo hace dos cosas:

1. **Sitio del link en bio** (`index.html`): el catálogo de TOROTE. El cliente elige productos y tallas, y el pedido se abre armado en WhatsApp.
2. **Publicador de Instagram** (`ig/` + `.github/workflows/instagram.yml`): cada 30 minutos un GitHub Action publica en @torotegymwear los posts, carruseles, reels y stories de `ig/queue.json` que ya vencieron **y** tienen `"aprobado": true`.

## Editar precios, productos o el número de WhatsApp

Todo está en `index.html`, en el bloque `CONFIG` y la lista `PRODUCTS` del final:

- `whatsapp`: número de pedidos (593 + número sin el 0).
- `price`: precio final **con IVA incluido**. Si pones `null`, el producto sale como "precio por WhatsApp".
- Las fotos de producto están en `assets/p/<id>.jpg` (720×900).

## Puesta en marcha (una sola vez)

### 1. GitHub
1. Crea la cuenta u organización **torotegymwear** en GitHub (así el sitio queda en `https://torotegymwear.github.io`).
2. Crea el repo público **torotegymwear.github.io** y sube este contenido.
3. En *Settings → Pages*, elige *Deploy from a branch* → `main` / `root`.
4. Si usas otro nombre de repo, crea la variable `SITE_URL` en *Settings → Secrets and variables → Actions → Variables* con la URL pública (por ejemplo `https://torolocote.github.io/torote`).

### 2. App de Meta (nueva, solo para TOROTE)
1. En developers.facebook.com → *Mis apps* → *Crear app* → caso de uso **"Administrar mensajes y contenido en Instagram"** (Instagram API with Instagram Login).
2. En *Instagram → Configuración de la API con inicio de sesión de Instagram*, agrega la cuenta **@torotegymwear** (debe ser Business o Creator) y concede los permisos `instagram_business_basic` e `instagram_business_content_publish`.
3. Pulsa **Generar token**. Ese token ya es de larga duración (60 días).
4. Copia el **ID de usuario de Instagram** que aparece junto a la cuenta.
5. No hace falta App Review: la app publica solo en tu propia cuenta.

### 3. Secretos en GitHub
En *Settings → Secrets and variables → Actions → New repository secret*:

| Secreto | Valor |
|---|---|
| `IG_TOKEN` | el token del paso 2.3 |
| `IG_USER_ID` | el ID del paso 2.4 |
| `GH_PAT` *(opcional)* | token fino de GitHub con permiso **Secrets: Read and write** solo en este repo. Sirve para guardar el token renovado. |

**Nunca pegues el token en un chat, en un archivo o en un commit.**

### 4. Probar
*Actions → Instagram TOROTE → Run workflow → modo `check`*. Debe imprimir `Token OK -> torotegymwear BUSINESS` y la cuota de 24 h.

## Día a día

- **Aprobar un lote:** en `ig/queue.json`, cambia `"aprobado": false` a `true` en lo que quieras publicar y haz commit. Lo que no esté aprobado nunca se publica.
- **Cambiar una fecha o un caption:** edita `fecha` (formato `2026-10-19T07:00:00-05:00`) o `caption` en la cola.
- **Revisar la cola sin publicar:** *Run workflow → modo `validate`*.
- **Registro:** `ig/published.json` guarda qué se publicó y con qué ID. Si un ID está ahí, no se vuelve a publicar.
- **Token:** se renueva solo los días 1 y 15 de cada mes. Sin `GH_PAT` igual se extiende la vigencia del token que ya tienes guardado.

## Tipos de publicación

| tipo | archivos | notas |
|---|---|---|
| `post` | 1 JPG 1080×1350 | |
| `carrusel` | 2–10 JPG 1080×1350 | |
| `reel` | 1 MP4 1080×1920, H.264 + AAC | `portada_ms` elige el fotograma de portada |
| `story` | 1 JPG o MP4 1080×1920 | las stories no llevan caption |

El límite de Instagram es de 50 publicaciones por cuenta cada 24 h; el plan de 3 posts + 5 stories al día queda muy por debajo.

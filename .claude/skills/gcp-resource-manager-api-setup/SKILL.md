---
name: gcp-resource-manager-api-setup
description: Activa con gcloud la Cloud Resource Manager API (y verifica la Cloud Storage API) en el proyecto de GCP dueño del ID de cliente OAuth del Proyecto-RAGs-v2, para que "Conectar con Google" pueda listar los proyectos y buckets del usuario. Incluye la comprobación real con un token y x-goog-user-project, permisos necesarios, costos (gratis) y solución de errores como SERVICE_DISABLED o "API has not been used in project … before or it is disabled". Use when the user or a student asks to "activar Resource Manager", "habilitar la API de proyectos", "no aparecen mis proyectos en el desplegable", "SERVICE_DISABLED", "cloudresourcemanager.googleapis.com", "gcloud services enable", or types /gcp-resource-manager-api-setup.
---

# Activar la Cloud Resource Manager API para "Conectar con Google"

Objetivo: que, cuando una persona inicia sesión con "Conectar con Google", la app pueda **listar sus proyectos de GCP** (el desplegable Proyecto → Bucket → Carpeta) y **leer sus buckets**.

Se hace en **el mismo proyecto** donde se creó el ID de cliente OAuth (skill `gcp-google-identity-oauth-setup`). Haz las dos skills.

## Por qué en el proyecto del cliente OAuth

Cuando el navegador llama a una API de Google con el token del usuario, Google la atribuye al **proyecto dueño del cliente OAuth**: es su "quota project". Si la API no está activa **ahí**, la llamada falla con `403 SERVICE_DISABLED`, aunque el usuario tenga permisos de sobra en sus propios proyectos.

| API | Para qué la usa la app | ¿Hay que activarla? |
|---|---|---|
| **Cloud Resource Manager API** (`cloudresourcemanager.googleapis.com`) | Listar los proyectos del usuario | **Sí**: no viene activa en proyectos nuevos |
| **Cloud Storage API** (`storage.googleapis.com`) | Listar buckets y leer los PDFs | Suele venir activa por defecto. Se verifica y, si falta, se activa por precaución |

## Quién configura qué (y quién paga)

| Papel | Qué necesita | Costo |
|---|---|---|
| **Quien levanta el sistema** (el profesor, o cada alumno en su equipo) | El proyecto con el cliente OAuth y estas APIs activas. **No necesita ningún bucket**: la app no guarda nada en GCS. | **Gratis.** Google no cobra el uso de la Cloud Resource Manager API, y activar APIs no cuesta. |
| **El dueño de los PDFs** (el "cliente") | Su bucket, en su proyecto | Paga su almacenamiento y las lecturas (listar y descargar), que se cobran a **su** proyecto. Son centavos. |

Activar estas dos APIs **no requiere facturación** en el proyecto.

## Prerequisitos

| Requisito | Cómo comprobarlo | Si falta |
|---|---|---|
| Google Cloud SDK | `gcloud version` | https://cloud.google.com/sdk/docs/install |
| Sesión de gcloud válida | `gcloud projects list --limit=1` | El alumno ejecuta `! gcloud auth login` (interactivo) |
| El proyecto del cliente OAuth | Lo eligió en `gcp-google-identity-oauth-setup` | Hacer esa skill primero, o elegir el proyecto ahora |
| Permiso para activar APIs | Ser **Propietario** o **Editor** del proyecto, o tener `roles/serviceusage.serviceUsageAdmin` | Pedirlo al dueño del proyecto. Quien creó el proyecto ya es Propietario. |

Si `gcloud` responde *"Reauthentication failed. cannot prompt during non-interactive execution"*, la sesión caducó. **No intentes resolverlo tú**: pídele al alumno que ejecute `! gcloud auth login` y continúa después.

## Procedimiento (ejecútalo paso a paso)

### Paso 1: Fijar el proyecto

Usa el mismo proyecto del cliente OAuth. Confírmalo con el alumno:

```bash
gcloud config get-value project
PROJECT_ID=<id-del-proyecto-del-cliente-oauth>
```

PowerShell: `$env:PROJECT_ID = "<id>"`, y en los comandos usa `$env:PROJECT_ID`.

### Paso 2: Ver qué está activo

```bash
gcloud services list --enabled --project="$PROJECT_ID" \
  --filter="config.name:(cloudresourcemanager.googleapis.com storage.googleapis.com)" \
  --format="value(config.name)"
```

Si salen las dos, salta al Paso 4.

### Paso 3: Activar las APIs

```bash
gcloud services enable cloudresourcemanager.googleapis.com storage.googleapis.com \
  --project="$PROJECT_ID"
```

Es idempotente: si ya estaban activas, no pasa nada. Tarda unos segundos y la propagación puede tomar **1–2 minutos más**.

### Paso 4: Verificar de verdad (con un token y el proyecto como quota project)

`services list` dice que la API está activa. Esta prueba confirma además que **una llamada atribuida a ese proyecto** funciona, que es lo que hará la app:

```bash
curl -s -o /dev/null -w "Resource Manager: HTTP %{http_code}\n" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "x-goog-user-project: $PROJECT_ID" \
  "https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=1"
```

| Resultado | Significado |
|---|---|
| `HTTP 200` | Listo: la API está activa y atribuida al proyecto. |
| `HTTP 403` | Mira el cuerpo de la respuesta (abajo). Casi siempre es `SERVICE_DISABLED` (espera 1–2 min tras el Paso 3) o falta el permiso `serviceusage.services.use` en el proyecto. |
| `HTTP 401` | Token caducado: `! gcloud auth login`. |

Para ver el motivo de un 403, repite el comando sin `-o /dev/null -w ...`. No imprimas la lista de proyectos en la conversación: con `pageSize=1` y el código HTTP basta.

PowerShell:

```powershell
$token = gcloud auth print-access-token
(Invoke-WebRequest -Uri "https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=1" `
  -Headers @{ Authorization = "Bearer $token"; "x-goog-user-project" = $env:PROJECT_ID }).StatusCode
```

### Paso 5: Probar en la app

Con el cliente OAuth ya configurado:
1. Abre `http://localhost:5174` → **Pipeline de ingesta**.
2. Elige la fuente **Bucket de Google Cloud Storage** y pulsa **Conectar con Google**.
3. El desplegable de **proyectos** debe llenarse. Solo aparecen los proyectos donde la cuenta tiene al menos permiso de lectura.

Si el botón **Conectar con Google** todavía no existe en el frontend, la configuración de GCP igual queda lista; verifícala cuando la función esté programada.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `403 SERVICE_DISABLED` · "Cloud Resource Manager API has not been used in project … before or it is disabled" | API no activa **en el proyecto del cliente OAuth** | Paso 3 en **ese** proyecto (no en otro) y espera 1–2 min. El número del mensaje es el *project number* del cliente OAuth. |
| `PERMISSION_DENIED` al ejecutar `services enable` | La cuenta no puede activar APIs | Pide `roles/serviceusage.serviceUsageAdmin` o Editor al dueño del proyecto. |
| `403` con "USER_PROJECT_DENIED" / falta `serviceusage.services.use` | La cuenta no puede usar el proyecto como quota project | Mismo arreglo: ser Propietario/Editor o tener `roles/serviceusage.serviceUsageConsumer`. |
| El desplegable de proyectos sale vacío | La cuenta no tiene proyectos visibles | Normal en cuentas nuevas. Crear un proyecto o pedir acceso de lectura a uno. |
| Aparecen proyectos pero los buckets dan 403 | Sin permiso de listar buckets en **ese** proyecto | El dueño del proyecto debe dar `roles/storage.bucketViewer` (listar) y `roles/storage.objectViewer` (leer PDFs). |
| Pide activar facturación | No hace falta para estas dos APIs | Revisa que el comando sea exactamente el del Paso 3. |

## Lo que NO hace esta skill

- No crea el cliente OAuth ni la pantalla de consentimiento: eso es `gcp-google-identity-oauth-setup`.
- No crea buckets ni da permisos sobre buckets ajenos.
- No activa APIs de pago.

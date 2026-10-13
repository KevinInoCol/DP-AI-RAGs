---
name: gcp-google-identity-oauth-setup
description: Configura Google Identity Services (OAuth 2.0) en un proyecto de GCP para el botón "Conectar con Google" del Proyecto-RAGs-v2 — elegir o crear el proyecto con gcloud, pantalla de consentimiento (Google Auth Platform: Branding, Audience en modo Testing con usuarios de prueba, Data access con los scopes de solo lectura), crear el ID de cliente OAuth de tipo Aplicación web con el origen http://localhost:5174, y guardar VITE_GOOGLE_CLIENT_ID en el .env del frontend. El cliente OAuth web NO se puede crear con gcloud, así que la skill automatiza lo posible y guía la consola paso a paso. Use when the user or a student asks to "configurar OAuth", "crear el ID de cliente de Google", "Google Identity Services", "pantalla de consentimiento", "Conectar con Google no funciona", "VITE_GOOGLE_CLIENT_ID", "origin_mismatch", "redirect_uri_mismatch", "access_denied / la app no está verificada", or types /gcp-google-identity-oauth-setup.
---

# Configurar Google Identity Services (OAuth 2.0) para "Conectar con Google"

Objetivo: que el frontend del Proyecto-RAGs-v2 pueda pedirle a una persona que inicie sesión con **su** cuenta de Google y le dé permiso de **solo lectura** para listar sus proyectos y leer sus buckets de Cloud Storage.

Al terminar, el alumno tiene un **ID de cliente OAuth** (`xxxxxxxx-yyyy.apps.googleusercontent.com`) guardado en `Frontend-RAGs/.env` como `VITE_GOOGLE_CLIENT_ID`.

La otra mitad de la configuración, activar la Cloud Resource Manager API en el **mismo proyecto**, está en la skill `gcp-resource-manager-api-setup`. Haz las dos.

## Quién configura qué (y quién paga)

| Papel | Qué necesita | Costo |
|---|---|---|
| **Quien levanta el sistema** (el profesor, o cada alumno en su equipo) | Un proyecto de GCP con el ID de cliente OAuth y la Cloud Resource Manager API activa. **No necesita ningún bucket**: la app no guarda nada en GCS; lee los PDFs, los procesa y los vectores van a Qdrant. | Gratis |
| **El dueño de los PDFs** (el "cliente") | Su bucket con PDFs, en su proyecto. | Paga su almacenamiento, como antes. Las lecturas de la app (listar y descargar) se cobran a su proyecto: centavos, suelen caber en su capa gratuita. |

En clase el alumno suele hacer los dos papeles: levanta su sistema y, para tener algo que ingestar, usa un bucket propio con PDFs de prueba.

**El ID de cliente OAuth es gratis y no requiere facturación activada en el proyecto.**

## Por qué cada alumno crea su propio cliente

- Una app en modo **Testing** solo deja entrar a los **usuarios de prueba** que el dueño añade a mano (máximo 100).
- Publicarla para cualquiera obliga a pasar la **verificación de Google**, porque pide un scope de Cloud Storage.
- Si el profesor borra su cliente, se rompe la app de todos.

Por eso cada alumno registra el suyo en su proyecto. Es un buen ejercicio de clase.

## Qué NO se puede automatizar

**El cliente OAuth web no se crea con `gcloud`.** Comprobado con Google Cloud SDK 577:
- `gcloud iam oauth-clients create` crea clientes de **Workforce Identity Federation** (identidades federadas), no de "Iniciar sesión con Google".
- `gcloud iap oauth-brands` / `gcloud iap oauth-clients` están **obsoletos**: Google apagó las IAP OAuth Admin APIs el 19 de enero de 2026.

La pantalla de consentimiento y el cliente se crean en la consola, en **Google Auth Platform**. Esta skill usa `gcloud` para todo lo demás y le da al alumno los enlaces directos.

## Prerequisitos

| Requisito | Cómo comprobarlo | Si falta |
|---|---|---|
| Google Cloud SDK | `gcloud version` | https://cloud.google.com/sdk/docs/install |
| Sesión de gcloud válida | `gcloud auth list` y `gcloud projects list --limit=1` | El alumno ejecuta `! gcloud auth login` (es interactivo: abre el navegador) |
| Una cuenta de Google | — | Una cuenta personal @gmail.com sirve |
| El repo clonado | existe `Proyecto-RAGs-v2/Frontend-RAGs/vite.config.js` | Clonar el repo del curso |

Si `gcloud` responde *"Reauthentication failed. cannot prompt during non-interactive execution"*, la sesión caducó. **No intentes resolverlo tú**: pídele al alumno que ejecute `! gcloud auth login` en el prompt de Claude Code y continúa después.

## Procedimiento (ejecútalo paso a paso)

### Paso 1: Elegir o crear el proyecto de GCP

Lista los proyectos de la cuenta activa:

```bash
gcloud config get-value account
gcloud projects list --format="table(projectId,name)" --limit=50
```

Pregúntale al alumno cuál usar. Si quiere uno nuevo, el ID debe ser único en todo GCP: 6–30 caracteres, minúsculas, dígitos y guiones.

```bash
gcloud projects create rag-toolkit-<algo-unico> --name="RAG Toolkit"
```

Guarda el proyecto elegido en una variable y déjalo como activo:

```bash
PROJECT_ID=<id-elegido>
gcloud config set project "$PROJECT_ID"
```

PowerShell: `$env:PROJECT_ID = "<id-elegido>"; gcloud config set project $env:PROJECT_ID`.

Usa **el mismo proyecto** en la skill `gcp-resource-manager-api-setup`: la API tiene que estar activa en el proyecto dueño del cliente OAuth.

### Paso 2: Leer el puerto del frontend

El origen autorizado debe coincidir **exactamente** con la URL del frontend. Léelo del repo; no lo supongas:

```bash
grep -n "port:" Proyecto-RAGs-v2/Frontend-RAGs/vite.config.js
```

Hoy es `port: 5174` con `strictPort: true`, así que el origen es **`http://localhost:5174`**. Si el alumno cambió el puerto, usa el suyo.

### Paso 3: Pantalla de consentimiento (Google Auth Platform)

Dale al alumno este enlace, con su proyecto ya puesto:

```
https://console.cloud.google.com/auth/overview?project=<PROJECT_ID>
```

Si el proyecto nunca configuró OAuth, la consola muestra **"Get started" / "Comenzar"**. Guíalo por las secciones:

1. **Branding (Información de la app):**
   - Nombre de la app: `RAG Toolkit`.
   - Correo de asistencia al usuario: el suyo.
   - Datos de contacto del desarrollador: el suyo.
2. **Audience (Público):**
   - Tipo de usuario: **Externo**.
     - **Interno** solo aparece si la cuenta pertenece a una organización de Google Workspace, y dejaría fuera a cualquier cuenta @gmail.com.
   - Estado de publicación: **Testing (Prueba)**. **No la publiques.**
   - **Usuarios de prueba → Add users:** añade el correo con el que el alumno va a iniciar sesión en la app. Si otra persona va a probar su app, añade también su correo.
3. **Data access (Acceso a datos) → Add or remove scopes:** añade estos dos scopes de **solo lectura**:
   - `https://www.googleapis.com/auth/cloudplatformprojects.readonly`: ver sus proyectos de GCP, para el desplegable de proyectos.
   - `https://www.googleapis.com/auth/devstorage.read_only`: leer sus buckets y archivos de Cloud Storage.

   Si no aparecen en la lista, búscalos pegando la URL completa del scope.

   **No añadas `cloud-platform`**: daría acceso completo a todo su GCP y la app no lo necesita.

### Paso 4: Crear el ID de cliente OAuth

En la misma consola, abre **Clients (Clientes) → Create client (Crear cliente)**:

```
https://console.cloud.google.com/auth/clients/create?project=<PROJECT_ID>
```

| Campo | Valor |
|---|---|
| Application type (Tipo de aplicación) | **Web application (Aplicación web)** |
| Name (Nombre) | `RAG Toolkit - local` |
| Authorized JavaScript origins (Orígenes autorizados de JavaScript) | `http://localhost:5174`, o el puerto del Paso 2 |
| Authorized redirect URIs (URIs de redirección autorizados) | **Déjalo vacío** |

La app usa el modelo de **token** de Google Identity Services: una ventana emergente devuelve el token directo al navegador, así que no hay redirección.

Al pulsar **Create**, la consola muestra el **Client ID** y un **Client secret**:
- Copia **solo el Client ID**. Termina en `.apps.googleusercontent.com`.
- **No guardes ni pegues el Client secret**: este flujo no lo usa. El Client ID es público por diseño (viaja en el JavaScript del navegador); el secret no.

Google avisa que un cliente nuevo puede tardar **unos minutos** en funcionar (a veces hasta 5).

### Paso 5: Guardar `VITE_GOOGLE_CLIENT_ID` en el frontend

Valida el formato antes de guardarlo:

```bash
CLIENT_ID="<pegar-el-client-id>"
echo "$CLIENT_ID" | grep -Eq '^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$' \
  && echo "Formato OK" || echo "Formato inválido: copia el Client ID, no el secret"
```

Guárdalo en `Proyecto-RAGs-v2/Frontend-RAGs/.env`. El `.gitignore` de la raíz del repo ya lo excluye; compruébalo con `git check-ignore -v Proyecto-RAGs-v2/Frontend-RAGs/.env`.

- Si el archivo **no existe**, créalo con la línea `VITE_GOOGLE_CLIENT_ID=<client-id>`.
- Si **existe** y ya tiene la variable, reemplaza esa línea.
- Si existe sin la variable, añádela al final.
- **No borres otras variables** del archivo.

Mantén también la variable, **vacía**, en `Frontend-RAGs/.env.example`, para que el siguiente alumno sepa que existe: `VITE_GOOGLE_CLIENT_ID=`.

Vite solo lee el `.env` al arrancar: **reinicia `npm run dev`** después de guardarlo.

### Paso 6: Verificar

1. **Origen correcto:** abre `http://localhost:5174`. Debe ser `localhost`, no `127.0.0.1`: para Google son orígenes distintos.
2. En la pestaña **Pipeline de ingesta**, elige la fuente **Bucket de Google Cloud Storage** y pulsa **Conectar con Google**.
3. Inicia sesión con un **usuario de prueba** del Paso 3.
4. **Pantalla "Google no verificó esta app":** es normal en modo Testing. Pulsa **Continuar**.
5. Acepta los dos permisos de solo lectura.
6. **Desplegable de proyectos:** debe llenarse. Si da error 403 `SERVICE_DISABLED`, falta la skill `gcp-resource-manager-api-setup`.

Si el botón **Conectar con Google** todavía no existe en el frontend, la configuración de GCP igual queda lista; verifícala cuando la función esté programada.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `Error 400: origin_mismatch` o `redirect_uri_mismatch` | El origen del navegador no coincide con el autorizado | Revisa puerto y host exactos (`http://localhost:5174`, sin `/` final). Usa `localhost`, no `127.0.0.1`. Espera unos minutos tras editarlo. |
| `Error 403: access_denied` · "solo puede acceder a ella los testers aprobados" | La cuenta no es usuario de prueba | Audience → Test users → añade ese correo. |
| "Google no verificó esta app" | Modo Testing | Normal: **Continuar**. Para quitarlo habría que verificar la app, y para clase no hace falta. |
| `invalid_client` / "The OAuth client was not found" | Client ID mal copiado, cliente borrado o recién creado | Copia de nuevo el ID; espera ~5 min si es nuevo; revisa que el `.env` esté en `Frontend-RAGs/`. |
| El botón no hace nada / no abre ventana | El navegador bloqueó la ventana emergente | Permite ventanas emergentes para `localhost:5174`. |
| `VITE_GOOGLE_CLIENT_ID` vacío en la app | Vite no se reinició o la variable no empieza por `VITE_` | Reinicia `npm run dev`. Solo las variables `VITE_*` llegan al navegador. |
| No aparece "Externo" / solo "Interno" | — | Externo siempre existe. Interno aparece además solo con Google Workspace. Elige **Externo**. |
| La consola pide facturación | No la pide para OAuth | Revisa que estés en Google Auth Platform y no activando otra API de pago. |

## Lo que NO hace esta skill

- No activa APIs: eso es `gcp-resource-manager-api-setup`.
- No crea buckets ni sube PDFs. El bucket es del dueño de los PDFs, no de quien levanta el sistema.
- No publica ni verifica la app. Para clase basta el modo Testing.
- No usa ni guarda el Client secret.

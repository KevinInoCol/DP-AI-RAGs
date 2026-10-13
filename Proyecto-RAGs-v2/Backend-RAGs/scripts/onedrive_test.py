"""
Spike de prueba: conecta a TU OneDrive (cuenta personal) vía Microsoft Graph,
lista tus PDFs y, opcionalmente, los ingesta a Qdrant con el pipeline.

Uso:
  # 1) solo listar los PDFs de tu OneDrive
  python onedrive_test.py <CLIENT_ID>

  # 2) listar + INGESTAR a un tenant (crea la colección tenant_id_<slug>)
  python onedrive_test.py <CLIENT_ID> <nombre_tenant>

CLIENT_ID = el "Application (client) ID" de tu App en Entra ID (ver pasos abajo).
También puedes ponerlo en .env como GRAPH_CLIENT_ID y omitir el argumento.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from pipeline.sources.onedrive import device_login, download, list_pdfs

load_dotenv()


def main() -> None:
    client_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GRAPH_CLIENT_ID")
    tenant = sys.argv[2] if len(sys.argv) > 2 else None

    if not client_id:
        print("Uso: python onedrive_test.py <CLIENT_ID> [nombre_tenant]")
        print("(o define GRAPH_CLIENT_ID en .env)")
        sys.exit(1)

    print("Autenticando con Microsoft (device code)...")
    token = device_login(client_id)

    pdfs = list_pdfs(token)
    print(f"\n✓ Conexión OK · {len(pdfs)} PDF(s) en tu OneDrive:")
    for p in pdfs:
        print(f"  - {p['name']}  ({p['size'] / 1024:.1f} KB)")

    if not tenant:
        print("\n(Para ingestar estos PDFs a Qdrant: python onedrive_test.py <CLIENT_ID> <tenant>)")
        return

    if not pdfs:
        print("\nNo hay PDFs que ingestar.")
        return

    print(f"\nDescargando e ingestando {len(pdfs)} PDF(s) al tenant '{tenant}'...")
    files = [(p["name"], download(token, p["id"])) for p in pdfs]

    from pipeline.orchestrator import ingest_documents

    for evt in ingest_documents(files, tenant):
        if evt.get("event") == "step":
            print(f"  · {evt['step']:11} {evt['status']:8} {evt['label']}")
        elif evt.get("event") == "done":
            print(f"[done] ruta={evt['index_route']} · {evt['num_vectors']} vectores en {evt['collection']}")
        else:
            print(" ", evt)


if __name__ == "__main__":
    main()

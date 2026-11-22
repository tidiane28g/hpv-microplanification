#!/usr/bin/env python3
"""
kobo_sync_campanha.py — Télécharge les soumissions des DEUX formulaires Kobo de la campagne HPV
(Résumé journalier + Supervision) et écrit kobo_cov.json et kobo_sup.json, lus automatiquement
par campanha.html. Aucune dépendance externe (Python 3.8+).

Variables d'environnement
  KOBO_SERVER      ex. kf.kobotoolbox.org   (défaut : kf.kobotoolbox.org)
  KOBO_TOKEN       clé API personnelle Kobo (la même que pour la microplanification)
  KOBO_COV_UID     identifiant du projet « Resumo Diário HPV »
  KOBO_SUP_UID     identifiant du projet « Supervisão HPV »
  KOBO_DROP_FIELDS_CAMPANHA (optionnel) champs supplémentaires à retirer, séparés par des virgules
  KOBO_BASE_URL    (optionnel, tests)

Les champs contenant des noms de personnes sont retirés avant publication (liste ci-dessous).
"""
import datetime, json, os, sys, urllib.error, urllib.request

DROP_DEFAULT = ["supervisor", "supervisor_nome", "nome_supervisor", "responsavel", "responsavel_nome",
                "nome_responsavel", "nome_do_responsavel", "contacto", "telefone", "telemovel",
                "username", "_submitted_by", "_notes", "_attachments", "_validation_status"]


def fetch_all(base, uid, token):
    url = f"{base}/api/v2/assets/{uid}/data/?format=json&limit=1000"
    out, pages = [], 0
    while url and pages < 200:
        req = urllib.request.Request(url, headers={"Authorization": f"Token {token}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
        except urllib.error.HTTPError as e:
            hint = {401: "token invalide", 403: "pas de droit de lecture sur ce projet",
                    404: "UID du projet ou serveur incorrect (projet non déployé ?)"}.get(e.code, "")
            sys.exit(f"ERREUR HTTP {e.code} pour le projet {uid} — {hint}")
        except urllib.error.URLError as e:
            sys.exit(f"ERREUR réseau : {e.reason}")
        out.extend(payload.get("results", []))
        url = payload.get("next")
        pages += 1
    return out


def flatten(r, drop):
    flat = {}
    for k, v in r.items():
        if isinstance(v, (list, dict)) or v is None:
            continue
        flat[k.split("/")[-1]] = v
    geo = r.get("_geolocation")
    if isinstance(geo, list) and len(geo) == 2 and all(isinstance(x, (int, float)) for x in geo):
        flat["_gps_latitude"], flat["_gps_longitude"] = geo
    for d in drop:
        flat.pop(d, None)
    return flat


def sync(name, uid, out, base, token, drop):
    if not uid:
        print(f"[{name}] identifiant du projet non défini — ignoré")
        return
    rows = [flatten(r, drop) for r in fetch_all(base, uid, token)]
    changed = True
    if os.path.exists(out):
        try:
            changed = json.load(open(out, encoding="utf-8")).get("rows") != rows
        except Exception:
            pass
    if changed:
        payload = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   "source": "kobo api", "rows": rows}
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[{name}] {len(rows)} soumissions — {'fichier mis à jour' if changed else 'aucun changement'} ({out})")


def main():
    token = os.environ.get("KOBO_TOKEN", "").strip()
    server = os.environ.get("KOBO_SERVER", "kf.kobotoolbox.org").strip()
    base = os.environ.get("KOBO_BASE_URL", f"https://{server}").rstrip("/")
    drop = DROP_DEFAULT + [x.strip() for x in os.environ.get("KOBO_DROP_FIELDS_CAMPANHA", "").split(",") if x.strip()]
    if not token:
        sys.exit("Définir KOBO_TOKEN (voir LISEZ-MOI).")
    sync("resumo", os.environ.get("KOBO_COV_UID", "").strip(), "kobo_cov.json", base, token, drop)
    sync("supervisao", os.environ.get("KOBO_SUP_UID", "").strip(), "kobo_sup.json", base, token, drop)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
kobo_sync.py — Télécharge les soumissions du formulaire Kobo « Microplanificação HPV »
et écrit kobo_data.json, le fichier lu automatiquement par Dashboard_Microplanificacao_HPV.html.

Aucune dépendance externe (Python 3.8+).

Variables d'environnement
  KOBO_SERVER      ex. kf.kobotoolbox.org  ou  eu.kobotoolbox.org   (défaut : kf.kobotoolbox.org)
  KOBO_ASSET_UID   identifiant du projet (ex. aBcD1234...) — voir le guide
  KOBO_TOKEN       clé API personnelle Kobo (Paramètres du compte > Sécurité)
  KOBO_DROP_FIELDS (optionnel) champs à retirer avant publication, ex. responsavel,funcao,val_nome,val_funcao
  KOBO_BASE_URL    (optionnel, tests) remplace https://<KOBO_SERVER>

Options
  --out FICHIER    fichier JSON de sortie (défaut : kobo_data.json)
  --embed FICHIER  réécrit aussi l'instantané intégré d'un dashboard .html (utile hors-ligne / pour envoi par e-mail)
"""
import argparse, datetime, json, os, re, sys, urllib.error, urllib.request


def fetch_all(base_url, uid, token):
    url = f"{base_url}/api/v2/assets/{uid}/data/?format=json&limit=1000"
    results, pages = [], 0
    while url and pages < 200:
        req = urllib.request.Request(url, headers={"Authorization": f"Token {token}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
        except urllib.error.HTTPError as e:
            hint = {401: "token invalide", 403: "pas de droit de lecture sur ce projet",
                    404: "UID du projet ou serveur incorrect (projet non déployé ?)"}.get(e.code, "")
            sys.exit(f"ERREUR HTTP {e.code} sur {url} — {hint}")
        except urllib.error.URLError as e:
            sys.exit(f"ERREUR réseau : {e.reason}")
        results.extend(payload.get("results", []))
        url = payload.get("next")
        pages += 1
    return results


def short(key):
    return key.split("/")[-1]


def flatten(obj):
    """Garde les valeurs simples avec le dernier segment du chemin comme nom (ident/regiao -> regiao)."""
    flat = {}
    for k, v in obj.items():
        if isinstance(v, (list, dict)) or v is None:
            continue
        flat[short(k)] = v
    return flat


def build_payload(results, drop):
    main, sites = [], []
    for r in results:
        m = flatten(r)
        m["_id"] = r.get("_id")
        m["_submission_time"] = r.get("_submission_time")
        main.append(m)
        reps = r.get("sites")
        if reps is None:
            reps = next((v for k, v in r.items() if k.endswith("/sites") and isinstance(v, list)), [])
        for s in reps or []:
            sf = flatten(s)
            sf["_submission__id"] = r.get("_id")
            sites.append(sf)
    for rows in (main, sites):
        for row in rows:
            for d in drop:
                row.pop(d, None)
    return {"main": main, "sites": sites}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="kobo_data.json")
    ap.add_argument("--embed")
    a = ap.parse_args()

    uid = os.environ.get("KOBO_ASSET_UID", "").strip()
    token = os.environ.get("KOBO_TOKEN", "").strip()
    server = os.environ.get("KOBO_SERVER", "kf.kobotoolbox.org").strip()
    base = os.environ.get("KOBO_BASE_URL", f"https://{server}").rstrip("/")
    drop = [x.strip() for x in os.environ.get("KOBO_DROP_FIELDS", "").split(",") if x.strip()]
    if not uid or not token:
        sys.exit("Définir KOBO_ASSET_UID et KOBO_TOKEN (voir LISEZ-MOI.md).")

    results = fetch_all(base, uid, token)
    payload = build_payload(results, drop)

    # n'écrit que si les données ont changé (évite un commit toutes les 10 min)
    changed = True
    if os.path.exists(a.out):
        try:
            old = json.load(open(a.out, encoding="utf-8"))
            changed = (old.get("main"), old.get("sites")) != (payload["main"], payload["sites"])
        except Exception:
            pass
    payload = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "source": "kobo api", **payload}
    if changed:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(payload['main'])} soumissions, {len(payload['sites'])} locaux — "
          f"{'fichier mis à jour' if changed else 'aucun changement'} ({a.out})")

    if a.embed:
        html = open(a.embed, encoding="utf-8").read()
        blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        new, n = re.subn(r"/\*SNAPSHOT_START\*/.*?/\*SNAPSHOT_END\*/",
                         lambda m: "/*SNAPSHOT_START*/" + blob + "/*SNAPSHOT_END*/", html, flags=re.S)
        if n != 1:
            sys.exit("Marqueurs SNAPSHOT introuvables dans " + a.embed)
        open(a.embed, "w", encoding="utf-8").write(new)
        print("Instantané intégré mis à jour dans", a.embed)


if __name__ == "__main__":
    main()

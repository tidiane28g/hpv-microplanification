# À placer dans le dépôt GitHub sous : .github/workflows/kobo-sync-campanha.yml
name: Sync Kobo Campanha -> kobo_cov.json et kobo_sup.json

on:
  schedule:
    - cron: "3-59/10 * * * *"    # toutes les ~10 minutes (GitHub peut retarder)
  workflow_dispatch:              # bouton "Run workflow"

permissions:
  contents: write

concurrency:
  group: kobo-sync-campanha
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Télécharger les données Kobo
        run: python kobo_sync_campanha.py
        env:
          KOBO_SERVER: ${{ secrets.KOBO_SERVER }}
          KOBO_TOKEN: ${{ secrets.KOBO_TOKEN }}
          KOBO_COV_UID: ${{ secrets.KOBO_COV_UID }}
          KOBO_SUP_UID: ${{ secrets.KOBO_SUP_UID }}
          KOBO_DROP_FIELDS_CAMPANHA: ${{ secrets.KOBO_DROP_FIELDS_CAMPANHA }}
      - name: Publier si changement
        run: |
          git config user.name "kobo-sync"
          git config user.email "kobo-sync@users.noreply.github.com"
          for f in kobo_cov.json kobo_sup.json; do [ -f "$f" ] && git add "$f"; done
          if ! git diff --staged --quiet; then
            git commit -m "Mise à jour des données Kobo (campagne)"
            git push || (git pull --rebase && git push)
          fi

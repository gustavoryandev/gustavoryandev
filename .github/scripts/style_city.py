name: GitHub-Profile-3D-Contrib

on:
  schedule:
    - cron: "45 */12 * * *" # a cada 12 horas (offset para não colidir com os outros workflows)
  workflow_dispatch: # permite rodar manualmente na aba Actions

permissions:
  contents: write # necessário para commitar o SVG

jobs:
  build:
    runs-on: ubuntu-latest
    name: generate-github-profile-3d-contrib
    steps:
      - uses: actions/checkout@v4

      - uses: yoshi389111/github-profile-3d-contrib@latest
        env:
          # Usa o token pessoal (secret GH_PAT) se existir; senão, o token padrão
          GITHUB_TOKEN: ${{ secrets.GH_PAT || secrets.GITHUB_TOKEN }}
          USERNAME: ${{ github.repository_owner }}
          SETTING_JSON: conf/github-profile-3d-contrib.json

      # cantos arredondados e borda #1E1E1E, igual aos outros cards
      - name: Estilizar o card
        run: python3 .github/scripts/style_city.py profile-3d-contrib/profile-city.svg

      - name: Commitar a cidade
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add profile-3d-contrib/
          git diff --cached --quiet || git commit -m "chore: atualiza GitHub City"
          git pull --rebase
          git push

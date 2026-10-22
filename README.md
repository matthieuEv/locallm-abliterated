# LocalLM abliterated — OpenCode V2 + Rapid-MLX

Un agent de code local sur Mac Apple Silicon : une commande installe et configure
OpenCode **stable 2.x**, télécharge le modèle
[`Youssofal/Qwen3.6-35B-A3B-Abliterated-Heretic-MLX-4bit`](https://huggingface.co/Youssofal/Qwen3.6-35B-A3B-Abliterated-Heretic-MLX-4bit),
démarre Rapid-MLX en arrière-plan, attend qu’il soit prêt, puis ouvre OpenCode.
Rapid-MLX s’arrête lorsque tu quittes OpenCode.

**Ce setup utilise ta configuration utilisateur globale.** `start` remplace
`opencode.json`, supprime le fichier concurrent `opencode.jsonc` et copie les
instructions du repo. `destroy` efface la configuration globale, les identifiants
enregistrés par OpenCode, les conversations, l’installation et le modèle indiqué
ci-dessus. Aucune sauvegarde ni confirmation interactive n’est effectuée.
Le repo et les fichiers de tes projets restent intacts.

## Pré requis

- Mac **Apple Silicon**, macOS 14 ou plus récent ; terminal natif, sans Rosetta.
- Internet pour les installations et le téléchargement initial.
- Le modèle occupe environ **24,6 Go sur disque**. Le script vérifie les fichiers
  manquants et exige **6 Gio libres supplémentaires** avant de commencer.
- La RAM doit accueillir le modèle, ses caches et macOS. Le profil de départ vise
  les Mac M4 Pro de 36–48 Go ; les performances de ce checkpoint doivent être
  mesurées sur ta machine, particulièrement à contexte long.

Si nécessaire, `locallm` installe automatiquement [uv](https://docs.astral.sh/uv/)
dans `~/.local/bin`, puis utilise Python 3.12 géré par uv. Pas de sudo, Docker,
Open WebUI, SearXNG ou modification de `.zshrc`.

## Start

```sh
git clone git@github.com:matthieuEv/locallm-abliterated.git
cd locallm-abliterated
./locallm start /chemin/absolu/vers/ton-projet
```

Depuis un clone déjà présent :

```sh
/chemin/vers/locallm-abliterated/locallm start "$PWD"
```

Sans chemin, OpenCode travaille dans le dossier courant. Pour reprendre une session
qui n’a pas été détruite :

```sh
./locallm start /chemin/vers/ton-projet -s ses_IDENTIFIANT
```

Chaque `start` cherche la dernière version **stable de la branche 2.x** dans les
métadonnées officielles, l’installe avec l’installateur V2, et vérifie sa version.
Les mises à jour internes sont désactivées : c’est `start` qui les gère.
Rapid-MLX est fixé à **0.16.6**, version dont les options ont été vérifiées.
Un téléchargement déjà présent dans le cache Hugging Face est réutilisé.

Le port **127.0.0.1:8000** doit être libre. Le script refuse un port occupé et ne
tue pas un serveur inconnu. Arrête ton ancien serveur avant le premier lancement.
Il refuse également les installations concurrentes d’OpenCode/Rapid-MLX dans le
PATH : retire celles gérées par npm/Homebrew avant d’utiliser ce setup. L’installation
standalone OpenCode dans `~/.opencode` et Rapid-MLX via uv sont prises en charge.

OpenCode utilise `--standalone` : son serveur privé suit la session, sans service
OpenCode persistant. Un ancien service OpenCode est arrêté avant la mise à jour.
Le watchdog de Rapid-MLX l’arrête aussi si le superviseur disparaît brutalement.

Quitter OpenCode libère la mémoire du modèle. Les installations, sessions et poids
restent sur disque jusqu’à `destroy` ; le prochain `start` peut les réutiliser.

## Logs de la session courante

Dans un deuxième terminal :

```sh
LOGS="${XDG_STATE_HOME:-$HOME/.local/state}/locallm-abliterated/current"
tail -n 100 -F "$LOGS/rapid-mlx.log"
```

Pour les logs OpenCode, ou les deux ensemble :

```sh
tail -n 100 -F "$LOGS/opencode.log"
tail -n 100 -F "$LOGS/rapid-mlx.log" "$LOGS/opencode.log"
```

`current` désigne le dernier lancement ayant atteint le chargement du serveur.
Les logs des installations et du téléchargement s’affichent dans le terminal de
`start`. Les journaux précédents restent dans le sous-dossier `logs/` jusqu’à
`destroy`.

## Destroy

```sh
/chemin/vers/locallm-abliterated/locallm destroy
```

Peut se lancer depuis un autre terminal pendant une session : le superviseur
actif est arrêté, puis les processus et les données sont nettoyés. **Les sessions
ne seront plus récupérables après cette commande.** Fais tes propres sauvegardes
avant si tu en veux.

La commande supprime :

- OpenCode standalone : `~/.opencode`.
- Configuration, authentification, sessions, bases, snapshots, caches et logs
  OpenCode : `~/.config/opencode`, `~/.local/share/opencode`,
  `~/.local/state/opencode`, `~/.cache/opencode` et son répertoire temporaire.
- Rapid-MLX et ses alias, désinstallés avec `uv tool uninstall rapid-mlx`.
- Configuration et caches Rapid-MLX : `~/.config/rapid-mlx`, `~/.rapid-mlx`,
  `~/.cache/rapid-mlx`, `~/.local/state/rapid-mlx`.
- Les anciens helpers `~/.local/bin/start-rapid-mlx` et `bench-rapid-mlx`.
- Toutes les révisions en cache du **modèle Youssofal indiqué ci-dessus** et ses
  verrous Hugging Face.
- L’état et les logs de ce lanceur : `~/.local/state/locallm-abliterated`.

Les variables `XDG_*`, `HF_HOME`, `HF_HUB_CACHE` et `UV_TOOL_BIN_DIR` sont respectées.
Utilise le même environnement pour `start` et `destroy`.
Les autres modèles Hugging Face et les dossiers `.opencode` appartenant aux projets
restent en place. uv, son Python et ses caches partagés restent disponibles comme
prérequis système : ils peuvent servir à tes autres applications. Le repo n’est
jamais une destination d’installation ou de suppression.

## Configuration versionnée

| Fichier | Destination et rôle |
| --- | --- |
| `config/opencode.json` | `~/.config/opencode/opencode.json` : modèle et agent |
| `config/local-context.md` | `~/.config/opencode/local-context.md` : exploration concise |
| `config/rapid-mlx.json` | `~/.config/rapid-mlx/locallm.json` : version et flags serveur |

Modifie ces fichiers dans le repo, puis relance `start`. Les configurations
propres aux projets et les réglages administrateur OpenCode peuvent également
affecter la configuration effective. Le modèle demandé est sélectionné par défaut.

| Budget | Valeur |
| --- | ---: |
| Fenêtre totale | 32 768 tokens |
| Entrée maximale | 28 672 tokens |
| Sortie | 4 096 tokens |
| Compaction automatique | activée |
| Contexte récent conservé | 8 000 tokens |
| Marge de compaction | 2 048 tokens |
| Seuil calculé avec OpenCode 2.1.2 | 26 624 tokens |

Le serveur utilise le même budget. Prefix cache de **4 Gio**, **une entrée
hybride**, KV **bf16**, prefill de **2 048 tokens**, **une génération à la fois**,
plafond Metal à **70 %** du budget recommandé par MLX. Mode texte, thinking
désactivé ; TurboQuant, spéculation et PFlash désactivés pour ce profil initial.
La quantification 4/6 bits des **poids du modèle** est conservée.

Le serveur lie uniquement l’interface locale. La clé `local` est une valeur de
compatibilité du client, pas une authentification serveur. Les poids sont locaux ;
les recherches web et téléchargements nécessitent Internet. Aucun fournisseur de
recherche n’est imposé : choisis celui proposé par OpenCode lorsque nécessaire.

Un grand résultat d’outil peut dépasser la marge avant la compaction. Un contexte
plus grand augmente le coût d’un prefill sans cache : ce profil ne garantit ni une
latence constante ni l’absence de swap. Les mesures de l’ancien 27B ne sont pas des
mesures de ce nouveau modèle.

## Vérification

```sh
uv run --no-project --no-config --python 3.12 -m unittest -v test_setup.py
sh -n locallm
```

Les tests utilisent des dossiers temporaires et des processus simulés : budgets,
copie de configuration, manque d’espace, port occupé, choix d’une version stable
2.x, suppression des sessions et du modèle, conservation du code et protection
contre un PID réutilisé. Ils ne détruisent pas ton installation réelle.

Pendant une session, pour vérifier l’identité du modèle :

```sh
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8000/v1/models
```

Sources : [installation officielle OpenCode V2](https://opencode.ai/v2/docs/),
[configuration V2](https://opencode.ai/v2/docs/config/),
[compaction](https://opencode.ai/v2/docs/compaction/),
[Rapid-MLX CLI](https://rapidmlx.com/docs/cli),
[options de performance](https://rapidmlx.com/docs/perf-flags).

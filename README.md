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
- La RAM doit accueillir le modèle, ses caches et macOS. Le profil 48k a été
  mesuré sur un **M4 Pro de 48 Gio** de mémoire unifiée, pas 36 Gio. Sur une autre
  machine, particulièrement avec moins de RAM, il faut remesurer mémoire, swap
  et latence avant de considérer ce profil comme stable.

Le lanceur est entièrement en **Bash**, compatible avec le Bash 3.2 fourni par
macOS. Il utilise les outils système `curl`, `lockf`, `lsof`, `realpath` et **jq**
pour lire les fichiers JSON. Si jq manque :

```sh
brew install jq
```

Si nécessaire, `locallm` installe automatiquement [uv](https://docs.astral.sh/uv/)
dans `~/.local/bin`. **Il n'y a plus de script Python dans le repo**, ni de commande
Python à exécuter pour piloter le setup ou ses tests. Rapid-MLX reste une application
Python : uv gère automatiquement son interpréteur 3.12 et ses dépendances internes.
Pas de sudo, Docker, Open WebUI, SearXNG ou modification de `.zshrc`.

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
Si le service de métadonnées OpenCode est indisponible (notamment HTTP 403),
`start` consulte les versions du paquet officiel `@opencode/cli` sur npm. Les
préversions et les versions 3.x restent exclues. Le numéro de version n'est pas
figé dans le repo : il est recherché à nouveau à chaque lancement.
Rapid-MLX est fixé à **0.16.6**, version dont les options ont été vérifiées.
Ses dépendances sont résolues à l'installation : ce numéro seul ne fige pas
l'ensemble de l'environnement Python.
Un téléchargement déjà présent dans le cache Hugging Face est réutilisé.

Le port **127.0.0.1:8000** doit être libre. Le script refuse un port occupé et ne
tue pas un serveur inconnu. Arrête ton ancien serveur avant le premier lancement.
Il refuse également les installations concurrentes d’OpenCode/Rapid-MLX dans le
PATH : retire celles gérées par npm/Homebrew avant d’utiliser ce setup. L’installation
standalone OpenCode dans `~/.opencode` et Rapid-MLX via uv sont prises en charge.

OpenCode utilise `--standalone` : son serveur privé suit la session, sans service
OpenCode persistant. Un ancien service OpenCode est arrêté avant la mise à jour.
Le watchdog de Rapid-MLX l’arrête aussi si le superviseur disparaît brutalement.
Le verrou système `lockf` empêche deux superviseurs simultanés et se libère à la
fin du processus. Les identités PID/date de création sont contrôlées avant de
signaler les processus enregistrés ; un PID réutilisé ne doit pas être arrêté.

**Lancer `opencode` seul ne lance pas Rapid-MLX.** C’est `./locallm start` qui
orchestre les deux processus. Attends le message « Rapid-MLX prêt » avant
l’ouverture d’OpenCode ; pendant le chargement, suis `rapid-mlx.log` depuis le
deuxième terminal. Le script n’installe aucun démarrage automatique à la connexion
macOS. Pour arrêter volontairement les deux, quitte OpenCode ; pendant le chargement,
Ctrl-C dans le terminal `start` demande leur arrêt. Un arrêt peut attendre la fin
d’une requête avant de libérer la mémoire ; le superviseur force l’arrêt après
son délai de nettoyage. Fermer la session ne lance pas `destroy`.

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
  verrous Hugging Face. Lorsque Rapid-MLX est installé, `rapid-mlx rm --yes`
  nettoie d'abord ce modèle via le gestionnaire de cache Hugging Face, avant la
  désinstallation : les blobs partagés encore utilisés par d'autres modèles
  sont conservés. Si ce nettoyage échoue, `destroy` s'arrête avec l'erreur plutôt
  que d'annoncer une libération de disque non réalisée.
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
| `config/local-context.md` | `~/.config/opencode/local-context.md` : lectures ciblées, preuves et journal de travail |
| `config/rapid-mlx.json` | `~/.config/rapid-mlx/locallm.json` : version et flags serveur |

Modifie ces fichiers dans le repo, puis relance `start`. Les configurations
propres aux projets et les réglages administrateur OpenCode peuvent également
affecter la configuration effective. Le modèle demandé est sélectionné par défaut.

| Budget | Valeur |
| --- | ---: |
| Fenêtre totale | 49 152 tokens (48k) |
| Entrée maximale | 40 960 tokens |
| Sortie | 8 192 tokens |
| Compaction automatique | activée |
| Contexte récent demandé | 4 000 tokens, approximatifs |
| Marge de compaction | 4 096 tokens |
| Seuil calculé avec OpenCode 2.1.2 | 36 864 tokens |

Les budgets client/serveur coïncident : **40 960 + 8 192 = 49 152**.
La compaction commence donc vers **75 %** de la fenêtre affichée, avant que
l’entrée maximale soit atteinte. Le seuil doit être revérifié lors d’une mise à
jour d’OpenCode : le lanceur vérifie les budgets statiques, pas chaque changement
du fonctionnement interne de la compaction.

Le serveur utilise le même budget. Prefix cache de **4 Gio**, **une entrée
hybride**, KV **bf16**, prefill de **2 048 tokens**, **une génération à la fois**,
plafond Metal à **80 %** du budget recommandé par MLX : environ **32,2 Go** sur
le M4 Pro 48 Gio mesuré, et non 80 % des 48 Gio physiques. Mode texte, thinking
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

## Compaction, recherches et mémoire de travail

Le setup utilise la **compaction native d’OpenCode**. L’ancien plugin local
`local.rapid-compaction` est explicitement désactivé dans `plugins`, s’il est
encore présent dans la configuration utilisateur. Il n’est ni copié ni effacé
par `start` ; les autres plugins découverts restent autorisés. Un projet peut
néanmoins ajouter une surcharge : vérifier sa configuration. Le plugin expérimental
produisait parfois des résumés identiques, avec un plan de reprise périmé et deux
requêtes de résumé d’environ 50 secondes chacune. Il ne constitue pas un correctif
fiable et n’est donc pas inclus dans le profil actif.

Cela ne prouve pas que la compaction native résout tous les problèmes : sur
OpenCode 2.1.2, `keep.tokens` pouvait retenir un échange autonome entier, puis
échouer avec « The compaction request cannot be reduced further… ». Une nouvelle
version doit être mesurée en travail réel. Le profil 48k et le journal réduisent
certains risques ; ils ne garantissent pas l’absence de boucles ni de perte de détails.

Les consignes demandent à l’agent de :

- Chercher les fichiers/symboles puis commencer par `read` avec `offset` / `limit`
  sur environ 80–120 lignes, en élargissant lorsque la justesse du travail l’exige.
- Créer ou actualiser `WORKLOG.md` dans **le projet actif** pour les tâches à
  plusieurs étapes : courte synthèse en tête, découvertes, preuves, tests,
  tentatives échouées et prochaine action non résolue.
- Mettre à jour les entrées concernées après chaque résultat significatif, avant
  de lancer la recherche suivante, sans recopier tout le journal, le code ou les logs.
- Relire d’abord la synthèse après une compaction, vérifier les contradictions
  et consulter le code actuel pertinent avant de le modifier.
- Distinguer faits observés, affirmations documentées, inférences et inconnues,
  ainsi que labo local, fichiers analysés et environnement actuel. Une mention
  `aarch64` dans un ancien script ne prouve pas l’architecture d’une autre machine.

Le lanceur ne crée pas de journal vide et n’écrase pas celui d’un projet. Ce sont
des **consignes données au modèle**, pas un plugin imposant les écritures ou les
plages de lecture. Il faut vérifier que le fichier change réellement : dans une
session observée, six compactions et 90 appels au modèle avaient eu lieu sans
nouvelle écriture du journal. `destroy` conserve les fichiers des projets, donc
leurs journaux, mais efface l’historique OpenCode.

Le plafond générique de sorties d’outils reste **200 lignes / 12 000 octets**.
`read` a ses propres limites de page : réduire ce plafond seul ne borne pas les
lectures de fichiers. Les lectures ciblées n'imposent pas de plafond supplémentaire
à la génération de code, qui conserve le budget de sortie de 8 192 tokens.

## Mesures disponibles et diagnostic

Mesure du 22 octobre sur ce M4 Pro 48 Gio, avec le modèle Youssofal et le profil
48k : une entrée synthétique de **37 869 tokens** a donné **72,31 s de TTFT** à
froid ; l’extension de 37 966 tokens réutilisait 37 854 tokens et a donné **0,74 s**.
Le décodage était d’environ **61,5–63,3 tokens/s**, le pic Metal de **26,17 Go** et
l’entrée de cache d’environ **987 Mio**, dans le budget de 4 Gio. Le swap n’a pas
augmenté pendant cet essai ; cela ne prouve pas l’absence de swap en usage prolongé.
Ces résultats concernent des requêtes précises et ne sont pas un benchmark du
dernier OpenCode installé automatiquement.

La mesure d’une session de code attribuait environ **47 %** du nouveau contenu
aux lectures de fichiers et **25 %** aux résultats shell. Les relectures identiques
se produisaient après compaction : un résultat perdu dans le résumé peut être
recherché à nouveau. Il faut suivre à la fois les résumés et le travail entre eux.

- `13.6K in · 1.7K out` sur une compaction décrit sa requête de résumé, pas la
  fenêtre totale ni la quantité de contexte disponible.
- Le cache accélère le préremplissage ; les tokens réutilisés occupent toujours
  le contexte. N’augmente pas automatiquement son plafond à 8 Gio.
- Mesure séparément TTFT, tokens de préfixe réutilisés et débit de décodage.
  `tokens produits / durée totale` mélange préremplissage et décodage.
- `ConnectionRefused` signifie que le client n’a pas de connexion à l’endpoint.
  Consulter le log et vérifier `/health/ready` avant de conclure à un problème de modèle.
- `rapid-mlx ls` pouvait sous-estimer le disque utilisé quand les poids étaient
  des liens vers des blobs partagés : une petite taille affichée ne prouve pas
  que le téléchargement des poids manque.

Pour consulter l’état serveur et les statistiques des trois derniers jours :

```sh
curl -fsS http://127.0.0.1:8000/v1/status
opencode stats --days 3 --cost --models
```

Le mode privé `--standalone` n’est pas nécessairement celui découvert par une
autre commande CLI : vérifier le serveur sélectionné avant d’utiliser une commande
de gestion sur une session active. Les statistiques ne reconstituent pas les
sessions supprimées par `destroy`.

## Vérification

```sh
./test_locallm.sh
/bin/bash -n locallm test_locallm.sh
```

Les tests sont eux aussi en Bash. Ils utilisent des HOME temporaires et de faux
exécutables OpenCode/Rapid-MLX/uv/curl : pas de téléchargement de poids, de
requête externe ni de suppression de l'installation réelle. Ils exercent le
parcours du lanceur, les budgets, le repli des métadonnées, les chemins avec
espaces, les liens symboliques, les échecs de démarrage, le verrou et le nettoyage.
Les commandes `destroy` des tests ne visent que ces installations temporaires.

Validation de la migration Bash, le **23 octobre 2026** : **17 scénarios** de test
et syntaxe Bash vérifiés. Un faux client a aussi été lancé dans un vrai terminal
PTY : l'entrée clavier, la sortie du client, Ctrl-C et l'arrêt du faux serveur
ont été vérifiés. `setup.py`, `test_setup.py` et leurs caches locaux ont été retirés ; les
réglages du modèle et les commandes publiques `start` / `destroy` sont conservés.

Avant la migration Bash, les fichiers de configuration avaient également été
chargés avec le vrai binaire OpenCode 2.1.2 dans un HOME et un service temporaires :
le catalogue effectif exposait **49 152 / 40 960 / 8 192** et l'ancien plugin
`local.rapid-compaction` restait désactivé. Les 25 options serveur, watchdog inclus,
avaient été vérifiées dans l'aide du Rapid-MLX 0.16.6 installé. Les tests isolés
ci-dessus ne modifient jamais l'installation réelle.

### Cycle réel vérifié le 23 octobre 2026

Un cycle **`destroy → start → fermeture d'OpenCode → destroy`** a ensuite été
exécuté sur le Mac M4 Pro 48 Gio, avec suppression de l'ancien setup et de ses
sessions, puis réinstallation dans les emplacements utilisateur habituels :

- Installation automatique d'**OpenCode 2.1.4 stable** et **Rapid-MLX 0.16.6**.
- Nouveau téléchargement complet du modèle Youssofal : **22,9 Gio**, en **12 min
  42 s** sur cette connexion. Cette durée concerne le téléchargement.
- Copie des configurations, chargement du modèle en arrière-plan et ouverture du
  vrai client OpenCode en terminal. `opencode debug config` confirme les budgets
  **49 152 / 40 960 / 8 192**, les instructions et la compaction configurée ;
  `/health/ready` et `/v1/models` confirment le modèle attendu.
- Dans un projet temporaire neutre, l'agent a d'abord essayé un chemin incorrect,
  puis retrouvé le fichier avec `glob`, réussi l'appel `read` et répondu
  exactement `LOCAL_SETUP_OK`. Aucun fichier du projet utilisateur n'a été modifié.
- Premier préremplissage de **8 819 tokens** : **11,9 s de TTFT** ; trois appels
  suivants réutilisent le préfixe et donnent **0,5–0,6 s de TTFT**. Pic Metal
  **26,41 Go**, entrée de prefix cache d'environ **423 Mio** en fin de test.
  Ce court échange ne mesure pas le débit de décodage ni les compactions longues.
- Quitter OpenCode arrête Rapid-MLX et rend le port 8000 disponible. `destroy`
  supprime ensuite les installations, les configurations, la base des sessions et
  le modèle, avec **22,9 Gio libérés**. Les chemins et PID enregistrés ont été
  contrôlés après suppression ; repo, projets et autre outil uv sont conservés.
  Un second `destroy` sur l'installation déjà supprimée réussit aussi.

Aucun correctif du lanceur n'a été nécessaire pendant ce cycle. **Limite observée :
le swap système est passé d'environ 1,8 à 5,5 Gio pendant l'installation, le
téléchargement et le chargement.** Cet essai ne permet pas d'en attribuer la cause
au seul modèle et ne valide pas une utilisation prolongée sans swap. Les contraintes
de qualité des compactions restent celles décrites plus haut. L'état final du test
est un setup supprimé ; le prochain `start` retéléchargera donc les poids.

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

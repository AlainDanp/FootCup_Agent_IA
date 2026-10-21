# Modifications - équipe balanced améliorée

Dézippe ce dossier PAR-DESSUS `agentic-football-sample-agents/` (mêmes chemins), puis déploie `ai-team-strands-balanced` comme d'habitude.

## lib/ (partagé par toutes les équipes, rétro-compatible)
- `agent_base.py` : agent sans historique à chaque tick (avant : l'historique des ticks précédents s'accumulait) ; timeout LLM à 3,5 s -> fallback ; latence loguée dans CloudWatch ("LLM latency") ; nouvelle couche 0 `fast_rules` avant le LLM.
- `fast_rules.py` (nouveau) : décisions instantanées sans LLM
  - j'ai le ballon près du but -> SHOOT côté opposé au gardien (MID < 20, FWD < 24 unités)
  - gardien 100 % par règles (placement sur la ligne, INTERCEPT si ballon libre dans la surface, relance vers le coéquipier le plus libre)
  - ballon libre et je suis le joueur de champ le plus proche -> j'y vais (évite que tout le monde coure dessus)
- `state.py` : ajoute au résumé : consignes du coach (`teamChat`), situation (mène/perd, temps restant, plan), joueur le plus proche du ballon, position du gardien adverse, `open=` (espace autour de chaque coéquipier).
- `prompt_common.py` (nouveau) : bloc commun des prompts (commandes + format), plus court = plus rapide.

## Équipe balanced
- Prompts réécrits par poste (rôles, zones gauche/droite pour les 2 attaquants, pressing haut, contre-attaque).
- MID : Nova Pro -> Nova Lite (Pro trop lent pour la limite de 5 s).

## À vérifier au 1er match d'entraînement
1. Les tirs partent-ils du côté opposé au gardien ? Sinon : `FLIP_AIM = True` dans `lib/fast_rules.py`.
2. Logs CloudWatch : "LLM latency" < 2 s, peu de "LLM timeout" / "fallback".
3. Envoie une consigne coach et vérifie que les joueurs changent de comportement.

## Sécurité coach (v2)
- Les messages coach sont entendus par les 10 joueurs : nos agents n'obéissent qu'aux messages contenant le mot de code de `lib/team_config.py` (`DNP7` par défaut).
- Mets dans `PLAYER_NAMES` les noms saisis sur la page My Team.
- Exemples : `DNP7 everyone press high` (toute l'équipe), `DNP7 Attaquant1 shoot now` (seulement ce joueur).

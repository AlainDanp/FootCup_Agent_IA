# ⚽ Les 5 Prodiges — Équipe d'agents IA pour l'AWS Agentic Football Cup

Équipe de **5 agents IA autonomes** qui jouent des matchs de football 5 contre 5 en temps réel, réalisée lors du workshop **AWS Agentic Football Cup** (ESIEA, octobre 2026).

Chaque joueur est un agent séparé, déployé sur **Amazon Bedrock AgentCore**. Toutes les ~2 secondes, le serveur de match envoie l'état du jeu à chaque agent, qui doit répondre en moins de **5 secondes** par une commande JSON (se déplacer, passer, tirer, presser, marquer…).

**Résultat :** victoire 1-0 contre l'équipe de référence AWS *The Benchmark FC* en match d'entraînement (MVP : le gardien).

> Projet construit à partir des agents d'exemple AWS [`aws-samples/sample-ai-possibilities`](https://github.com/aws-samples/sample-ai-possibilities/tree/main/agentic-football-sample-agents). Ce dépôt documente mes modifications.

---

## Stack

| Outil | Rôle |
|---|---|
| **Strands Agents SDK** (Python) | Framework des agents |
| **Amazon Bedrock** — Nova Micro / Nova Lite | Modèles qui prennent les décisions |
| **Amazon Bedrock AgentCore** | Hébergement serverless des 5 agents |
| **AWS CDK** + AgentCore CLI | Déploiement (infrastructure as code) |
| **Amazon CloudWatch** | Logs et latence des agents |

---

## Architecture

```
Serveur de match (AWS)                Mon compte AWS
┌──────────────────┐   toutes les   ┌───────────────────────────────┐
│ Physique, règles │ ──── ~2 s ───► │ 5 agents sur AgentCore        │
│ Player Portal 3D │ ◄── JSON ───── │ (GK, DEF, MID, FWD1, FWD2)    │
└──────────────────┘                │        │                      │
                                    │        ▼                      │
                                    │ Amazon Bedrock (Nova)         │
                                    └───────────────────────────────┘
```

Chaque agent décide en **4 couches**, de la plus rapide à la plus sûre :

```
État du jeu
   │
   ├─ 0. Règles rapides (fast_rules.py)  → décision instantanée, sans LLM
   │      ↓ aucune règle ne s'applique
   ├─ 1. LLM (Nova)                       → décision tactique, limite de 3,5 s
   │      ↓ timeout ou JSON invalide
   ├─ 2. Plan de secours par poste        → règles simples (fallback.py)
   │      ↓ erreur
   └─ 3. Commande de sécurité             → le joueur ne reste jamais bloqué
```

---

## Mes améliorations

### 1. Règles rapides avant le LLM (`lib/fast_rules.py`)
Un appel LLM coûte du temps alors que la limite est de 5 s. Les situations évidentes sont donc tranchées par du code :
- **Tir automatique** quand un joueur a le ballon près du but, du côté opposé au gardien adverse.
- **Gardien 100 % déterministe** : placement sur la ligne, sortie sur ballon libre dans la surface, relance vers le coéquipier le plus libre. Zéro latence LLM.
- **Un seul joueur va sur le ballon libre** (le plus proche), pour éviter que toute l'équipe coure dessus.

### 2. Appels LLM sans historique et limités dans le temps (`lib/agent_base.py`)
- Dans le code d'origine, un seul agent Strands servait pendant tout le match et accumulait l'historique des ticks précédents. Résultat : des prompts plus longs, une latence plus haute et un modèle qui raisonne sur des positions périmées. Ici, **chaque tick repart d'un contexte vide**.
- **Limite de 3,5 s** sur l'appel au LLM ; au-delà, le plan de secours prend le relais.
- La latence de chaque appel est écrite dans CloudWatch.

### 3. Un état du jeu plus riche pour le LLM (`lib/state.py`)
- Situation du match : mène / est mené, temps restant, plan adapté (*protéger le score* ou *tout attaquer* dans les 90 dernières secondes).
- `open=` : espace libre autour de chaque coéquipier, pour mieux choisir les passes.
- Joueur le plus proche du ballon et position du gardien adverse.

### 4. Consignes du coach protégées (`lib/team_config.py`)
Pendant un match, les messages du coach sont **reçus par les 10 joueurs, adversaires compris**. Un coach adverse pourrait donc donner des ordres à mon équipe : c'est une forme d'**injection de prompt**.
- Mes agents n'obéissent qu'aux messages qui contiennent un **mot de code secret**.
- Un message qui nomme un joueur ne s'applique qu'à lui : `CODE Sniper shoot now`.

### 5. Prompts réécrits (`lib/prompt_common.py` + `ai-*/src/main.py`)
- Bloc commun (commandes, format de sortie) séparé du rôle de chaque joueur : des prompts plus courts, donc plus rapides.
- Rôles précis : deux attaquants sur des couloirs séparés (gauche / droite), pressing haut, contre-attaque, défenseur qui ne dépasse jamais la ligne médiane.
- Milieu passé de Nova Pro à Nova Lite, trop lent pour la limite de 5 s.

---

## Structure

```
agentic-football-sample-agents/
├── lib/                        # Code partagé par les 5 agents
│   ├── agent_base.py           # Boucle de décision (règles → LLM → secours)
│   ├── fast_rules.py           # [nouveau] Règles instantanées
│   ├── state.py                # Résumé de l'état du jeu pour le LLM
│   ├── prompt_common.py        # [nouveau] Bloc de prompt commun
│   ├── team_config.py          # [nouveau] Mot de code + noms des joueurs
│   ├── fallback.py             # Plan de secours par poste
│   └── parsing.py              # Extraction du JSON renvoyé par le LLM
└── ai-team-strands-balanced/
    ├── ai-gk/   ai-def/   ai-mid/   ai-fwd1/   ai-fwd2/
    └── deploy_all.py           # Déploie les 5 agents sur AgentCore
```

---

## Lancer le projet

**Prérequis :** Python 3.10+, Node.js 20+, AWS CLI, [uv](https://docs.astral.sh/uv/), et un compte AWS avec accès aux modèles Nova (région `us-east-1`).

```bash
# Installation
npm install -g @aws/agentcore aws-cdk
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows (source .venv/bin/activate sur macOS/Linux)
pip install -e ./ai-team-strands-balanced/ai-gk

# Tests hors ligne (sans AWS)
cd ai-team-strands-balanced
python ai-gk/test_local.py           # idem pour ai-def, ai-mid, ai-fwd1, ai-fwd2

# Test avec le vrai modèle (identifiants AWS requis)
python ai-fwd1/test_local.py --llm

# Déploiement des 5 agents
python deploy_all.py
```

Les ARN des agents (console AWS → Bedrock → AgentCore → Runtime) s'enregistrent ensuite dans le Player Portal de l'événement.

---

## Ce que j'en retiens

- **Ne pas tout confier au LLM.** Dans un système temps réel, le code déterministe gère les cas évidents et le LLM ne traite que les cas ambigus. On y gagne en latence, en coût et en fiabilité.
- **La gestion d'état d'un agent compte.** Un historique qui s'accumule dégrade silencieusement les performances.
- **Toute entrée externe envoyée à un LLM est une surface d'attaque**, même dans un jeu.
- **Prévoir des plans de secours** : un agent en production ne doit jamais rester sans réponse.

## Pistes d'amélioration

- Vérifier dans CloudWatch le taux d'appels LLM réussis par rapport au plan de secours, puis ajuster la limite de temps et les modèles.
- Mémoriser les consignes du coach sur tout le match (AgentCore Memory).
- Utiliser AgentCore Evaluations (LLM-as-a-judge) pour noter la qualité des décisions.
- Adapter la tactique au style de l'adversaire détecté pendant le match.

---

*Réalisé par Danp — étudiant ingénieur ESIEA — workshop AWS Agentic Football Cup, octobre 2026.*
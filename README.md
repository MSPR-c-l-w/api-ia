# HealthAI Coach API (`api-ia`)

Microservice **Flask** + **MongoDB** (Motor) pour l'analyse nutritionnelle et les recommandations sportives IA.

Partie de l'[EPIC #79](https://github.com/MSPR-c-l-w/backend/issues/79).

---

## Table des matières

- [Prérequis](#prérequis)
- [Démarrage rapide — Docker Hub](#démarrage-rapide--docker-hub)
- [Démarrage local (développement)](#démarrage-local-développement)
- [Variables d'environnement](#variables-denvironnement)
- [Structure](#structure-clean-architecture)
- [Endpoints](#endpoints)
- [Tests](#tests)
- [CI/CD](#cicd)
- [Contribution](#contribution)

---

## Prérequis

- **Docker 24+** — c'est tout. MongoDB est **inclus dans l'image**, aucune installation supplémentaire n'est nécessaire.
- **Python 3.12+** uniquement si tu travailles sur le code source (développement local).

---

## Démarrage rapide — Docker Hub

> MongoDB est embarqué dans l'image. Un seul conteneur suffit pour faire tourner le service complet.

L'image est publiée automatiquement sur Docker Hub à chaque merge sur `main` :
`<DOCKERHUB_USERNAME>/api-ia`

Remplace `<DOCKERHUB_USERNAME>` par le nom d'utilisateur Docker Hub du projet.

---

### Option A — `docker run` (la plus simple)

```bash
docker run -d \
  --name healthai-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v healthai_data:/data/db \
  -e ENVIRONMENT=production \
  -e BACKEND_API_KEY="votre-clé-secrète" \
  <DOCKERHUB_USERNAME>/api-ia:latest
```

**Ce que fait chaque flag :**

| Flag | Rôle |
|---|---|
| `--restart unless-stopped` | Redémarre automatiquement après un crash ou reboot serveur |
| `-p 8000:8000` | Expose l'API sur le port 8000 de la machine hôte |
| `-v healthai_data:/data/db` | **Obligatoire** — persiste les données MongoDB entre les redémarrages |
| `-e ENVIRONMENT=production` | Désactive `/docs` (Swagger) en production |
| `-e BACKEND_API_KEY=...` | Clé secrète partagée avec le backend NestJS pour les routes `/recommendations/*` |

> **`BACKEND_API_KEY`** est la seule variable obligatoire. Elle doit correspondre à `WORKOUT_SERVICE_API_KEY` côté backend NestJS.

---

### Option B — Docker Compose

Crée un fichier `docker-compose.yml` sur ton serveur :

```yaml
services:
  api:
    image: <DOCKERHUB_USERNAME>/api-ia:latest
    ports:
      - "8000:8000"
    environment:
      ENVIRONMENT: production
      BACKEND_API_KEY: ${BACKEND_API_KEY}   # défini dans un fichier .env local
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped

volumes:
  mongo_data:
```

Puis crée un fichier `.env` à côté :

```env
BACKEND_API_KEY=votre-clé-secrète
```

Lance le service :

```bash
docker compose up -d
```

---

### Vérifier que le service est opérationnel

```bash
# Attendre ~15s le temps que MongoDB démarre (premier lancement)
curl http://localhost:8000/health
# → {"status": "ok", "timestamp": "..."}
```

> Au **premier démarrage**, MongoDB initialise ses fichiers de données — prévoir 10–20 secondes avant que le service réponde. Les démarrages suivants sont immédiats.

---

### Choisir le bon tag

| Tag | À utiliser quand… |
|---|---|
| `latest` | Tu veux toujours la dernière version stable |
| `v1.2.3` | Tu veux épingler une version précise (recommandé en production) |
| `v1.2` | Tu suis les patchs du minor `1.2` automatiquement |
| `sha-abc1234` | Tu veux une image traçable liée à un commit exact |

```bash
# Exemple avec version épinglée
docker run -d ... <DOCKERHUB_USERNAME>/api-ia:v1.0.0
```

---

## Démarrage local (développement)

### Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

### Installer les hooks git (équivalent Husky)

```bash
make setup-hooks
# ou manuellement :
pre-commit install --hook-type pre-commit
pre-commit install --hook-type pre-push
```

Les hooks activés :
- **pre-commit** : lint ruff, format ruff, vérifications YAML/JSON, protection de clés privées, blocage des commits directs sur `main`
- **pre-push** : exécution des tests unitaires

### Lancer l'API

```bash
# Via Docker Compose (avec MongoDB intégré)
make docker-run

# Ou directement
python run.py
```

---

## Variables d'environnement

| Variable | Défaut image | Obligatoire | Description |
|---|---|---|---|
| `BACKEND_API_KEY` | — | **Oui** | Clé partagée avec le backend NestJS — header `X-API-Key` sur `/recommendations/*` |
| `ENVIRONMENT` | `development` | Non | `development` \| `test` \| `production` — en `production`, `/docs` (Swagger) est désactivé |
| `PORT` | `8000` | Non | Port HTTP du serveur |
| `SECRET_KEY` | — | Non | Clé interne (réservée pour évolutions futures) |

Pour le développement local, copier `.env.example` vers `.env`.

---

## Structure (clean architecture)

```text
app/
  contexts/
    workout/          # Moteur sport — domain, application, infrastructure
    nutrition/        # Nutrition — use cases + stub vision
  shared/             # MongoDB, exceptions applicatives
  composition/        # Container (injection de dépendances)
  routers/            # Blueprints Flask
  main.py
tests/                # pytest — unit / integration / e2e
.github/workflows/    # CI/CD pipelines
docs/
```

---

## Endpoints

| Méthode | Chemin | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Santé du service |
| `POST` | `/api/nutrition/analyze` | — | Analyse nutrition |
| `POST` | `/recommendations/workout` | `X-API-Key` | Programme hebdomadaire |
| `POST` | `/recommendations/workout/{id}/feedback` | `X-API-Key` | Retour utilisateur |

**Swagger UI** (hors production) : http://localhost:8000/docs

---

## Tests

```bash
make test-unit          # Tests unitaires + rapport de couverture
make test-integration   # Tests d'intégration (nécessite MongoDB)
make test-e2e           # Tests end-to-end
make test               # Tout sauf e2e
```

Marqueurs pytest :

| Marker | Description |
|---|---|
| `@pytest.mark.unit` | Aucun service externe requis |
| `@pytest.mark.integration` | Nécessite MongoDB actif |
| `@pytest.mark.e2e` | Nécessite le stack complet |

---

## CI/CD

### Pipelines CI (`.github/workflows/`)

| Fichier | Déclencheur | Description |
|---|---|---|
| `ci-quality.yml` | Tout push / PR | Lint (ruff) + vérification du format |
| `ci-unit-tests.yml` | Tout push / PR | Tests unitaires + rapport coverage |
| `ci-integration-tests.yml` | Tout push / PR | Tests d'intégration (service MongoDB) |
| `ci-e2e.yml` | PR avec label **`e2e`** | Tests end-to-end (stack complet) |

### Pipelines CD

| Fichier | Déclencheur | Description |
|---|---|---|
| `cd-docker.yml` | Push sur `main` ou tag `v*.*.*` | Scan Trivy → build multi-platform → push Docker Hub |
| `cd-release.yml` | Push sur `main` | Semantic release (CHANGELOG + tag + GitHub Release) |

### Secrets GitHub requis

| Secret | Description |
|---|---|
| `DOCKERHUB_USERNAME` | Nom d'utilisateur Docker Hub |
| `DOCKERHUB_TOKEN` | Access token Docker Hub (lecture/écriture) |
| `GH_PAT` | Personal Access Token GitHub (optionnel — permet de déclencher d'autres workflows depuis la release) |
| `CODECOV_TOKEN` | Token Codecov (optionnel) |

### Conventional Commits (pour les releases)

Le versioning sémantique est basé sur les messages de commit :

| Préfixe | Bump |
|---|---|
| `feat:` | Minor (1.**X**.0) |
| `fix:`, `perf:` | Patch (1.0.**X**) |
| `BREAKING CHANGE` | Major (**X**.0.0) |

---

## Contribution

1. Forker / créer une branche depuis `main`
2. Installer les hooks : `make setup-hooks`
3. Commiter avec des messages [Conventional Commits](https://www.conventionalcommits.org/)
4. Ouvrir une PR — les pipelines CI se déclenchent automatiquement
5. Ajouter le label `e2e` sur la PR pour activer les tests end-to-end

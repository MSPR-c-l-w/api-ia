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

- **Docker 24+** (pour lancer depuis Docker Hub)
- **Python 3.12+** (pour le développement local)
- **MongoDB 7** (inclus dans le compose)

---

## Démarrage rapide — Docker Hub

L'image officielle est publiée sur Docker Hub à chaque merge sur `main`.

### 1. Créer le fichier `.env`

```bash
cp .env.example .env
# Éditer les valeurs selon votre environnement
```

Variables minimales requises :

| Variable | Valeur exemple | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://mongo:27017/healthai_coach` | URI MongoDB |
| `BACKEND_API_KEY` | `votre-clé-secrète` | Clé partagée avec le backend NestJS |
| `PORT` | `8000` | Port HTTP |

### 2. Lancer avec une seule commande

MongoDB est **intégré dans l'image** — aucun service externe requis.

```bash
docker run -d \
  --name healthai-api \
  -p 8000:8000 \
  -v healthai_data:/data/db \
  -e ENVIRONMENT=production \
  -e BACKEND_API_KEY="votre-clé-secrète" \
  <DOCKERHUB_USERNAME>/api-ia:latest
```

Le volume `-v healthai_data:/data/db` garantit la **persistance des données** MongoDB entre les redémarrages.

API disponible sur : **http://localhost:8000**

### 3. Lancer avec Docker Compose (optionnel)

Créer un `docker-compose.yml` :

```yaml
services:
  api:
    image: <DOCKERHUB_USERNAME>/api-ia:latest
    ports:
      - "${PORT:-8000}:8000"
    environment:
      ENVIRONMENT: production
      BACKEND_API_KEY: ${BACKEND_API_KEY}
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped

volumes:
  mongo_data:
```

```bash
docker compose up -d
```

### 4. Utiliser un MongoDB externe (optionnel)

Si tu as déjà un MongoDB, surcharge simplement `MONGODB_URI` :

```bash
docker run -d \
  --name healthai-api \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e MONGODB_URI="mongodb://mon-serveur:27017/healthai_coach" \
  -e BACKEND_API_KEY="votre-clé-secrète" \
  <DOCKERHUB_USERNAME>/api-ia:latest
```

### 4. Vérifier que le service est opérationnel

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

### Tags disponibles

| Tag | Description |
|---|---|
| `latest` | Dernier commit mergé sur `main` |
| `v1.2.3` | Version sémantique précise |
| `v1.2` | Dernière version du minor `1.2` |
| `sha-abc1234` | Image liée à un commit précis |

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

| Variable | Défaut | Description |
|---|---|---|
| `MONGODB_URI` | — | URI MongoDB |
| `BACKEND_API_KEY` | — | Clé partagée avec le backend NestJS — header `X-API-Key` |
| `PORT` | `8000` | Port HTTP |
| `ENVIRONMENT` | `development` | `development` \| `test` \| `production` — en `production`, `/docs` est désactivé |
| `SECRET_KEY` | — | Clé interne (réservée) |

Copier `.env.example` vers `.env`.

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

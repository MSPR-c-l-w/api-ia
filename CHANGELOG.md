# CHANGELOG

<!-- version list -->

## v0.3.0 (2026-06-24)

### Bug Fixes

- **scripts**: Retire les identifiants hardcodes des scripts d'entrainement
  ([`f3b64b3`](https://github.com/MSPR-c-l-w/api-ia/commit/f3b64b3b139c97d2edd9da85f69967fefce85875))

- **workout**: Entraine le modele sur le vrai catalogue backend + vraies donnees
  ([`96eb17f`](https://github.com/MSPR-c-l-w/api-ia/commit/96eb17fa8a3bf1000c347ca8ebf48eaff78bf3ee))

- **workout**: Valide empiriquement le seuil de satisfaction du label
  ([`99232e0`](https://github.com/MSPR-c-l-w/api-ia/commit/99232e086801f498200c49afdf01d0625ad124c4))

### Code Style

- Ruff format get_workout_program + recommendations router
  ([`2eee183`](https://github.com/MSPR-c-l-w/api-ia/commit/2eee183173f803b39eab351d72648164f523292f))

### Documentation

- Ajoute l'ergonomie des fonctionnalites IA cote social-media
  ([`3d4f9e9`](https://github.com/MSPR-c-l-w/api-ia/commit/3d4f9e9f4e6ffe366cdc37137c174dd42e403dfa))

- Ajoute le role du backend (separation architecturale + integration)
  ([`2648c7e`](https://github.com/MSPR-c-l-w/api-ia/commit/2648c7e263c9c8a2ff20a4ab76cd7c3e1bfc0f02))

- Doc unique algorithmes/APIs/ergonomie/accessibilite/metriques
  ([`a1a6af8`](https://github.com/MSPR-c-l-w/api-ia/commit/a1a6af89cee93c99598479c059c78ff4fb4141e3))

- Documente ENABLE_RETRAINING_SCHEDULER dans .env.example
  ([`98daf52`](https://github.com/MSPR-c-l-w/api-ia/commit/98daf524a3c2720224b79adb2a87927a18cdd30e))

- Enrichit le livrable avec le detail complet d'ai-engines-technical-doc.md
  ([`36be672`](https://github.com/MSPR-c-l-w/api-ia/commit/36be67272469929869ec9df3e49d0e7c56fcdedf))

- Flux analyse photo + mise a jour meal-plan (branche Flo)
  ([`dc2edb1`](https://github.com/MSPR-c-l-w/api-ia/commit/dc2edb1f4ec831228db9b4b88de3c0b2ba1352af))

- Justifie le choix d'architecture ML (boosting vs alternatives)
  ([`2bb6238`](https://github.com/MSPR-c-l-w/api-ia/commit/2bb62385d3ce2083df98ca5470abae9c3004fb7a))

- Justifie les choix d'API externes (vision, LLM) et corrige une affirmation obsolete
  ([`cb22bf7`](https://github.com/MSPR-c-l-w/api-ia/commit/cb22bf7ce00540880df886e07a1a1d945773fb6c))

- Nomme explicitement la methodologie d'entrainement
  ([`64d9eb0`](https://github.com/MSPR-c-l-w/api-ia/commit/64d9eb076957c349091e45c68d12e107d9bb7d2a))

- Precise la piste de reentrainement periodique
  ([`234197f`](https://github.com/MSPR-c-l-w/api-ia/commit/234197f31c15ba5cc2c41c3b607be176322f6a85))

- Retire la section Synthese du livrable algos/APIs/ergonomie
  ([`f890aec`](https://github.com/MSPR-c-l-w/api-ia/commit/f890aeccc79c474382bb5e7e388ad1a742a8fe87))

- Simplifie la presentation de l'ergonomie IA (sans statut pending)
  ([`fd9d866`](https://github.com/MSPR-c-l-w/api-ia/commit/fd9d8662a65bd2925f6d2bc0d7341d6bd566d807))

### Features

- **ml**: Reentrainement periodique automatique des modeles
  ([`0875470`](https://github.com/MSPR-c-l-w/api-ia/commit/087547013cf8d1594197dba51f0d9e6b0b040258))

- **nutrition**: Ajoute la categorie comme feature du MealTypeModel
  ([`5a8dcea`](https://github.com/MSPR-c-l-w/api-ia/commit/5a8dcea1239d98071a73626f7cd4e1663a82a8bb))

- **nutrition**: Modele de classification du type de repas (donnees reelles)
  ([`2da5030`](https://github.com/MSPR-c-l-w/api-ia/commit/2da503061616b90e2b1f4d22b062e29dda18f7b6))

- **nutrition**: Support du budget dans MealPlanRequest
  ([`d1f92cb`](https://github.com/MSPR-c-l-w/api-ia/commit/d1f92cbe837a49d7db761b81ce3aaeef9dc346be))

- **workout**: Endpoint GET /recommendations/workout/:id + doc complete api-ia
  ([`19ed806`](https://github.com/MSPR-c-l-w/api-ia/commit/19ed8065043b192c164534c26df047ffa488e312))

- **workout**: Modele de scoring appris (GradientBoostingClassifier)
  ([`59b58d9`](https://github.com/MSPR-c-l-w/api-ia/commit/59b58d96210db970df11c548d00e80525a504eff))


## v0.2.0 (2026-06-20)

### Bug Fixes

- **nutrition**: Robustesse OllamaVisionProvider (téléchargement image + plancher de confiance)
  ([#26](https://github.com/MSPR-c-l-w/api-ia/pull/26),
  [`076f490`](https://github.com/MSPR-c-l-w/api-ia/commit/076f49002ceb6b3cb1afdefe7e6d5cb49e30c35a))

- **nutrition**: Timeout court dédié au téléchargement d'image (OllamaVisionProvider)
  ([#26](https://github.com/MSPR-c-l-w/api-ia/pull/26),
  [`076f490`](https://github.com/MSPR-c-l-w/api-ia/commit/076f49002ceb6b3cb1afdefe7e6d5cb49e30c35a))

### Chores

- Add .coverage data file ([#25](https://github.com/MSPR-c-l-w/api-ia/pull/25),
  [`68e1233`](https://github.com/MSPR-c-l-w/api-ia/commit/68e1233e7075ba0826f82a18f621d5af6d0f85d3))

### Features

- **nutrition**: Alias FR/EN + priorité des tables backend, keep_alive Ollama
  ([#26](https://github.com/MSPR-c-l-w/api-ia/pull/26),
  [`076f490`](https://github.com/MSPR-c-l-w/api-ia/commit/076f49002ceb6b3cb1afdefe7e6d5cb49e30c35a))

- **nutrition**: Détection des aliments d'un plat via catalogue MongoDB
  ([#26](https://github.com/MSPR-c-l-w/api-ia/pull/26),
  [`076f490`](https://github.com/MSPR-c-l-w/api-ia/commit/076f49002ceb6b3cb1afdefe7e6d5cb49e30c35a))

- **nutrition**: Détection vision locale gratuite via Ollama
  ([#26](https://github.com/MSPR-c-l-w/api-ia/pull/26),
  [`076f490`](https://github.com/MSPR-c-l-w/api-ia/commit/076f49002ceb6b3cb1afdefe7e6d5cb49e30c35a))

- **nutrition**: Résout les aliments détectés vers les noms exacts de la base NoSQL
  ([#26](https://github.com/MSPR-c-l-w/api-ia/pull/26),
  [`076f490`](https://github.com/MSPR-c-l-w/api-ia/commit/076f49002ceb6b3cb1afdefe7e6d5cb49e30c35a))

### Testing

- Add unit and integration tests for nutrition adapters, feedback use case and Mongo repos
  ([#25](https://github.com/MSPR-c-l-w/api-ia/pull/25),
  [`68e1233`](https://github.com/MSPR-c-l-w/api-ia/commit/68e1233e7075ba0826f82a18f621d5af6d0f85d3))

- Reach 100% coverage and add end-to-end workflow tests
  ([#25](https://github.com/MSPR-c-l-w/api-ia/pull/25),
  [`68e1233`](https://github.com/MSPR-c-l-w/api-ia/commit/68e1233e7075ba0826f82a18f621d5af6d0f85d3))

- Suite de tests complète (unitaires, intégration, e2e) — couverture 100%
  ([#25](https://github.com/MSPR-c-l-w/api-ia/pull/25),
  [`68e1233`](https://github.com/MSPR-c-l-w/api-ia/commit/68e1233e7075ba0826f82a18f621d5af6d0f85d3))


## v0.1.7 (2026-06-10)

### Bug Fixes

- Nom des exercices dans la réponse workout + variables env backend
  ([#24](https://github.com/MSPR-c-l-w/api-ia/pull/24),
  [`8f014a1`](https://github.com/MSPR-c-l-w/api-ia/commit/8f014a1899abb00472413add9f4e9857b98f8b6a))

- Propagate exercise name in workout response + pass backend env vars to container
  ([#24](https://github.com/MSPR-c-l-w/api-ia/pull/24),
  [`8f014a1`](https://github.com/MSPR-c-l-w/api-ia/commit/8f014a1899abb00472413add9f4e9857b98f8b6a))

- **lint**: Format weekly_planner.py pour ruff ([#24](https://github.com/MSPR-c-l-w/api-ia/pull/24),
  [`8f014a1`](https://github.com/MSPR-c-l-w/api-ia/commit/8f014a1899abb00472413add9f4e9857b98f8b6a))


## v0.1.6 (2026-06-09)

### Bug Fixes

- Ruff lint and format
  ([`a0d2df6`](https://github.com/MSPR-c-l-w/api-ia/commit/a0d2df683cd4b14de51f4c149b7d44b3774fc255))

### Code Style

- Ruff format exercises_catalog
  ([`a0d2df6`](https://github.com/MSPR-c-l-w/api-ia/commit/a0d2df683cd4b14de51f4c149b7d44b3774fc255))

### Continuous Integration

- Add Dependabot for pip, GitHub Actions and Docker weekly updates
  ([`c693785`](https://github.com/MSPR-c-l-w/api-ia/commit/c693785d6cfffb7fe79529211d4cfd2036b1be6c))

- Retire codecov, conserve le rapport coverage en artifact
  ([`a0d2df6`](https://github.com/MSPR-c-l-w/api-ia/commit/a0d2df683cd4b14de51f4c149b7d44b3774fc255))


## v0.1.5 (2026-06-01)

### Bug Fixes

- **cd**: Build linux/amd64 only — MongoDB 7 has no arm64 Debian packages
  ([`3e2ad01`](https://github.com/MSPR-c-l-w/api-ia/commit/3e2ad01061c247bc4e283ca18d1d38617d9b55fb))


## v0.1.4 (2026-06-01)

### Bug Fixes

- **docker**: Apt-get upgrade to patch libgnutls30 CVE-2026-33845 / CVE-2026-42010
  ([`e7762cc`](https://github.com/MSPR-c-l-w/api-ia/commit/e7762cc8b8785aff8037c111fed1be112b666131))


## v0.1.3 (2026-06-01)

### Bug Fixes

- **cd**: Upgrade codeql-action to v4, mark sarif upload non-blocking
  ([`bf07e12`](https://github.com/MSPR-c-l-w/api-ia/commit/bf07e12d02254b2d380fae2c846bb8a3eae2f2da))


## v0.1.2 (2026-06-01)

### Bug Fixes

- **docker**: Pin base image to python:3.12-slim-bookworm
  ([`a68d58c`](https://github.com/MSPR-c-l-w/api-ia/commit/a68d58c6437aba51729035eebcb267c5ae80c426))


## v0.1.1 (2026-06-01)

### Bug Fixes

- **cd**: Replace trivy-action@0.31.0 with @master (version does not exist)
  ([`6902847`](https://github.com/MSPR-c-l-w/api-ia/commit/6902847ecffa6ce93ba8448bf39843ba9e594f6c))


## v0.1.0 (2026-06-01)

- Initial Release

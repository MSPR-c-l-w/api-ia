# Choix des algorithmes/APIs, ergonomie, accessibilité et métriques

> Document de synthèse répondant directement au livrable du cahier des charges
> MSPR TPRE502 : « Documentation détaillée décrivant le choix des algorithmes
> et APIs utilisés, les principes d'ergonomie appliqués et les normes
> d'accessibilité mises en œuvre. Les métriques de performance des modèles IA
> devront être fournies (ex. précision, rappel, F1-score). »
>
> Ce livrable est transversal à trois dépôts : `api-ia` (algorithmes, APIs IA,
> métriques), `backend` (choix d'architecture IA) et `social-media`
> (ergonomie, accessibilité de l'application mobile). Ce document regroupe
> l'intégralité des trois volets en un seul endroit, sans renvoi externe.

---

## 1. Choix des algorithmes (`api-ia`)

**Algorithme retenu : `GradientBoostingClassifier` (scikit-learn)**, pour les
deux modèles entraînés du projet (`ExerciseScoringModel` côté sport,
`MealTypeModel` côté nutrition).

| Alternative écartée    | Raison                                                                                                                                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Réseau de neurones      | Nécessite un volume de données bien plus important pour généraliser (quelques milliers d'échantillons ici, pas des dizaines de milliers) ; excelle sur données brutes non structurées, pas sur des features tabulaires déjà propres (7 à 23 colonnes) ; coût d'infrastructure disproportionné (GPU) pour un service conteneurisé à côté d'une API NestJS. |
| Arbre de décision seul  | Forte variance — un arbre profond unique épouse le bruit des labels (notamment les notes subjectives du sport) et généralise mal. Le boosting combine ~100 arbres peu profonds (`max_depth=3`) appris séquentiellement, chacun corrigeant les erreurs du précédent. |
| Forêt aléatoire         | Ensemble d'arbres également, mais appris en parallèle (bagging) sans correction séquentielle des erreurs résiduelles. Le boosting converge mieux sur peu de features et expose un hyperparamètre `learning_rate` explicite, facile à justifier et à ajuster — pas d'équivalent aussi direct côté forêt aléatoire. |

**Type d'apprentissage et procédure** (identique pour les deux modèles) :
supervisé (label connu à l'avance) · entraînement par lot (`model.fit()` une
seule fois sur tout le train set, volume tenant en mémoire) · validation
croisée stratifiée 5-fold pour le balayage du `learning_rate` · bootstrap pour
les données synthétiques complémentaires côté sport.

**Note méthodologique sur le seuil de binarisation du label (modèle sport)** :
une première analyse sur un petit échantillon (120 feedbacks, notes {2,3,4}
seulement) avait suggéré d'abaisser le seuil de satisfaction de 4 à 3 (sur 5)
pour rééquilibrer les classes. Sur un échantillon plus large (521 feedbacks,
distribution {2:30, 3:137, 4:211, 5:143}), ce seuil à 3 s'est révélé être une
**sur-correction** : 94 % des échantillons devenaient « satisfaisant », rendant
la tâche triviale (F1 artificiellement gonflé à 0.96 en prédisant presque
toujours positif). Le seuil à 4 a été conservé (~61 % positif sur le test
set), un déséquilibre plus sain. Leçon retenue : le seuil de binarisation d'un
label continu est un choix de modélisation, pas un paramètre que
l'entraînement optimise lui-même — il doit être validé empiriquement sur un
échantillon représentatif avant d'être figé.

**Opérationalisation — réentraînement périodique** : un planificateur
hebdomadaire (`app/shared/infrastructure/retraining_scheduler.py`, basé sur
`APScheduler`) relance l'entraînement des deux modèles chaque dimanche. Un
garde-fou (`model_deployment_guard.py`) compare la métrique du nouveau modèle
(F1 / F1 macro) à celle du modèle actuellement déployé avant de remplacer le
fichier `.joblib` — un réentraînement qui produirait un modèle moins bon que
l'actuel ne l'écrase jamais. Désactivé par défaut
(`ENABLE_RETRAINING_SCHEDULER=false`), à activer explicitement en production.

---

## 2. Choix des APIs utilisées (`api-ia`)

| Fonction              | Ordre de priorité                                  | Justification                                                                                                                                                              |
| ---------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vision par ordinateur   | 1. **Ollama** (local, modèle `llava`) → 2. **Google Vision API** → 3. stub interne | Ollama gratuit, exécution locale, aucune donnée image envoyée à un tiers, pas de quota. Google Vision en repli si pas de serveur local disponible (quota gratuit limité, payant au-delà). Stub en dernier recours pour ne jamais faire échouer une requête. |
| Génération de texte (LLM) | 1. **Ollama** → 2. suggestions statiques FR        | Même logique : exécution locale gratuite en priorité, repli sans dépendance dure à une API tierce payante si aucun endpoint n'est configuré.                              |

**Robustesse de l'intégration externe** : cache mémoire à TTL
(`AiCacheService`, clé = hash SHA256 du contenu de la requête) pour éviter les
appels redondants ; chaîne de fallback en cascade décrite ci-dessus ;
dégradation contrôlée — aucune erreur 5xx renvoyée au client si une API
externe est indisponible.

---

## 3. Choix d'architecture côté `backend`

Le cahier des charges autorise explicitement deux options : « *Cette API IA
peut être intégrée au back-end développé lors de la MSPR TPRE501 ou bien
développée séparément* ». Le projet a choisi de la **développer séparément**
(`api-ia`, micro-service Python/Flask indépendant) plutôt que de l'intégrer au
backend NestJS.

**Justification** : l'écosystème de machine learning (scikit-learn, pandas) et
les ressources qui en découlent (entraînement, ré-entraînement périodique,
modèles `.joblib`) sont nativement Python, pas TypeScript/Node ; séparer
permet une **scalabilité indépendante** de l'API métier et du moteur IA
(charge CPU différente, cycle de déploiement différent), et une documentation
OpenAPI dédiée au micro-service IA.

**Intégration backend → `api-ia`** (`WorkoutMicroserviceClient`,
`AiNutritionService`) :

| Aspect                  | Implémentation                                                                                   |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| Authentification          | Header `X-API-Key` (clé partagée, `WORKOUT_SERVICE_API_KEY`)                                          |
| Timeout                   | 10 secondes par appel (`REQUEST_TIMEOUT_MS`) — évite qu'une requête HTTP bloque indéfiniment           |
| Gestion d'indisponibilité | Configuration manquante ou échec réseau → `WorkoutMicroserviceUnavailableException` (HTTP 503 explicite), jamais de crash silencieux ni de réponse vide non qualifiée |
| Journalisation             | Échec loggé (`Logger.warn`) avec le code d'erreur Axios pour le diagnostic                              |

Le backend ne porte donc ni algorithme ni modèle IA propre (c'est le rôle
d'`api-ia`) ; sa contribution à ce livrable est le **choix architectural de
séparation** et la **robustesse de l'appel** au micro-service.

---

## 4. Métriques de performance des modèles IA (`api-ia`)

### 4.1 Moteur Sport — `ExerciseScoringModel`

Entraîné sur 8877 échantillons (7077 réels issus de vrais feedbacks
utilisateurs via le catalogue backend `Exercise`, 1800 synthétiques en
complément) ; évalué sur un test set hold-out de 1776 échantillons jamais vus
à l'entraînement. Label binaire : `satisfait = 1` si note réelle/simulée ≥ 4/5.

**Balayage du `learning_rate`** (validation croisée stratifiée 5-fold, métrique F1) :

| learning_rate | F1 moyen (CV) | Écart-type |
| --- | --- | --- |
| 0.01 | 0.7949 | 0.0070 |
| **0.05 (retenu)** | **0.7962** | 0.0071 |
| 0.1 | 0.7925 | 0.0135 |
| 0.2 | 0.7873 | 0.0140 |
| 0.3 | 0.7919 | 0.0158 |

**Performance sur le test set (hold-out, 1776 échantillons) :**

| Métrique | Valeur |
| --- | --- |
| Exactitude (accuracy) | 0.7264 |
| **Précision** | **0.7290** |
| **Rappel (recall)** | **0.8760** |
| **F1-score** | **0.7958** |
| R² (probabilité prédite vs note normalisée) | 0.2534 |
| RMSE | 0.4217 |
| Taux de faux positifs (FPR) | 0.5065 |
| Taux de faux négatifs (FNR) | 0.1240 |

**Matrice de confusion :**

| | Prédit négatif | Prédit positif |
| --- | --- | --- |
| **Réel négatif** | 343 (TN) | 352 (FP) |
| **Réel positif** | 134 (FN) | 947 (TP) |

**Importance des features apprises :**

| Feature | Importance |
| --- | --- |
| objective_match | 0.6199 |
| equipment_available | 0.1749 |
| level_diff | 0.1094 |
| n_contraindications | 0.0610 |
| limitation_conflict | 0.0154 |
| n_equipment_required | 0.0105 |
| preference_overlap_ratio | 0.0090 |

### 4.2 Moteur Nutrition — `MealTypeModel`

Entraîné sur 595 échantillons 100 % réels (catalogue `Nutrition`, 601+
aliments Kaggle validés par revue humaine) ; évalué sur un test set hold-out
de 119 échantillons. Label : `meal_type_name` (colonne réelle du dataset, 4 classes).

**Distribution des classes (595 échantillons) :**

| Classe | Échantillons |
| --- | --- |
| Petit-déjeuner | 82 |
| Collation | 166 |
| Dîner | 211 |
| Déjeuner | 136 |

**Balayage du `learning_rate`** (validation croisée stratifiée 5-fold, métrique F1 macro) :

| learning_rate | F1 macro moyen (CV) | Écart-type |
| --- | --- | --- |
| 0.01 | 0.3807 | 0.0319 |
| 0.05 | 0.4650 | 0.0331 |
| **0.1 (retenu)** | **0.4724** | 0.0267 |
| 0.2 | 0.4618 | 0.0504 |
| 0.3 | 0.4477 | 0.0395 |

**Performance sur le test set (hold-out, 119 échantillons) :**

| Métrique | Valeur |
| --- | --- |
| Exactitude (accuracy) | 0.5714 |
| **Précision (macro)** | **0.5222** |
| **Rappel (macro)** | **0.5113** |
| **F1-score (macro)** | **0.5068** |
| Baseline classe majoritaire (`Dîner`) | 0.3550 |

Le modèle bat la baseline naïve de **+21.6 points**, et le hasard pur (25 % sur
4 classes) de +32 points.

**Matrice de confusion :**

| Réel \ Prédit | Petit-déjeuner | Déjeuner | Dîner | Collation |
| --- | --- | --- | --- | --- |
| **Petit-déjeuner** | 3 | 1 | 2 | 11 |
| **Déjeuner** | 2 | 13 | 12 | 0 |
| **Dîner** | 2 | 7 | 29 | 4 |
| **Collation** | 1 | 7 | 2 | 23 |

**Importance des features apprises (toutes, 64 au total — macros + one-hot catégorie) :**

| Feature | Importance | Feature | Importance |
| --- | --- | --- | --- |
| sugar_g | 0.1915 | category_Légumineuse | 0.0023 |
| sodium_mg | 0.1398 | category_Légume/Condiment | 0.0022 |
| calories | 0.0791 | category_Farine/Céréales | 0.0021 |
| protein_g | 0.0751 | category_Protéines/Fruits de mer | 0.0020 |
| carbs_g | 0.0725 | category_Céréales/Dessert | 0.0019 |
| category_Repas/Transformé | 0.0508 | category_Légumes/Transformés | 0.0015 |
| cholesterol_mg | 0.0496 | category_Protéiné/Végétarien | 0.0010 |
| fat_g | 0.0484 | category_Repas/Soupe | 0.0010 |
| fiber_g | 0.0390 | category_Viande | 0.0007 |
| category_Snack/Transformé | 0.0358 | category_Légumes | 0.0007 |
| category_Légume | 0.0307 | category_Repas/Pâtes | 0.0006 |
| category_Boissons | 0.0229 | category_Repas/Riz | 0.0006 |
| category_Fruits | 0.0166 | category_Repas | 0.0004 |
| category_Desserts | 0.0157 | category_Protéine | 0.0002 |
| category_Condiments | 0.0135 | category_Repas/Poisson | 0.0001 |
| category_Noix | 0.0105 | category_Oeufs | 0.0000 |
| category_Produits laitiers | 0.0079 | category_1 tasse) * | 0.0000 |
| category_Repas/Protéines | 0.0077 | category_4oz) * | 0.0000 |
| category_Repas/Végétarien | 0.0073 | category_Boisson/Repas | 0.0000 |
| category_Collation | 0.0064 | category_Collation/Apéritif | 0.0000 |
| category_Céréales | 0.0062 | category_Collation/Dessert | 0.0000 |
| category_Protéine/Viande | 0.0056 | category_Poisson | 0.0000 |
| category_Supplément/Traité | 0.0055 | category_Produits laitiers/Desserts | 0.0000 |
| category_Céréales/transformées | 0.0054 | category_Protéines/Laitiers | 0.0000 |
| category_Farine/Légumineuse | 0.0053 | category_Repas/Viande | 0.0000 |
| category_Repas/Fruits | 0.0037 | category_crus) * | 0.0000 |
| category_Boissons/produits laitiers-Alt | 0.0035 | category_dans le bouillon) * | 0.0000 |
| category_Féculents | 0.0034 | category_jaune) * | 0.0000 |
| category_Condiment/Laiterie | 0.0034 | category_autre | 0.0000 |
| category_Supplément | 0.0033 | | |
| category_Protéines/Transformées | 0.0033 | | |
| category_Repas/Légumes | 0.0030 | | |
| category_Boissons/produits laitiers | 0.0029 | | |
| category_Condiment/Transformé | 0.0027 | | |
| category_Protéine/Poisson | 0.0025 | | |
| category_Repas/Fruits de mer | 0.0024 | | |

\* Catégories à importance ≈0 issues de fragments de parenthèses mal parsés du
CSV Kaggle d'origine (ex. `"1 tasse)"`, `"4oz)"`) — anomalie de qualité des
données amont (ETL), sans impact sur le modèle.

### 4.3 Métriques complémentaires du socle déterministe (règles pondérées)

Les deux moteurs combinent les modèles entraînés ci-dessus avec un socle à
règles pondérées (filtre dur de compatibilité, calcul TDEE/macros). Ce socle
est lui aussi mesuré, avec MSE/RMSE/R² (définitions : RSS = `Σ(y_true−y_pred)²`,
TSS = `Σ(y_true−ȳ_true)²`, MSE = `RSS/n`, RMSE = `√MSE`, R² = `1 − RSS/TSS`) :

| Moteur / axe | y_true vs y_pred | MSE | RMSE | R² | Interprétation |
| --- | --- | --- | --- | --- | --- |
| Workout (règles pondérées) | note utilisateur normalisée vs score `score_exercise()` | 0.20 | 0.45 | −2.65 | R² négatif attendu : le moteur optimise l'adéquation profil↔exercice, pas la note utilisateur — il n'a jamais été entraîné pour la prédire (rôle repris par `ExerciseScoringModel`, §4.1). |
| Nutrition — lookup macros (50 aliments) | macros DB Kaggle vs macros estimées | ≈0 | 0.02–0.20 | 1.00 | Lecture directe depuis la table `Nutrition` (pas d'estimation) ; R²=1.0 normal, utile seulement si remplacé un jour par un modèle de prédiction. |
| Nutrition — équilibre repas simulés (20 repas, 1-3 aliments) | cible (1/3 du target jour) vs macros réelles | — | 455 kcal / 26.7 g prot. / 58 g gluc. | −14.2 / −13.8 / −10.1 | Déficits dus à des repas simulés à 1-3 aliments (test isolé de la formule) ; avec le `MealComposerService` réel (3-5 composants + scaling), la cible est atteinte à ~90-95 %. |

Indicateurs de précision opérationnelle mesurés en routine : score moyen d'un
exercice compatible ~0.70-0.85 ; score moyen du `MealComposerService` ~0.56-0.60
sur [0,1] ; précision calorique du plan repas ±5-10 % de la cible après
scaling des portions ; 101/101 tests automatisés passants sur ces deux moteurs.

---

## 5. Principes d'ergonomie appliqués (`social-media`)

| Principe                          | Implémentation                                                                                                       |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Navigation simple et prévisible      | 4 onglets principaux (Accueil, Publier, Profil, Réglages), libellés textuels + icônes combinés                          |
| Langue et clarté des messages       | Interface entièrement en français ; messages d'erreur contextualisés (connexion échouée, export bloqué, suppression de compte) |
| Prévention des erreurs destructrices | Modales de confirmation avant toute action irréversible (déconnexion, suppression de compte avec re-saisie du mot de passe) |
| Confort visuel personnalisable       | Mode sombre (toggle dans Réglages → Apparence, persisté en local)                                                       |
| Continuité de service                | Mode hors ligne avec bannière explicite (`OfflineBanner`) et cache du fil d'actualité                                   |
| Autonomie de l'utilisateur           | FAQ intégrée (5 questions), section Aide & Support, guide utilisateur externe (`DOCUMENTATION_UTILISATION.md`, ~470 lignes) |
| Onboarding sans friction             | Inscription/connexion self-service, pas de configuration préalable requise                                              |

**Ergonomie spécifique aux fonctionnalités IA** :

| Fonctionnalité IA                                  | Implémentation                                                                                                                                                          |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Recommandations IA (plan repas, programme sportif)     | `AiRecommendationsScreen.tsx` : écran dédié, actions Générer/Régénérer explicites, états de chargement visibles, résultats affichés directement dans l'app.              |
| Reconnaissance photo des aliments                      | Consomme `POST /ai/nutrition/analyze-photo` (contrat déjà prêt côté `api-ia`, §2) ; même principe d'ergonomie que ci-dessus : action explicite, retour immédiat dans l'app. |
| Préférences IA utilisateur (allergies, régime, objectif, limitations physiques) | Écran de réglages consommant `PUT /users/me/ai-preferences` (endpoint déjà disponible côté backend), intégré aux sections existantes des Réglages.                      |

Ergonomie cohérente sur l'ensemble des trois : action explicite, retour visuel immédiat, résultat consultable dans l'app sans étape intermédiaire — alignée sur les principes déjà appliqués ci-dessus (clarté des messages, continuité de service, autonomie de l'utilisateur).

---

## 6. Normes d'accessibilité mises en œuvre (`social-media`)

Conformité visée : **WCAG / RGAA niveau AA**. Implémentation via la **React
Native Accessibility API** sur les composants à fort impact utilisateur :

| Mécanisme                          | Composants concernés                                                                          |
| ------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `accessibilityRole`                    | Boutons, onglets, switches, alertes (`OfflineBanner`, `Toast`, `ErrorScreen`)                       |
| `accessibilityLabel`                   | Retour arrière, bouton like, avatar profil, badges, FAB « Créer une publication »                  |
| `accessibilityState`                   | Onglets sélectionnés, switches cochés/désactivés, bouton export désactivé pendant le cooldown        |
| `accessibilityRole="alert"`            | Bannière hors ligne, toasts, écran d'erreur — annonce immédiate aux lecteurs d'écran (VoiceOver/TalkBack) |
| `hitSlop`                               | Zone tactile élargie sur les boutons d'en-tête et d'engagement                                       |
| `accessibilityIgnoresInvertColors`      | Galerie médias et badges — préserve le rendu en mode couleurs inversées                              |

**Multi-plateforme** (Expo/React Native) : iOS, Android et Web depuis un seul
code source — élimine la barrière d'équipement pour l'accès à l'application.

**Limite déclarée honnêtement** : implémentation ciblée sur les composants à
fort impact, pas d'audit WCAG formalisé, pas de réglages d'accessibilité
dédiés (taille de police, contraste forcé) ni de tests automatisés
d'accessibilité (axe-core) dans le dépôt à ce stade.

---

## Synthèse

| Volet du livrable           | Dépôt          | Statut                                                              |
| ----------------------------- | -------------- | ---------------------------------------------------------------------- |
| Choix des algorithmes          | `api-ia`        | ✅ Documenté et justifié (§1)                                          |
| Choix des APIs                 | `api-ia`        | ✅ Documenté et justifié (§2)                                          |
| Choix d'architecture IA         | `backend`       | ✅ Séparation justifiée + robustesse de l'appel documentée (§3)        |
| Métriques (précision/rappel/F1, R²/RMSE/MSE) | `api-ia` | ✅ Fournies pour les deux modèles entraînés et le socle déterministe (§4) |
| Principes d'ergonomie           | `social-media`  | ✅ Documentés, avec dispositifs concrets (§5)                          |
| Normes d'accessibilité          | `social-media`  | ✅ Documentées, conformité partielle déclarée honnêtement (§6)         |

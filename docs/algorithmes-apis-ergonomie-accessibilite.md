# Choix des algorithmes/APIs, ergonomie, accessibilité et métriques

> Document de synthèse répondant directement au livrable du cahier des charges
> MSPR TPRE502 : « Documentation détaillée décrivant le choix des algorithmes
> et APIs utilisés, les principes d'ergonomie appliqués et les normes
> d'accessibilité mises en œuvre. Les métriques de performance des modèles IA
> devront être fournies (ex. précision, rappel, F1-score). »
>
> Ce livrable est transversal à deux dépôts : `api-ia` (algorithmes, APIs IA,
> métriques) et `social-media` (ergonomie, accessibilité de l'application
> mobile). Ce document regroupe les deux volets en un seul endroit ; les
> détails complets restent dans les documents sources cités à chaque section.

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

Justification complète et détaillée : [`ai-engines-technical-doc.md` §1.1, §3.5, §4.4](ai-engines-technical-doc.md).

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

Détail complet : [`ai-engines-technical-doc.md` §1.1](ai-engines-technical-doc.md).

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
à l'entraînement.

| Métrique               | Valeur |
| ----------------------- | ------ |
| Exactitude (accuracy)    | 0.726  |
| **Précision**            | **0.729** |
| **Rappel**               | **0.876** |
| **F1-score**             | **0.796** |
| Taux de faux positifs    | 0.507  |
| Taux de faux négatifs    | 0.124  |

### 4.2 Moteur Nutrition — `MealTypeModel`

Entraîné sur 595 échantillons 100 % réels (catalogue `Nutrition`, 601+
aliments Kaggle validés par revue humaine) ; évalué sur un test set hold-out
de 119 échantillons.

| Métrique                          | Valeur |
| ----------------------------------- | ------ |
| Exactitude (accuracy)                | 0.571  |
| **Précision (macro)**                | **0.522** |
| **Rappel (macro)**                   | **0.511** |
| **F1-score (macro)**                 | **0.507** |
| Baseline classe majoritaire (`Dîner`) | 0.355  |

Le modèle bat la baseline naïve de **+21.6 points** et le hasard pur (25 % sur
4 classes) de +32 points.

Détail complet (matrices de confusion, importance des features, méthodologie
de validation du seuil de satisfaction côté sport) :
[`ai-engines-technical-doc.md` §3.5, §4.4, §6](ai-engines-technical-doc.md).

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

Détail complet : `social-media/docs/conduite_du_changement_HealthAI` (§3.3 à
§4.2) — document dédié au livrable « conduite du changement ».

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

Détail complet : `social-media/docs/conduite_du_changement_HealthAI` (§3.1,
§3.2, §6 — limites et perspectives).

---

## Synthèse

| Volet du livrable           | Dépôt          | Statut                                                              |
| ----------------------------- | -------------- | ---------------------------------------------------------------------- |
| Choix des algorithmes          | `api-ia`        | ✅ Documenté et justifié (§1)                                          |
| Choix des APIs                 | `api-ia`        | ✅ Documenté et justifié (§2)                                          |
| Choix d'architecture IA         | `backend`       | ✅ Séparation justifiée + robustesse de l'appel documentée (§3)        |
| Métriques (précision/rappel/F1) | `api-ia`        | ✅ Fournies pour les deux modèles entraînés (§4)                       |
| Principes d'ergonomie           | `social-media`  | ✅ Documentés, avec dispositifs concrets (§5)                          |
| Normes d'accessibilité          | `social-media`  | ✅ Documentées, conformité partielle déclarée honnêtement (§6)         |

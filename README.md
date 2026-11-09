# Sparkle
Sparkle is presenting to you ! A friendly desktop pet who you can talk with and interact with.

## Chatbot cloud gratuit

Sparkle utilise Groq avec le modèle `openai/gpt-oss-120b`, un modèle de
raisonnement performant et rapide. L'offre **Free** de Groq ne demande pas de
carte bancaire. Aucun abonnement payant n'est nécessaire pour cette configuration.

Les [limites gratuites officielles](https://console.groq.com/docs/rate-limits)
annoncées au 9 novembre 2026 sont de 30 requêtes/minute, 1 000 requêtes/jour,
8 000 tokens/minute et 200 000 tokens/jour pour ce modèle. Le premier plafond
atteint s'applique ; les limites exactes du compte restent visibles dans la console.

1. Crée une clé sur <https://console.groq.com/keys>.
2. Copie `.env.example` vers `.env`.
3. Remplace la valeur par ta clé :

```text
SPARKLE_API_KEY=ta_cle_groq
# Facultatif ; cette valeur est déjà le modèle par défaut.
SPARKLE_MODEL=openai/gpt-oss-120b
```

Le fichier `.env` est chargé automatiquement au démarrage et ignoré par Git.
Ne partage jamais ce fichier : il contient ta clé secrète.
Une variable Windows déjà définie prend le dessus sur la valeur du `.env`.
Après une modification, redémarre Sparkle.

### Refus Groq 403

Un refus 403 n'indique pas forcément une clé invalide. Le problème reproduit
ici venait de Cloudflare : l'identification réseau par défaut `Python-urllib`
était refusée avec le code 1010. Sparkle envoie désormais son propre
`User-Agent: Sparkle/1.0`, qui a été accepté avec la même clé.

Les messages distinguent maintenant les refus Cloudflare, les clés invalides
(401), les modèles bloqués par l'organisation ou le projet (403), et les
quotas atteints (429). Pour un modèle bloqué, consulte les
[permissions des modèles](https://console.groq.com/docs/model-permissions).

### Choix du fournisseur

Pour les réponses textuelles courtes de Sparkle, Groq / GPT-OSS 120B reste la
configuration recommandée : elle exploite la clé existante et privilégie la
rapidité avec un modèle de raisonnement. Il n'existe pas de meilleur modèle
universel : la qualité dépend du type de question et les catalogues évoluent.

Gemini 3.8 Flash est une autre option cloud avec une offre gratuite, notamment
pour un futur usage multimodal. Google distingue le
[palier gratuit sans compte de facturation](https://ai.google.dev/gemini-api/docs/billing)
des paliers payants ; les modèles éligibles sont indiqués dans sa
[grille tarifaire](https://ai.google.dev/gemini-api/docs/pricing).
Cette alternative n'est pas intégrée à Sparkle pour le moment.

Les catalogues communautaires sont utiles pour découvrir des fournisseurs,
mais les conditions et les identifiants doivent être vérifiés auprès de chaque
fournisseur. Le catalogue fourni référence encore certains modèles Groq retirés
de l'offre gratuite ; voir les
[retraits officiels](https://console.groq.com/docs/deprecations).

## Prochain train

Un **double-clic gauche** sur Sparkle ouvre la bulle CFF avec deux champs :

```text
[Départ] > [Arrivée]
```

Renseigne les deux noms de gare : la recherche démarre après une courte pause
dans la saisie, ou immédiatement avec Entrée. Les majuscules et les accents ne
sont pas obligatoires. Si une gare n'est pas reconnue, la bulle affiche :
« Sparkle n'a pas trouvé cette station ! ».

Les heures de départ et d'arrivée apparaissent sur la deuxième ligne ; la ligne
de train et la voie sur la troisième. Seul le prochain train est affiché, avec
un éventuel retard ou changement en dessous. Les champs restent modifiables.
Les gares saisies sont conservées tant que Sparkle reste ouvert.

Les variables `NEAREST_STATION` et `FINAL_STATION` du `.env` sont désormais
facultatives et servent uniquement à préremplir les deux champs au démarrage.
Un clic simple ferme la bulle ; le clic simple habituel ouvre toujours le chat
après le délai de double-clic. Les recherches ne bloquent pas les animations.

Les horaires proviennent de [transport.opendata.ch](https://transport.opendata.ch/docs.html),
avec le filtre `transportations[]=train`. Source des données horaires :
opentransportdata.swiss. Aucune clé API n'est nécessaire pour cette fonction.

## Combo

Chaque contact de souris détecté lorsque Sparkle est en l'air ajoute un point.
La bulle utilise `assets/combo/combo.png` et suit Sparkle en haut à droite.
Elle laisse passer la souris et ne prend pas le focus.

À l'atterrissage, sur le bas de l'écran ou une fenêtre, le prochain combo repart
de zéro. Le dernier score reste affiché pendant deux secondes, puis disparaît.
Un nouveau contact en l'air pendant ce délai démarre un nouveau combo.
Ouvrir le chatbot ou le mode CFF masque immédiatement le score et annule le combo.
Le compteur fonctionne indépendamment du cooldown des effets sonores.

## Effets sonores

Les fichiers de `assets/sfx` sont choisis au hasard selon l'action : `cff` pour
un itinéraire reçu, `crush` pour un atterrissage au sol ou sur une fenêtre,
`glass` pour un bord de l'écran (hors sol) ou un contact de souris en l'air,
`shine` à l'entrée dans un état cute/sad/love, et `talk` pour une réponse reçue.
Les erreurs de réseau et les itinéraires introuvables ne jouent pas de son.

Le cooldown global est modifiable en haut de `src/sound.py` :

```python
SOUND_COOLDOWN_SECONDS = 0.2
```

Il se mesure entre les débuts des sons, toutes catégories confondues. Un
événement pendant ce délai est ignoré, sans lecture différée. Un son déjà lancé
va jusqu'à sa fin, même si un nouveau son commence après le cooldown.
Une valeur de `0` désactive ce délai.

Les sons sont décodés et préchargés avant l'apparition de Sparkle. Leur silence
initial est retiré en mémoire, sans modifier les fichiers originaux. Le flux
audio reste ouvert avec un tampon d'environ 21 ms pour éviter les coupures et
grésillements d'un tampon trop court. Windows et le périphérique audio peuvent
encore ajouter une courte latence matérielle.

Le Bluetooth ajoute un délai de transmission et de décodage que le tampon de
Sparkle ne peut pas supprimer. Pour comparer, utilise une sortie filaire ou USB
audio et redémarre Sparkle. Une prise USB servant uniquement à charger un casque
ne suffit pas : il doit recevoir le son par câble.

Pour choisir une sortie uniquement pour Sparkle, modifie en haut de
`src/sound.py`, puis redémarre l'application :

```python
SOUND_OUTPUT_DEVICE = "Realtek"
```

Branche alors ton casque ou tes enceintes sur cette sortie. Une partie unique
du nom suffit, sans distinction de majuscules ; un nom complet est prioritaire.
La valeur vide `""` conserve la sortie Windows par défaut. Si le nom est absent
ou ambigu, Sparkle utilise la sortie par défaut et indique les sorties disponibles
dans la console. Le cooldown ignore des déclenchements rapprochés ; il ne retarde
jamais leur lecture. Réduire encore le tampon logiciel peut provoquer des
grésillements et ne supprime pas le délai du Bluetooth.

Sur Windows, Sparkle exclut les encodeurs vidéo `av1_mf`, `h264_mf` et `hevc_mf`
du sondage initial de Qt. Ils sont inutiles à la lecture des sons et provoquent
des messages « could not create MFT » lorsque les encodeurs correspondants ne
sont pas installés. Le décodage audio et ses messages d'erreur restent actifs.
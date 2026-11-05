# Bot RSS Discord

Petit bot Discord que j'ai fait pour poster automatiquement les nouveaux articles de mes flux RSS et les vidéos de quelques chaînes Twitch dans des salons Discord.

Toutes les 10 minutes, le bot regarde les flux. S'il y a du nouveau, il le poste dans le bon salon sous forme d'embed. Il garde en mémoire ce qu'il a déjà posté (dans une petite base SQLite) pour éviter les doublons.

## Ce qu'il fait

- Suit des flux RSS (sites d'info, podcasts, chaînes YouTube…)
- Suit des chaînes Twitch via yt-dlp (pas besoin de compte ni d'API Twitch)
- Chaque flux ou chaîne publie dans son propre salon Discord
- Au premier lancement sur un nouveau flux, il poste seulement les 30 derniers articles et marque les plus anciens comme déjà vus
- Publie du plus ancien au plus récent

## Installation

Il faut Python 3.10 ou plus.

```bash
pip install discord.py feedparser yt-dlp python-dotenv
```

Ensuite, créer les fichiers de configuration (voir les sections ci-dessous).

## Le fichier `.env`

Créer un fichier nommé exactement `.env` à côté de `bot.py`. Exemple :

```env
DISCORD_TOKEN=ton_token_de_bot_ici
DB_PATH=articles.db
```

- `DISCORD_TOKEN` (obligatoire) : le token du bot, à récupérer dans le [Discord Developer Portal](https://discord.com/developers/applications) → ton application → *Bot* → *Reset Token*. Le bot refuse de démarrer sans lui.
- `DB_PATH` (optionnel) : chemin du fichier SQLite qui stocke les articles déjà postés. Par défaut, `articles.db`.

Le fichier `.env` contient un secret : il ne doit jamais être commité. Il est déjà listé dans `.gitignore`.

## Les fichiers texte : flux RSS et chaînes Twitch

Les flux ne se configurent plus dans le code. Ils se listent dans deux fichiers texte placés à côté de `bot.py`, lus au démarrage :

| Fichier | Contenu |
| --- | --- |
| `RSS_feeds.txt` | un flux RSS par ligne : URL + ID du salon |
| `Twich_feeds.txt` | une chaîne Twitch par ligne : nom de la chaîne + ID du salon |

Le nom `Twich_feeds.txt` est écrit comme ça dans le code : il faut le reprendre à l'identique.

### Format de `RSS_feeds.txt`

```text
# Format : "URL du flux": ID_du_salon
"https://www.mediapart.fr/journal/podcasts/rss": 1566384937442086993
"https://api.blast-info.fr/rss.xml": 1566144707334246420
"https://www.youtube.com/feeds/videos.xml?channel_id=UCdnaDhU-LDQrIEEmSIfq0-Q": 1566384937442086993
```

- l'URL est entre guillemets, suivie de `:` puis de l'ID du salon (un nombre, sans guillemets) ;
- une ligne qui commence par `#` est un commentaire, les lignes vides sont ignorées ;
- plusieurs flux peuvent publier dans le même salon ;
- une ligne mal formée n'arrête pas le bot : elle est ignorée et un message `[feeds] ligne N ignorée (format invalide)` apparaît dans la console.

Pour une chaîne YouTube, l'URL du flux est :
`https://www.youtube.com/feeds/videos.xml?channel_id=ID_DE_LA_CHAINE`

### Format de `Twich_feeds.txt`

```text
# Format : "nom_de_la_chaine": ID_du_salon   (nom = twitch.tv/<nom>)
"ostpolitik": 1566875561941401630
"laurenemarx": 1566875561941401630
```

- le nom est celui qui apparaît dans l'URL `twitch.tv/<nom>` ; il est converti en minuscules automatiquement ;
- pas de compte ni de clé d'API Twitch : les vidéos sont récupérées avec yt-dlp.

### Récupérer l'ID d'un salon

Dans Discord, aller dans *Paramètres utilisateur* → *Avancés* → activer le **mode développeur**. Ensuite, clic droit sur le salon → **Copier l'identifiant**.

### Ajouter ou modifier un flux

1. Ajouter ou modifier la ligne dans le fichier texte concerné.
2. Redémarrer le bot : les fichiers ne sont lus qu'au lancement.

Un flux qui apparaît pour la première fois est traité comme un premier lancement : seuls les 30 derniers éléments sont postés.

## Lancer le bot

```bash
python bot.py
```

## Réglages

En haut de `bot.py` :

- `MAX_POSTS_PER_RUN` : nombre max de posts par flux à chaque passage (30 par défaut)
- `FIRST_RUN_POSTS` : nombre d'articles postés la première fois qu'un flux est ajouté (30 par défaut)
- `TWITCH_SCAN_LIMIT` : nombre de vidéos récentes regardées par chaîne Twitch à chaque passage (30 par défaut)
- `DB_PATH` : peut aussi être défini dans `.env`, voir plus haut

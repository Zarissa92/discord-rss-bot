# Bot RSS Discord

Petit bot Discord que j'ai fait pour poster automatiquement les nouveaux articles de mes flux RSS (et les vidéos de chaînes Twitch) dans des salons Discord.

Toutes les 10 minutes il regarde les flux, et s'il y a du nouveau il le poste dans le bon salon sous forme d'embed. Il garde en mémoire ce qu'il a déjà posté (dans une petite base SQLite) pour pas faire de doublons.

## Ce qu'il fait

- Suit des flux RSS (sites d'info, podcasts, chaînes YouTube…)
- Suit des chaînes Twitch via yt-dlp (pas besoin de compte ni d'API Twitch)
- Chaque flux / chaîne a son propre salon Discord
- Au premier lancement sur un nouveau flux, il poste seulement les 30 derniers articles et marque les plus vieux comme déjà vus
- Poste du plus ancien au plus récent

## Installation

Il faut Python 3.10 ou plus.

```bash
pip install discord.py feedparser yt-dlp python-dotenv
```

Ensuite créer un fichier `.env` à côté du script :

```
DISCORD_TOKEN=le_token_du_bot
DB_PATH=articles.db
```

`DB_PATH` est optionnel, par défaut c'est `articles.db`.

## Lancer le bot

```bash
python bot.py
```

## Ajouter un flux

Dans le script, ajouter une ligne dans `FEEDS` avec l'URL du flux et l'ID du salon :

```python
FEEDS = {
    "https://exemple.com/feed.xml": 123456789012345678,
}
```

Pour une chaîne YouTube, le flux c'est :
`https://www.youtube.com/feeds/videos.xml?channel_id=ID_DE_LA_CHAINE`

## Ajouter une chaîne Twitch

Dans `TWITCH_CHANNELS`, mettre le nom de la chaîne (celui dans `twitch.tv/<nom>`) et l'ID du salon :

```python
TWITCH_CHANNELS = {
    "nomdelachaine": 123456789012345678,
}
```

⚠️ Pas la peine de remettre les anciens flux Twitch via openrss dans `FEEDS`, sinon ça fait des doublons.

## Réglages

En haut du script :

- `MAX_POSTS_PER_RUN` : nombre max de posts par flux à chaque passage
- `FIRST_RUN_POSTS` : nombre d'articles postés la première fois qu'un flux est ajouté
- `TWITCH_SCAN_LIMIT` : nombre de vidéos récentes regardées par chaîne Twitch

Pour récupérer l'ID d'un salon : activer le mode développeur dans Discord, puis clic droit sur le salon → Copier l'identifiant.
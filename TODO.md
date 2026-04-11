# instagram l2
Extract and process the following fields:
 - src_file
 - node.id
 - node.shortcode
 - node.edge_media_to_comment.count 
 - node.owner.username
 - node.owner.full_name
 - node.edge_media_to_caption.edges: json array to compare with the `node.iphon_struct.caption.<element>`. Example: [{'node': {'created_at': '1759602114', 'text': 'Ma façon de vous souhaiter une bonne rentrée avec un peu d\'humour en cette journée qui peut être forte en émotions pour beaucoup.\n\nExtrait de la série québécoise "Les beaux malaises".', 'id': '18028768844722096'}}]
 - node.iphone_struct.caption.created_at_utc
 - node.iphone_struct.caption.text
 - node.iphone_struct.caption.user.full_name
 - node.iphone_struct.caption.user.username
 
## From node.iphone_struct.caption.text
	Extract tags. Examples: 
	- `#aerialsilks #aerialrope #training #flex #loveart #vertigocirko'`
	- `Después de 10000 intentos 😄 #training #flex #aerialsilks #vertigocirko`
 
 How to save them? To be searchable
 
# Add whatsapp chat history
Dropbox location Apps/logme_rjof/WhatsApp
It's a zip which includes the name "Chat de WhatsApp con <person_name>.txt"

## Goal
How long it takes an answer

# working in processing Multi_Timer
Create Muti_Timer_l1:
 - Use the fields & field_type from the source conf in config.ini
 - Make the convertions and validations

 processing/Multi_TimerProcessor.py

# Reformat all sources based in Multi_Timer source
# Lots of fails in new installation

# Souces to add
## Spotify
https://developer.spotify.com/documentation/web-api
## koreader Clipping (kindle)
## pomodoro
## podcast adict
## Multi timer
## Tap log
## loop habits
## History from google maps (timeline)
## History of Redmi Watch 2 Lite (wearable)
## Mi Smart Band 4 (wearable)
## Mi Fit (google app)
## WhatsApp text

# Sources storage to add
 - Dropbox

# Stats
## KoreaderStatistics
  - Time by book
  - Mean time by page (by book)
  - 120 seconds in page (comment) might indicate I fell asleep.
## KoreaderClipping
  - Create Anki cards from every note.
  - In case of a single word highlighted it is probable a word to learn. The process should be to look for a definition in the original language and add a Anki card with the definition.
  - When a new book is find ask gptchat to create a set of X amount of questions about the book.
  
# Rules generation
 For example:
 ```
 If third day without making excersise:
   send a notification: 'Make excersise today"
   ```
# Communication channel
Link the api to a slack channel

# Visual interface
Mainly for statistics.

Use shiny (Rlang) or Express (? Learning opportunity vs learning curve)

# DONE <2024-12-31 15:48> Instagram
Add */media/rjof/toshiba/rjof/instagram/instaloader/instagram_organizer/* to process instagram videos

# DONE <2024-01-25 14:34> change logs destination
to data location: ~/logme_data using the config
[LogsPath]
logs_path = /home/rjof/logme_data/logs



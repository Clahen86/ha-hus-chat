"""Constants for House Chat (Hus-chat)."""

DOMAIN = "hus_chat"
PANEL = "hus-chat"
STATIC = "/hus_chat_static"
SIGNAL = "hus_chat_update"
MAX_MESSAGES = 1000  # the oldest go (with their pictures and voice messages)
SHOWN = 200  # sent to the chat when it opens
STALE_S = 30 * 24 * 3600  # a phone whose location has been gone this long gets no messages
ESCALATE_S = 10 * 60  # a house message nobody took goes to everyone after this
HOUSE = "house"
TITLES = {"da": "Hus-chat", "nb": "Hus-chat", "sv": "Hus-chatt", "de": "Haus-Chat", "nl": "Huis-chat", "fr": "Chat maison"}
DEFAULT_TITLE = "House Chat"

TEXT = {
    "da": {"onway": "På vej hjem", "eta": "hjemme ca. kl. {t}", "arrived": "{name} er hjemme", "reply": "Svar", "take": "✋ Jeg tager den", "taken": "{name} tog den", "nobody": "Ingen har reageret – sendt til alle.",
           "house": "Huset", "image": "📷 Billede", "audio": "🎤 Lydbesked", "family": "Familien",
           "meal_ready": "Maden er klar: {meal} ({kid})", "cook": "{kid} laver mad i dag: {meal}", "cook_at": ", klar ca. kl. {t}"},
    "en": {"onway": "On my way home", "eta": "home about {t}", "arrived": "{name} is home", "reply": "Reply", "take": "✋ I'll take it", "taken": "{name} took it", "nobody": "Nobody reacted – sent to everyone.",
           "house": "The house", "image": "📷 Picture", "audio": "🎤 Voice message", "family": "Family",
           "meal_ready": "Dinner is ready: {meal} ({kid})", "cook": "{kid} is cooking today: {meal}", "cook_at": ", ready about {t}"},
    "de": {"onway": "Auf dem Heimweg", "eta": "zu Hause gegen {t}", "arrived": "{name} ist zu Hause", "reply": "Antworten", "take": "✋ Ich mach das", "taken": "{name} macht es", "nobody": "Niemand hat reagiert – an alle gesendet.",
           "house": "Das Haus", "image": "📷 Bild", "audio": "🎤 Sprachnachricht", "family": "Familie",
           "meal_ready": "Das Essen ist fertig: {meal} ({kid})", "cook": "{kid} kocht heute: {meal}", "cook_at": ", fertig gegen {t}"},
    "sv": {"onway": "På väg hem", "eta": "hemma ca kl. {t}", "arrived": "{name} är hemma", "reply": "Svara", "take": "✋ Jag tar det", "taken": "{name} tog det", "nobody": "Ingen reagerade – skickat till alla.",
           "house": "Huset", "image": "📷 Bild", "audio": "🎤 Röstmeddelande", "family": "Familjen",
           "meal_ready": "Maten är klar: {meal} ({kid})", "cook": "{kid} lagar mat i dag: {meal}", "cook_at": ", klart ca kl. {t}"},
    "nb": {"onway": "På vei hjem", "eta": "hjemme ca. kl. {t}", "arrived": "{name} er hjemme", "reply": "Svar", "take": "✋ Jeg tar den", "taken": "{name} tok den", "nobody": "Ingen reagerte – sendt til alle.",
           "house": "Huset", "image": "📷 Bilde", "audio": "🎤 Talemelding", "family": "Familien",
           "meal_ready": "Maten er klar: {meal} ({kid})", "cook": "{kid} lager mat i dag: {meal}", "cook_at": ", klar ca. kl. {t}"},
    "nl": {"onway": "Onderweg naar huis", "eta": "thuis rond {t}", "arrived": "{name} is thuis", "reply": "Antwoorden", "take": "✋ Ik doe het", "taken": "{name} doet het", "nobody": "Niemand reageerde – naar iedereen gestuurd.",
           "house": "Het huis", "image": "📷 Foto", "audio": "🎤 Spraakbericht", "family": "Familie",
           "meal_ready": "Het eten is klaar: {meal} ({kid})", "cook": "{kid} kookt vandaag: {meal}", "cook_at": ", klaar rond {t}"},
    "fr": {"onway": "En route vers la maison", "eta": "à la maison vers {t}", "arrived": "{name} est à la maison", "reply": "Répondre", "take": "✋ Je m'en occupe", "taken": "{name} s'en occupe", "nobody": "Personne n'a réagi – envoyé à tous.",
           "house": "La maison", "image": "📷 Photo", "audio": "🎤 Message vocal", "family": "Famille",
           "meal_ready": "Le repas est prêt : {meal} ({kid})", "cook": "{kid} cuisine aujourd'hui : {meal}", "cook_at": ", prêt vers {t}"},
}

BUILTIN_AGENT = "conversation.home_assistant"  # Home Assistant's own Assist - always there, no quota
AI_RETRY_S = 30 * 60  # an AI that failed isn't asked again for this long
AI_TIMEOUT_S = 45  # no answer from the AI in this long: Home Assistant's own answers
NOTE_FALLBACK = {
    "da": "Svaret af Home Assistant – {name} svarede ikke", "en": "Answered by Home Assistant – {name} didn't answer",
    "de": "Beantwortet von Home Assistant – {name} hat nicht geantwortet", "sv": "Besvarat av Home Assistant – {name} svarade inte",
    "nb": "Besvart av Home Assistant – {name} svarte ikke", "nl": "Beantwoord door Home Assistant – {name} antwoordde niet",
    "fr": "Répondu par Home Assistant – {name} n'a pas répondu",
}

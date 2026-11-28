# Changelog – House Chat

Newest first. Each version lists what changed since the one before.

## 0.14.0 – 2026-11-28

- "Lige nu" on top of the chat: what matters right now – a machine waiting to be emptied, who is on the way home and when, tonight's dinner and how many eat with, the bins out tonight. It changes by itself and goes when it's over; a tap finds the message
- Tasks go when they're done: an emptied machine, an answered doorbell or a bin taken out shows small in the chat and is gone from every phone – also when someone had pressed "I'll take it" first
- Good morning is personal: each one gets their own – a child their school day, their friends' birthdays (a week ahead too) and their chores; the grown-ups when each child is out of school, the family calendar today and the cheapest power. Found in your calendars, nobody sees another child's day
- The bins: the evening before, which bin is collected tomorrow (from your waste calendar, e.g. Affaldshåndtering DK) with "I'll take it"
- A machine done at night rings no phone – it waits in the chat and in good morning
- Ask the house: "what's for dinner?", "who's home?", "when are the bins collected?", "when is Holly out of school?", "when is power cheapest?", "what do I have today?" – answered at once, without an AI
- Shopping understands more: "we need milk", "out of coffee" – onto Madplan's shopping list when you have Madplan, otherwise Home Assistant's, never twice
- Reminders: "remind me to take the parcel in when I get home", and "remind us about the bins every Tuesday at 18"
- An app link keeps its own quiet hours and push setting; an edited reminder rings at the new time; a personal message is never read aloud on the speaker

## 0.13.1 – 2026-11-22

- The dinner poll came as a plain message: the Yes/No buttons now show in the chat, and in the notification on the phone - a tap there counts as your answer

## 0.13.0 – 2026-11-22

- Good morning at 7: the weather, dinner from Madplan and who cooks, chores left per child in Pligt-pilot, and the cheapest three hours for power - each line only when it's there. Switch it on under Settings → Messages from the house
- Home for dinner? A poll every day at the time you choose. Those who say yes get "dinner is ready" (from Pligt-pilot, or hus_chat.send with to: dinner) - nobody answered: those at home
- Messages to those at home also reach anyone whose location is unknown, or whose phone hasn't reported for 6 hours - in doubt, included
- No more warning in Home Assistant's log at start-up (the version was read from disk in the event loop)

## 0.12.1 – 2026-11-18

- The app from a link shows the house button when it's allowed, and always loads the newest version

## 0.12.0 – 2026-11-18

- A link may talk to the house when an admin allows it: Assist only, never locks, alarm or garage doors

## 0.11.0 – 2026-11-18

- A child takes a machine in Pligt-pilot: 'Take it in Pligter' in the chat and on the phone

## 0.10.1 – 2026-11-18

- The bubble stays tucked away on every address until a new message

## 0.10.0 – 2026-11-18

- Docs: settings picture with the QR code
- Works with Pligt-pilot and Madplan: who took the machine, cook day, food is ready

## 0.9.1 – 2026-11-18

- App links: QR code to scan

## 0.9.0 – 2026-11-18

- The chat as an app from a link (no login, web push), read aloud, shopping list, reminders, polls, on my way home, search and pin, double tap tucks the bubble away

## 0.8.0 – 2026-11-16

- Setup: who gets a house message is only home/all/persons - never a person's id
- Store and update links open right inside Home Assistant
- Error reports: a translated message shown on purpose (a refusal) is not reported as an error
- Support: version from Home Assistant's loader, no blocking read in the event loop
- Private messages, delete and clear, reply, react, edit, seen by, no duplicates, follow-up survives restart, phones cleared when read

## 0.7.0 – 2026-11-14

- How it is set up, once a day for the developer (names cleaned), and the Share my setup switch

## 0.6.0 – 2026-11-14

- Update card (new version, your error fixed) and the version in the daily question

## 0.5.2 – 2026-11-14

- Home Assistant's own commands first, questions keep running when the phone disconnects, AI given up after 45 s

## 0.5.1 – 2026-11-14

- When the chosen AI can't answer (quota used up, offline), Home Assistant's own Assist answers with a note

## 0.5.0 – 2026-11-14

- Choose which AI answers for the house (any conversation agent in HA, default: the one Assist uses)

## 0.4.5 – 2026-11-14

- Speak to the house like a voice command (Assist speech-to-text, sends by itself)
- Send button always fits

## 0.4.4 – 2026-11-14

- Settings in the sidebar page were empty - the page now fills the screen

## 0.4.3 – 2026-11-14

- The suggestions can never stop the settings from showing

## 0.4.2 – 2026-11-14

- Files under a new address for every version, so a browser never mixes old and new files

## 0.4.1 – 2026-11-14

- A closed bubble tucks away as a small tab at the edge

## 0.4.0 – 2026-11-14

- Suggestions of the other apps (fits your home, from the same developer)

## 0.3.1 – 2026-11-14

- Clearer urgent messages, README with the house's messages and new pictures

## 0.3.0 – 2026-11-14

- A freezer that stopped or a dehumidifier with a full tank (Appliance Watch) - a stopped freezer rings like an alarm

## 0.2.0 – 2026-11-14

- Check again
- Everyone with the Home Assistant app is in the chat - a person isn't needed
- At home from the phone's own location
- My phones: turn an old phone off
- A phone whose location has been gone for 30 days gets no messages
- The house writes by itself (machines done, smoke/water/CO ringing like an alarm, doorbell with a picture, alarm), who gets what per kind, mute a kind for yourself

## 0.1.0 – 2026-11-14

- House Chat 0.1.0: the family's chat in Home Assistant - a bubble on every page, the house writes along, answers from the notification, I'll take it, quiet hours, pictures and voice messages, Assist

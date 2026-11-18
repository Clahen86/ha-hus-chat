// House Chat (Hus-chat) - loaded by Home Assistant on every page (the chat bubble) and as the sidebar panel.
// No build step. The bubble can be dragged, and dropped on ✕ to tuck it away as a small tab at the edge of the screen -
// a tap on the tab brings it back, and so does a new message.
import { defineSupport, defineUpdate } from "./support.js";
import { defineSuggest } from "./suggest.js";

const T = {
  da: { family: "Familien", home: "{names} er hjemme", homeOne: "{names} er hjemme", nobody: "Ingen er hjemme", write: "Skriv en besked …",
    ask: "Spørg eller styr huset …", toHouse: "Til huset", house: "Huset", today: "I dag", yesterday: "I går", take: "✋ Jeg tager den",
    took: "✓ {name} tog den", you: "dig", settings: "Indstillinger", agentT: "🤖 Hvem svarer for huset", agentH: "Den AI, der svarer, når du skriver eller taler til huset. Tilføj flere under Indstillinger → Enheder og tjenester (fx Google AI, OpenAI, Ollama).", asAssist: "Som i Assist", builtin: "Home Assistant", quiet: "Stille timer", quietH: "Kun det, der haster (røg, vand …), kommer igennem.",
    from: "Fra", to: "Til", push: "Beskeder på telefonen", pushH: "Når appen er lukket, kan du svare direkte i beskeden.",
    bubble: "Vis chat-boblen", bubbleH: "Boblen ligger over alt i Home Assistant. Træk den ned på ✕ eller tryk to gange hurtigt på den, så gemmer den sig som en lille fane i kanten – tryk på fanen, eller den kommer selv, når nogen skriver.",
    help: "🛟 Hjælp", close: "Luk", rec: "Optager …", cancel: "Annuller", empty: "Sig hej til familien 👋", emptyH: "Huset skriver også her – fx når vaskemaskinen er færdig.",
    rules: "Beskeder fra huset", rulesH: "Huset skriver selv, når noget sker. Vælg hvem der får hvad.", rulesKid: "Kun en admin kan ændre, hvem der får hvad.",
    topics: { machines: "🧺 Maskiner færdig", safety: "🔥 Røg, vand og CO", doorbell: "🔔 Det ringer på døren", alarm: "🚨 Alarm" },
    topicsH: { machines: "Maskiner færdige, og fryser eller affugter med problemer (fra Maskiner)", safety: "Ringer som en alarm på telefonen – også på lydløs", doorbell: "Med et billede fra kameraet ved døren", alarm: "Når alarmen går, eller slås til og fra" },
    toHome: "Hjemme", toAll: "Alle", forMe: "Til mig", always: "Altid", on: "Slået til",
    myPhones: "Mine telefoner", myPhonesH: "Slå en gammel telefon fra, så den ikke får beskeder.", stale: "ikke set i 30 dage – får ingen beskeder",
    picture: "Billede", voice: "Lydbesked", listen: "Lytter … sig det til huset", noStt: "Tale er ikke sat op i Assist – skriv i stedet.", heard: "Hørte ikke noget – prøv igen.", micNo: "Mikrofonen er ikke tilladt.", failed: "Kunne ikke sende – prøv igen.", back: "Tilbage", toHouseH: "Svar fra huset",
    reply: "Svar", edit: "Rediger", del: "Slet", delAsk: "Slette beskeden for alle?", edited: "redigeret", seen: "Set af {names}", replyTo: "Svarer {name}", editing: "Retter beskeden",
    clear: "Ryd hele chatten", clearH: "Sletter alle beskeder, billeder og lydbeskeder for alle. Kan ikke fortrydes.", clearAsk: "Slette hele chatten for alle?",
    tomorrow: "I morgen", more: "Mere", pollT: "Afstemning", pollQ: "Spørgsmål", pollOpt: "Svar {n}", pollAdd: "+ Svar", pollSend: "Send afstemning", votes: "{n} stemmer", vote1: "1 stemme",
    onway: "På vej hjem", shopT: "Indkøbsliste", shopAdd: "Tilføj vare", shopNone: "Ingen indkøbsliste i Home Assistant. Tilføj integrationen »Indkøbsliste«.", shopEmpty: "Listen er tom 🎉",
    onShop: "🛒 På indkøbslisten", remindAt: "⏰ Påmindelse {when}", pin: "Fastgør", unpin: "Fjern fastgørelse", search: "Søg i beskeder", searchNone: "Ingen beskeder passer",
    speakT: "Læs højt", speakH: "Husets beskeder siges på en højttaler, når nogen er hjemme – ikke om natten, undtagen alarmer.", speakPick: "– vælg højttaler –", speakTest: "Prøv", speakNoTts: "Ingen tale (TTS) er sat op i Home Assistant.",
    apps: "Chatten som app – uden login", appsH: "Til børn og andre uden en Home Assistant-konto. De åbner linket og vælger »Føj til hjemmeskærm«. Linket giver kun adgang til chatten.",
    appsLocal: "Kun hjemme: Home Assistant har ingen adresse udefra (Nabu Casa).", appName: "Navn", appWho: "Hvem er det?", appAlone: "Kun med navnet", appNew: "Lav link",
    appCopy: "Kopiér", appCopied: "Kopieret", appShare: "Del", appDel: "Slet", appDelAsk: "Slette linket? Appen holder op med at virke for {n}.", appDevices: "{n} med beskeder", notMember: "Du er ikke med i familiens chat endnu. Bed en admin om at gøre dig til en person i Home Assistant, eller installer appen på din telefon." },
  en: { family: "Family", home: "{names} are home", homeOne: "{names} is home", nobody: "Nobody is home", write: "Write a message …",
    ask: "Ask or control the house …", toHouse: "To the house", house: "The house", today: "Today", yesterday: "Yesterday", take: "✋ I'll take it",
    took: "✓ {name} took it", you: "you", settings: "Settings", agentT: "🤖 Who answers for the house", agentH: "The AI that answers when you write or speak to the house. Add more under Settings → Devices & services (e.g. Google AI, OpenAI, Ollama).", asAssist: "As in Assist", builtin: "Home Assistant", quiet: "Quiet hours", quietH: "Only what's urgent (smoke, water …) comes through.",
    from: "From", to: "To", push: "Messages on the phone", pushH: "When the app is closed you can answer right in the notification.",
    bubble: "Show the chat bubble", bubbleH: "The bubble floats over all of Home Assistant. Drag it onto ✕ or tap it twice quickly and it tucks away as a small tab at the edge – tap the tab, or it comes back when somebody writes.",
    help: "🛟 Help", close: "Close", rec: "Recording …", cancel: "Cancel", empty: "Say hi to the family 👋", emptyH: "The house writes here too – e.g. when the washing machine is done.",
    rules: "Messages from the house", rulesH: "The house writes by itself when something happens. Choose who gets what.", rulesKid: "Only an admin can change who gets what.",
    topics: { machines: "🧺 Machines done", safety: "🔥 Smoke, water and CO", doorbell: "🔔 Someone at the door", alarm: "🚨 Alarm" },
    topicsH: { machines: "Machines done, and a freezer or dehumidifier in trouble (from Appliance Watch)", safety: "Rings like an alarm on the phone – also on silent", doorbell: "With a picture from the camera at the door", alarm: "When the alarm goes off, or is armed and disarmed" },
    toHome: "At home", toAll: "Everyone", forMe: "For me", always: "Always", on: "On",
    myPhones: "My phones", myPhonesH: "Turn an old phone off so it gets no messages.", stale: "not seen for 30 days – gets no messages",
    picture: "Picture", voice: "Voice message", listen: "Listening … tell the house", noStt: "Speech isn't set up in Assist – type instead.", heard: "Didn't catch that – try again.", micNo: "The microphone isn't allowed.", failed: "Couldn't send – try again.", back: "Back", toHouseH: "Answer from the house",
    reply: "Reply", edit: "Edit", del: "Delete", delAsk: "Delete the message for everyone?", edited: "edited", seen: "Seen by {names}", replyTo: "Replying to {name}", editing: "Editing the message",
    clear: "Clear the whole chat", clearH: "Deletes every message, picture and voice message for everyone. Can't be undone.", clearAsk: "Delete the whole chat for everyone?",
    tomorrow: "Tomorrow", more: "More", pollT: "Poll", pollQ: "Question", pollOpt: "Answer {n}", pollAdd: "+ Answer", pollSend: "Send poll", votes: "{n} votes", vote1: "1 vote",
    onway: "On my way home", shopT: "Shopping list", shopAdd: "Add item", shopNone: "No shopping list in Home Assistant. Add the “Shopping list” integration.", shopEmpty: "The list is empty 🎉",
    onShop: "🛒 On the shopping list", remindAt: "⏰ Reminder {when}", pin: "Pin", unpin: "Unpin", search: "Search messages", searchNone: "No messages match",
    speakT: "Read aloud", speakH: "The house's messages are said on a speaker when somebody is home – not at night, except alarms.", speakPick: "– pick a speaker –", speakTest: "Try", speakNoTts: "No speech (TTS) is set up in Home Assistant.",
    apps: "The chat as an app – no login", appsH: "For children and others without a Home Assistant account. They open the link and choose “Add to Home Screen”. The link only opens the chat.",
    appsLocal: "Only at home: Home Assistant has no outside address (Nabu Casa).", appName: "Name", appWho: "Who is it?", appAlone: "Just the name", appNew: "Make link",
    appCopy: "Copy", appCopied: "Copied", appShare: "Share", appDel: "Delete", appDelAsk: "Delete the link? The app stops working for {n}.", appDevices: "{n} with messages", notMember: "You're not in the family chat yet. Ask an admin to make you a person in Home Assistant, or install the app on your phone." },
};
const COLORS = ["#ff8a65", "#4db6ac", "#9575cd", "#4fc3f7", "#f06292", "#aed581", "#ffb74d", "#7986cb"];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const haRoot = () => document.querySelector("home-assistant");
const haHass = () => haRoot()?.hass;
const tr = (hass) => T[(hass?.language || "en").split("-")[0]] || T.en;
const media = (name) => `/api/hus_chat/media/${encodeURIComponent(name)}`;

// The logo: two speech bubbles that together make a roof.
export const LOGO = (id = "l") => `<svg viewBox="0 0 100 100" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#ff6b8a"/><stop offset="1" stop-color="#7c5cff"/></linearGradient></defs><rect width="100" height="100" fill="url(#${id})"/>
  <path d="M18 52 L46 24 a6 6 0 0 1 8 0 L56 26 L28 56 V72 L20 78 V60 a8 8 0 0 1 -2 -8Z" fill="#fff" opacity=".95"/>
  <path d="M82 52 L54 24 a6 6 0 0 0 -8 0 L44 26 L72 56 V72 L80 78 V60 a8 8 0 0 0 2 -8Z" fill="#fff" opacity=".65"/>
  <rect x="40" y="52" width="20" height="22" rx="5" fill="#fff"/></svg>`;

function shrink(file) {  // a phone photo becomes ~300 kB: at most 1600 px, JPEG
  return new Promise((ok) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const k = Math.min(1, 1600 / Math.max(img.width, img.height)), c = document.createElement("canvas");
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
      c.toBlob((b) => ok(b), "image/jpeg", 0.82);
    };
    img.onerror = () => { URL.revokeObjectURL(url); ok(null); };
    img.src = url;
  });
}

const STYLE = `
:host{--bg:#f5f6fb;--panel:#ffffff;--bubble:#eceef6;--text:#151829;--muted:#6b7090;--line:rgba(20,24,60,.08);--me1:#6f5cff;--me2:#2f8bff;
  --card1:rgba(255,107,138,.12);--card2:rgba(124,92,255,.12);--cardline:rgba(124,92,255,.28);--ok:#1fa971;
  display:flex;flex-direction:column;height:100%;min-height:0;background:var(--bg);color:var(--text);font-family:-apple-system,"SF Pro Text","Inter","Segoe UI",Roboto,sans-serif;position:relative;overflow:hidden}
:host([dark]){--bg:#0f1020;--panel:#171a2e;--bubble:#262a45;--text:#f3f4fb;--muted:#9aa0c8;--line:rgba(255,255,255,.07);--card1:rgba(255,107,138,.18);--card2:rgba(124,92,255,.2);--cardline:rgba(160,140,255,.32);--ok:#8ff0b8}
*{box-sizing:border-box}
button{font:inherit;color:inherit;cursor:pointer;border:0;background:none}
.pinbar{display:flex;align-items:center;gap:8px;padding:8px 14px;background:var(--panel);border-bottom:1px solid var(--line);font-size:13px;cursor:pointer;flex:none}
.pinbar span{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pinbar b{color:#7c5cff;margin-right:4px}
.srch{flex:1;min-width:0;padding:9px 12px;border-radius:20px;border:1px solid var(--line);background:var(--bubble);color:var(--text);font:inherit;font-size:15px;outline:none}
.b.poll{min-width:220px;max-width:100%;white-space:normal}.poll .q{font-weight:650;margin-bottom:8px}.poll button{position:relative;display:block;width:100%;text-align:left;margin-top:6px;padding:9px 12px;border-radius:12px;background:var(--line);overflow:hidden;font:inherit;font-size:14px}
.poll button i{position:absolute;inset:0 auto 0 0;background:linear-gradient(135deg,#ff6b8a55,#7c5cff55);border-radius:12px}.poll button span{position:relative;display:flex;justify-content:space-between;gap:8px}.poll button.mine{box-shadow:inset 0 0 0 2px #7c5cff}
.poll small{display:block;margin-top:6px;color:var(--muted);font-size:12px}
.tag{display:inline-block;margin-top:5px;font-size:12px;padding:3px 9px;border-radius:99px;background:var(--line);color:var(--muted)}
.frm input{width:100%;box-sizing:border-box;padding:11px 12px;margin-top:8px;border-radius:12px;border:1px solid var(--line);background:var(--bubble);color:var(--text);font:inherit;font-size:15px}
.shopi{display:flex;align-items:center;gap:12px;padding:12px 2px;border-top:1px solid var(--line);font-size:15px}.shopi button{width:24px;height:24px;border-radius:50%;border:2px solid var(--muted);flex:none}
.hit{background:#ffd54a66;border-radius:3px}
.top{display:flex;align-items:center;gap:10px;padding:12px 14px;background:var(--panel);border-bottom:1px solid var(--line);flex:none}
.logo{width:40px;height:40px;border-radius:12px;overflow:hidden;flex:none;box-shadow:0 4px 12px rgba(124,92,255,.35)}.logo svg{width:100%;height:100%;display:block}
.tt{min-width:0;flex:1}.tt b{display:block;font-size:17px}.tt span{display:block;font-size:12.5px;color:var(--ok);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tt span.away{color:var(--muted)}
.faces{display:flex;flex:none}.faces .av{width:28px;height:28px;font-size:12px;margin-left:-8px;border:2px solid var(--panel)}.faces .av.out{filter:grayscale(1);opacity:.55}
.ib{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;font-size:19px;flex:none}.ib:hover{background:var(--line)}
.ib svg{width:22px;height:22px;fill:currentColor}
.list{flex:1;overflow-y:auto;padding:14px 12px 8px;display:flex;flex-direction:column;gap:4px;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
.day{align-self:center;font-size:11.5px;color:var(--muted);background:var(--line);padding:3px 10px;border-radius:99px;margin:10px 0 6px}
.row{display:flex;gap:7px;align-items:flex-end;max-width:100%}.row.new{animation:in .22s ease}.row.me{flex-direction:row-reverse}
@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.av{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700;color:#fff;flex:none;overflow:hidden;background-size:cover;background-position:center}
.av.house{background:none}.av.house svg{width:100%;height:100%}
.av.gap{visibility:hidden}
.col{display:flex;flex-direction:column;gap:3px;max-width:78%;min-width:0}.me .col{align-items:flex-end}
.who{font-size:11.5px;color:var(--muted);margin:6px 0 1px 4px}
.b{padding:9px 13px;border-radius:20px;font-size:15px;line-height:1.38;background:var(--bubble);white-space:pre-wrap;word-wrap:break-word;overflow-wrap:anywhere}
.me .b{background:linear-gradient(135deg,var(--me1),var(--me2));color:#fff}
.b.house{background:linear-gradient(135deg,var(--card1),var(--card2));border:1px solid var(--cardline)}
.b .lbl{display:block;font-size:11px;opacity:.75;margin-bottom:2px}
.b .note{display:block;font-size:11px;opacity:.6;margin-top:4px}
.card{border-radius:20px;background:linear-gradient(135deg,var(--card1),var(--card2));border:1px solid var(--cardline);padding:11px 13px;min-width:200px}
.card .h{font-weight:650;font-size:15px}.card .s{font-size:14px;margin-top:3px;white-space:pre-wrap}
.card .urgent{display:inline-grid;place-items:center;width:20px;height:20px;font-size:12px;font-weight:800;color:#fff;background:#ff3b5c;border-radius:50%;margin-right:7px;vertical-align:2px}
.card.hot{border-color:#ff3b5c;box-shadow:0 0 0 3px rgba(255,59,92,.15);animation:hot 1.6s ease-in-out infinite}@keyframes hot{50%{box-shadow:0 0 0 6px rgba(255,59,92,.05)}}
.chips{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}.chip{font-size:13.5px;font-weight:650;padding:8px 13px;border-radius:99px;background:var(--panel);box-shadow:0 1px 3px rgba(0,0,0,.12)}
.chip.go{background:linear-gradient(135deg,#ff6b8a,#7c5cff);color:#fff}.set .chip{background:var(--bubble);box-shadow:none;padding:6px 11px;font-size:13px}.set .chip.go{background:linear-gradient(135deg,#ff6b8a,#7c5cff);color:#fff}.chip:disabled{cursor:default;opacity:.85}
.done{font-size:12px;color:var(--ok);margin:4px 0 0 4px}
.pic{display:block;max-width:240px;max-height:300px;width:100%;border-radius:18px;object-fit:cover;cursor:zoom-in;background:var(--line)}
.time{font-size:10.5px;color:var(--muted);margin:1px 6px 4px}
.audio{display:flex;align-items:center;gap:9px;padding:8px 12px 8px 8px;border-radius:22px;background:var(--bubble);min-width:200px}
.me .audio{background:linear-gradient(135deg,var(--me1),var(--me2));color:#fff}
.play{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.9);color:#6f5cff;display:grid;place-items:center;font-size:14px;flex:none}
.wave{flex:1;height:26px;display:flex;align-items:center;gap:2px}.wave i{flex:1;border-radius:2px;background:currentColor;opacity:.35}.wave i.on{opacity:1}
.dur{font-size:12px;opacity:.8;min-width:32px;text-align:right}
.empty{margin:auto;text-align:center;color:var(--muted);padding:20px}.empty .logo{width:72px;height:72px;border-radius:22px;margin:0 auto 14px}.empty b{display:block;color:var(--text);font-size:17px;margin-bottom:4px}
.bar{display:flex;gap:8px;align-items:flex-end;padding:10px 10px calc(10px + env(safe-area-inset-bottom));background:var(--panel);border-top:1px solid var(--line);flex:none}
.field{flex:1;min-width:0;display:flex;align-items:flex-end;gap:4px;background:var(--bubble);border-radius:22px;padding:4px 4px 4px 14px;min-height:44px}
textarea{flex:1;min-width:0;width:100%;border:0;background:none;color:var(--text);font:inherit;font-size:15px;resize:none;max-height:120px;padding:9px 0;outline:none;line-height:1.35}
textarea::placeholder{color:var(--muted)}
.hb{height:36px;border-radius:18px;padding:0 10px;display:flex;align-items:center;gap:6px;font-size:13px;font-weight:650;color:var(--muted);flex:none}
.hb .mini{width:22px;height:22px;border-radius:7px;overflow:hidden;filter:grayscale(1);opacity:.7}.hb .mini svg{width:100%;height:100%;display:block}
.hb.on{background:linear-gradient(135deg,#ff6b8a,#7c5cff);color:#fff}.hb.on .mini{filter:none;opacity:1}
.round{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;flex:none;font-size:19px}
.round.go{background:linear-gradient(135deg,var(--me1),var(--me2));color:#fff;box-shadow:0 4px 14px rgba(79,108,255,.4)}
.round.cam{background:var(--bubble)}
.round svg{width:22px;height:22px;fill:currentColor}
.recbar{flex:1;display:flex;align-items:center;gap:10px;height:44px;border-radius:22px;background:var(--bubble);padding:0 14px;font-weight:600}
.dot{width:10px;height:10px;border-radius:50%;background:#ff3b5c;animation:blink 1s infinite}@keyframes blink{50%{opacity:.25}}
.err{position:absolute;left:50%;bottom:80px;transform:translateX(-50%);background:#ff3b5c;color:#fff;padding:8px 14px;border-radius:99px;font-size:13px;z-index:5}
.sheet{position:absolute;inset:0;background:var(--bg);z-index:4;display:flex;flex-direction:column;animation:up .2s ease}
@keyframes up{from{transform:translateY(16px)}to{transform:none}}
:host([sheet]) .list,:host([sheet]) .bar{display:none}
.sbody{padding:14px;overflow-y:auto;flex:1}
.set{background:var(--panel);border-radius:18px;padding:14px;margin-bottom:12px}
.srow{display:flex;gap:12px;align-items:center}.srow div{flex:1}.srow small{display:block;color:var(--muted);font-size:12.5px;margin-top:2px}
.sw{width:46px;height:28px;border-radius:14px;background:var(--line);position:relative;flex:none;transition:background .15s}
.sw::after{content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.3);transition:left .15s}
.sw.on{background:linear-gradient(135deg,#ff6b8a,#7c5cff)}.sw.on::after{left:21px}
.times{display:flex;gap:10px;margin-top:12px}.times label{flex:1;font-size:12.5px;color:var(--muted)}
.times input{display:block;width:100%;margin-top:4px;padding:9px;border-radius:12px;border:1px solid var(--line);background:var(--bubble);color:var(--text);font:inherit}
.link{width:100%;text-align:left;padding:14px;border-radius:18px;background:var(--panel);font-weight:600}
.quote{font-size:12.5px;padding:5px 9px;margin-bottom:5px;border-left:3px solid currentColor;border-radius:6px;background:rgba(0,0,0,.06);opacity:.85;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}
.me .quote{background:rgba(255,255,255,.18)}
.ed{font-size:10.5px;opacity:.6;margin-left:6px}
.reacts{display:flex;gap:4px;flex-wrap:wrap;margin-top:-2px}.reacts button{font-size:12.5px;padding:2px 7px;border-radius:99px;background:var(--panel);box-shadow:0 1px 2px rgba(0,0,0,.12)}.reacts button.mine{box-shadow:0 0 0 1.5px #7c5cff}
.seen{align-self:flex-end;font-size:11px;color:var(--muted);margin:0 8px 4px}
.acts{position:absolute;inset:0;z-index:5;background:rgba(10,10,30,.35);display:flex;align-items:flex-end;animation:up .15s ease}
.acts .box{width:100%;background:var(--panel);border-radius:22px 22px 0 0;padding:14px 14px calc(14px + env(safe-area-inset-bottom))}
.acts .emo{display:flex;justify-content:space-around;margin-bottom:10px}.acts .emo button{font-size:26px;width:46px;height:46px;border-radius:50%}.acts .emo button:hover{background:var(--line)}
.acts .do{display:block;width:100%;text-align:left;padding:13px 10px;border-radius:12px;font-size:15px;font-weight:600}.acts .do:hover{background:var(--line)}.acts .do.bad{color:#ff3b5c}
.strip{display:flex;align-items:center;gap:8px;padding:8px 14px;background:var(--panel);border-top:1px solid var(--line);font-size:13px;color:var(--muted);flex:none}
.strip span{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.strip b{color:var(--text)}
.lightbox{position:absolute;inset:0;background:rgba(0,0,0,.92);z-index:6;display:grid;place-items:center;cursor:zoom-out}.lightbox img{max-width:96%;max-height:92%;border-radius:12px}
`;

const ICON = {
  gear: `<svg viewBox="0 0 24 24"><path d="M12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7m7.4-2.5a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 0 0-1.7-1L15 2.5h-4l-.4 2.4a7.4 7.4 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1c.5.4 1.1.7 1.7 1l.4 2.4h4l.4-2.4c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.5z"/></svg>`,
  close: `<svg viewBox="0 0 24 24"><path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>`,
  back: `<svg viewBox="0 0 24 24"><path d="M20 11H7.8l5.6-5.6L12 4l-8 8 8 8 1.4-1.4L7.8 13H20z"/></svg>`,
  send: `<svg viewBox="0 0 24 24"><path d="M2 21 23 12 2 3v7l15 2-15 2z"/></svg>`,
  mic: `<svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3m5.3-3a5.3 5.3 0 0 1-10.6 0H5a7 7 0 0 0 6 6.9V21h2v-3.1a7 7 0 0 0 6-6.9z"/></svg>`,
  plus: `<svg viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z"/></svg>`,
  search: `<svg viewBox="0 0 24 24"><path d="M9.5 3a6.5 6.5 0 0 1 5.2 10.4l5.4 5.4-1.4 1.4-5.4-5.4A6.5 6.5 0 1 1 9.5 3m0 2a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9"/></svg>`,
  cam: `<svg viewBox="0 0 24 24"><path d="M4 4h3l2-2h6l2 2h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2m8 3a5 5 0 1 0 0 10 5 5 0 0 0 0-10m0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6"/></svg>`,
};

// ---------- the chat itself (the panel, and the window the bubble opens) ----------
class HusChatView extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.msgs = []; this.people = []; this.me = null; this.prefs = {}; this.toHouse = false; this.text = "";
    this.sheet = null; this.rec = null; this.playing = null; this.ready = false;
    this.reads = {}; this.member = true; this.replyTo = null; this.editing = null; this.pending = null;
  }
  set hass(h) { this._hass = h; this.toggleAttribute("dark", !!h?.themes?.darkMode); if (this.isConnected && !this._unsub) this.subscribe(); else if (this.ready) this.paintTop(); }
  get hass() { return this.closable ? (haHass() || this._hass) : (this._hass || haHass()); }  // the bubble's window follows the page's
  get t() { return tr(this.hass); }
  connectedCallback() {
    if (!this.shadowRoot.innerHTML) this.skeleton();
    if (this.hass && !this._unsub) this.subscribe();
    // Open and in front: no phone notification meanwhile (told again every minute, and when it changes).
    this._vis = () => this.presence();
    document.addEventListener("visibilitychange", this._vis);
    this._beat = setInterval(() => this.presence(), 60000);
  }
  disconnectedCallback() {
    if (this._unsub) { this._unsub.then((u) => u()).catch(() => {}); this._unsub = null; }
    document.removeEventListener("visibilitychange", this._vis); clearInterval(this._beat);
    this.presence(false);
  }
  presence(force) {
    const open = force ?? this.visible();
    if (open === this._open && !open) return;
    this._open = open;
    this.hass?.connection?.sendMessagePromise({ type: "hus_chat/presence", open }).catch(() => {});
  }

  subscribe() {
    const h = this.hass;
    if (!h?.connection) return;
    this._unsub = h.connection.subscribeMessage((e) => this.onEvent(e), { type: "hus_chat/subscribe" });
    this._unsub.catch(() => { this._unsub = null; });
  }
  onEvent(e) {
    if (e.type === "init") {
      Object.assign(this, { msgs: e.messages, people: e.people, me: e.me, prefs: e.prefs, phones: e.phones || [], rules: e.rules || {}, agents: e.agents || null,
        reads: e.reads || {}, member: e.member !== false, pinned: e.pinned || null, speak: e.speak || null, ready: true });
      this.paintTop(); this.paintList(true); this.presence();
    } else if (e.type === "message") {
      this.msgs.push(e.message); this.paintList(this.nearBottom() || e.message.from === this.me?.id);
    } else if (e.type === "update") {
      const i = this.msgs.findIndex((m) => m.id === e.message.id);
      if (i >= 0) this.msgs[i] = e.message;
      this.paintList(false);
    } else if (e.type === "delete") {
      this.msgs = this.msgs.filter((m) => m.id !== e.message.id); this.paintList(false);
    } else if (e.type === "clear") {
      this.msgs = []; this.paintList(true);
    } else if (e.type === "pin") {
      this.pinned = e.message.id; this.paintPin(); return;
    } else if (e.type === "read") {
      this.reads[e.message.who] = e.message.t; this.paintSeen(); return;
    }
    this.markRead();
  }
  visible() { return this.isConnected && this.offsetParent !== null && document.visibilityState === "visible"; }
  markRead() {
    const last = this.msgs[this.msgs.length - 1];
    if (this.visible() && !this._open) this.presence();
    if (last && this.visible() && last.t > (this._readT || 0)) { this._readT = last.t; this.hass?.connection.sendMessagePromise({ type: "hus_chat/read", t: last.t }).catch(() => {}); }
  }
  nearBottom() { const l = this.$(".list"); return !l || l.scrollHeight - l.scrollTop - l.clientHeight < 120; }
  $(s) { return this.shadowRoot.querySelector(s); }

  skeleton() {
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <div class="top"></div><div class="list" role="log" aria-live="polite"></div><div class="bar"></div>`;
    this.shadowRoot.addEventListener("click", (e) => this.click(e));
    this.paintBar();
  }
  avatar(sender, name, gap = false, cls = "") {
    if (gap) return `<div class="av gap"></div>`;
    if (sender === "house") return `<div class="av house ${cls}">${LOGO("a" + Math.random().toString(36).slice(2, 7))}</div>`;
    const p = this.people.find((x) => x.id === sender);
    const pic = p?.picture, idx = Math.abs([...String(sender)].reduce((a, c) => a + c.charCodeAt(0), 0)) % COLORS.length;
    return `<div class="av ${cls}" title="${esc(name || "")}" style="${pic ? `background-image:url('${esc(pic)}')` : `background:${COLORS[idx]}`}">${pic ? "" : esc((name || "?").slice(0, 1).toUpperCase())}</div>`;
  }
  paintTop() {
    const t = this.t, top = this.$(".top");
    if (!top) return;
    const h = this.hass, people = this.people.map((p) => ({ ...p, home: h?.states?.[p.id] ? h.states[p.id].state === "home" : p.home }));
    const home = people.filter((p) => p.home).map((p) => p.name.split(" ")[0]);
    const sub = home.length ? (home.length === 1 ? t.homeOne : t.home).replace("{names}", home.length > 2 ? `${home.slice(0, -1).join(", ")} & ${home.at(-1)}` : home.join(home.length === 2 ? " & " : "")) : t.nobody;
    if (this.searching && !this.sheet) {  // search: the top becomes a search field
      top.innerHTML = `<button class="ib" data-a="unsearch" aria-label="${t.back}">${ICON.back}</button><input class="srch" type="search" placeholder="${esc(t.search)}" value="${esc(this.q || "")}">`;
      const i = top.querySelector("input");
      i.addEventListener("input", () => { this.q = i.value; this.paintList(true); });
      setTimeout(() => i.focus(), 30);
      this.paintPin();
      return;
    }
    top.innerHTML = `${this.sheet ? `<button class="ib" data-a="unsheet" aria-label="${t.back}">${ICON.back}</button>` : ""}
      <div class="logo">${LOGO("t")}</div><div class="tt"><b>${this.sheet ? ({ help: t.help, poll: t.pollT, shop: t.shopT }[this.sheet] || t.settings) : t.family}</b>${this.sheet ? "" : `<span class="${home.length ? "" : "away"}">● ${esc(sub)}</span>`}</div>
      ${this.sheet ? "" : `<div class="faces">${people.slice(0, 5).map((p) => this.avatar(p.id, p.name, false, p.home ? "" : "out")).join("")}</div>
      <button class="ib" data-a="search" aria-label="${t.search}">${ICON.search}</button><button class="ib" data-a="settings" aria-label="${t.settings}">${ICON.gear}</button>`}
      ${this.closable ? `<button class="ib" data-a="close" aria-label="${t.close}">${ICON.close}</button>` : ""}`;
    this.paintPin();
  }
  paintPin() {  // the pinned message under the top - tap it to find it
    this.$(".pinbar")?.remove();
    const m = !this.sheet && this.pinned && this.msgs.find((x) => x.id === this.pinned);
    if (!m) return;
    const el = document.createElement("div"); el.className = "pinbar"; el.dataset.a = "gopin";
    el.innerHTML = `<span><b>📌</b>${esc(m.name || "")}: ${esc(m.text || m.title || "")}</span>`;
    this.$(".top").after(el);
  }
  day(ts) {
    const d = new Date(ts * 1000), now = new Date(), t = this.t;
    const same = (a, b) => a.toDateString() === b.toDateString();
    if (same(d, now)) return t.today;
    if (same(d, new Date(now - 864e5))) return t.yesterday;
    if (same(d, new Date(+now + 864e5))) return t.tomorrow;
    return d.toLocaleDateString(this.hass?.language || undefined, { weekday: "long", day: "numeric", month: "long" });
  }
  hm(ts) { return new Date(ts * 1000).toLocaleTimeString(this.hass?.language || undefined, { hour: "2-digit", minute: "2-digit" }); }
  wave(id) { let s = [...id].reduce((a, c) => a + c.charCodeAt(0), 7); return Array.from({ length: 24 }, () => { s = (s * 9301 + 49297) % 233280; return `<i style="height:${30 + (s / 233280) * 70}%"></i>`; }).join(""); }
  item(m, prev, next) {
    const t = this.t, me = m.from === this.me?.id, house = m.from === "house";
    const firstOfGroup = !prev || prev.from !== m.from || m.t - prev.t > 300 || prev.kind === "house";
    const lastOfGroup = !next || next.from !== m.from || next.t - m.t > 300 || m.kind === "house";
    const who = !me && firstOfGroup ? `<div class="who">${esc(house ? t.house : m.name)}</div>` : "";
    let body = "";
    if (m.kind === "house") {
      const bang = m.urgent ? `<span class="urgent">!</span>` : "";
      body = `<div class="card${m.urgent && !m.taken ? " hot" : ""}">${m.title ? `<div class="h">${bang}${esc(m.title)}</div>` : ""}${m.text ? `<div class="${m.title ? "s" : "h"}">${m.title ? "" : bang}${esc(m.text)}</div>` : ""}
        ${m.image ? `<img class="pic" style="margin-top:8px" src="${media(m.image)}" data-a="zoom" loading="lazy" alt="">` : ""}
        ${m.take && !m.taken ? `<div class="chips"><button class="chip go" data-a="take" data-id="${esc(m.id)}">${t.take}</button></div>` : ""}</div>
        ${m.taken ? `<div class="done">${t.took.replace("{name}", m.taken.by === this.me?.id ? t.you : esc(m.taken.name || "?"))}</div>` : ""}`;
    } else {
      if (m.image) body += `<img class="pic" src="${media(m.image)}" data-a="zoom" loading="lazy" alt="${t.picture}">`;
      if (m.audio) body += `<div class="audio" data-audio="${esc(m.audio)}"><button class="play" data-a="play" data-src="${esc(m.audio)}" aria-label="${t.voice}">▶</button><div class="wave">${this.wave(m.id)}</div><span class="dur">0:00</span></div>`;
      if (m.poll) {
        const total = m.poll.reduce((a, o) => a + o.votes.length, 0);
        body += `<div class="b poll"><div class="q">📊 ${esc(m.text)}</div>${m.poll.map((o, i) => `<button class="${o.votes.includes(this.me?.id) ? "mine" : ""}" data-a="vote" data-id="${esc(m.id)}" data-o="${i}">
          <i style="width:${total ? Math.round(o.votes.length / total * 100) : 0}%"></i><span><b style="font-weight:600">${esc(o.t)}</b><em style="font-style:normal">${o.votes.length || ""}</em></span></button>`).join("")}
          <small>${total === 1 ? t.vote1 : t.votes.replace("{n}", total)}${total ? " · " + esc(m.poll.flatMap((o) => o.votes).map((v) => this.people.find((p) => p.id === v)?.name.split(" ")[0] || "").filter(Boolean).join(", ")) : ""}</small></div>`;
      } else if (m.text) body += `<div class="b${house ? " house" : ""}">${m.reply ? `<div class="quote">${esc(m.reply.name)}: ${esc(m.reply.text)}</div>` : ""}${m.kind === "to_house" ? `<span class="lbl">🏠 ${t.toHouse}</span>` : ""}${esc(m.text)}${m.edited ? `<span class="ed">(${t.edited})</span>` : ""}${m.note ? `<span class="note">ⓘ ${esc(m.note)}</span>` : ""}</div>`;
    }
    if (m.shop) body += `<span class="tag">${t.onShop}: ${esc(m.shop.join(", "))}</span>`;
    if (m.remind) body += `<span class="tag">${esc(t.remindAt.replace("{when}", `${this.day(m.remind).toLowerCase()} ${this.hm(m.remind)}`))}</span>`;
    const rx = Object.entries(m.reactions || {});
    if (rx.length) body += `<div class="reacts">${rx.map(([e, who]) => `<button class="${who.includes(this.me?.id) ? "mine" : ""}" data-a="react" data-id="${esc(m.id)}" data-e="${esc(e)}">${e} ${who.length}</button>`).join("")}</div>`;
    const fresh = this._seen && !this._seen.has(m.id);
    return `${who}<div class="row${me ? " me" : ""}${fresh ? " new" : ""}">${me ? "" : this.avatar(m.from, m.name, !lastOfGroup)}<div class="col" data-a="msg" data-id="${esc(m.id)}">${body}${lastOfGroup ? `<div class="time">${this.hm(m.t)}</div>` : ""}</div></div>`;
  }
  paintList(scroll) {
    const t = this.t, list = this.$(".list");
    if (!list || this.sheet) return;
    if (!this.msgs.length) {
      list.innerHTML = this.member ? `<div class="empty"><div class="logo">${LOGO("e")}</div><b>${t.empty}</b>${t.emptyH}</div>`
        : `<div class="empty"><div class="logo">${LOGO("e")}</div>${t.notMember}</div>`;
      return;
    }
    let html = "", lastDay = "";
    const q = this.searching && (this.q || "").trim().toLowerCase();
    const shown = q ? this.msgs.filter((m) => `${m.text || ""} ${m.title || ""} ${m.name || ""}`.toLowerCase().includes(q)) : this.msgs;
    if (q && !shown.length) { list.innerHTML = `<div class="empty">${t.searchNone}</div>`; return; }
    shown.forEach((m, i) => {
      const d = this.day(m.t);
      if (d !== lastDay) { html += `<div class="day">${esc(d)}</div>`; lastDay = d; }
      html += this.item(m, shown[i - 1], shown[i + 1]);
    });
    const keep = list.scrollTop;
    list.innerHTML = html + `<div class="seen"></div>`;
    this.paintSeen();
    this._seen = new Set(this.msgs.map((m) => m.id));  // only messages that arrive later slide in
    list.scrollTop = scroll ? list.scrollHeight : keep;
    list.querySelectorAll("img.pic").forEach((img) => img.addEventListener("load", () => { if (scroll) list.scrollTop = list.scrollHeight; }, { once: true }));
  }
  paintSeen() {  // under your last message: who has read it
    const el = this.$(".seen"), mine = [...this.msgs].reverse().find((m) => m.from === this.me?.id);
    if (!el) return;
    const names = mine ? this.people.filter((p) => p.id !== this.me?.id && (this.reads[p.id] || 0) >= mine.t).map((p) => p.name.split(" ")[0]) : [];
    const last = this.msgs[this.msgs.length - 1];
    el.textContent = names.length && last?.id === mine?.id ? this.t.seen.replace("{names}", names.join(", ")) : "";
  }
  paintStrip() {  // replying to, or editing, a message - above the field
    this.$(".strip")?.remove();
    const t = this.t, m = this.replyTo || this.editing;
    if (!m) return;
    const el = document.createElement("div"); el.className = "strip";
    el.innerHTML = `<span>${this.editing ? `<b>${t.editing}</b>` : `<b>${esc(t.replyTo.replace("{name}", m.name || ""))}</b> · ${esc(m.text || m.title || "")}`}</span>
      <button class="ib" data-a="unstrip" aria-label="${t.cancel}" style="width:30px;height:30px">${ICON.close}</button>`;
    this.$(".bar").before(el);
  }
  actions(id) {  // a tap on a message: react, reply, edit, delete
    const t = this.t, m = this.msgs.find((x) => x.id === id);
    if (!m || this.sheet) return;
    const mine = m.from === this.me?.id;
    const el = document.createElement("div"); el.className = "acts";
    el.innerHTML = `<div class="box"><div class="emo">${["👍", "❤️", "😂", "😮", "😢", "🙏"].map((e) => `<button data-a="react" data-id="${esc(id)}" data-e="${e}">${e}</button>`).join("")}</div>
      ${m.kind === "chat" || m.kind === "house" ? `<button class="do" data-a="reply" data-id="${esc(id)}">↩︎ ${t.reply}</button>` : ""}
      <button class="do" data-a="pin" data-id="${this.pinned === id ? "" : esc(id)}">📌 ${this.pinned === id ? t.unpin : t.pin}</button>
      ${mine && m.kind === "chat" && m.text && !m.poll ? `<button class="do" data-a="edit" data-id="${esc(id)}">✎ ${t.edit}</button>` : ""}
      ${mine || this.me?.admin ? `<button class="do bad" data-a="del" data-id="${esc(id)}">🗑 ${t.del}</button>` : ""}</div>`;
    el.addEventListener("click", (e) => { if (e.target === el) el.remove(); });
    this.shadowRoot.appendChild(el);
  }
  paintBar() {
    const t = this.t, bar = this.$(".bar");
    if (!bar) return;
    if (this.listening) {
      bar.innerHTML = `<button class="round cam" data-a="lcancel" aria-label="${t.cancel}">${ICON.close}</button>
        <div class="recbar"><span class="dot"></span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.listen}</span></div>
        <button class="round go" data-a="lsend" aria-label="Send">${ICON.send}</button>`;
      return;
    }
    if (this.rec) {
      bar.innerHTML = `<button class="round cam" data-a="reccancel" aria-label="${t.cancel}">${ICON.close}</button>
        <div class="recbar"><span class="dot"></span><span>${t.rec}</span><span class="rectime" style="margin-left:auto">0:00</span></div>
        <button class="round go" data-a="recsend" aria-label="${t.voice}">${ICON.send}</button>`;
      return;
    }
    bar.innerHTML = `<button class="round cam" data-a="plus" aria-label="${t.more}">${ICON.plus}</button>
      <div class="field"><textarea rows="1" placeholder="${esc(this.toHouse ? t.ask : t.write)}" aria-label="${esc(t.write)}">${esc(this.text)}</textarea>
        ${window.HUS_CHAT_APP ? "" : `<button class="hb ${this.toHouse ? "on" : ""}" data-a="house" title="${esc(t.toHouse)}"><span class="mini">${LOGO("h")}</span>${this.toHouse ? t.toHouse : ""}</button>`}</div>
      ${this.text.trim() ? `<button class="round go" data-a="send" aria-label="Send">${ICON.send}</button>` : `<button class="round go" data-a="rec" aria-label="${t.voice}">${ICON.mic}</button>`}`;
    const ta = bar.querySelector("textarea");
    const grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(120, ta.scrollHeight) + "px"; };
    ta.addEventListener("input", () => {
      const had = !!this.text.trim(); this.text = ta.value; grow();
      if (had !== !!this.text.trim()) { const pos = ta.selectionStart; this.paintBar(); const n = this.$("textarea"); n.focus(); n.setSelectionRange(pos, pos); }
    });
    ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !("ontouchstart" in window)) { e.preventDefault(); this.send(); } });
    grow();
  }
  error(text) {
    const el = document.createElement("div"); el.className = "err"; el.textContent = text;
    this.shadowRoot.appendChild(el); setTimeout(() => el.remove(), 3500);
  }
  async upload(blob, type) {
    const fd = new FormData();
    fd.append("file", new File([blob], type.startsWith("image") ? "picture.jpg" : "voice", { type }));
    const r = await this.hass.fetchWithAuth("/api/hus_chat/upload", { method: "POST", body: fd });
    if (!r.ok) throw new Error(String(r.status));
    return r.json();
  }
  async send(media = null) {
    const text = this.text.trim();
    if (!text && !media) return;
    if (this.editing && !media) {
      const id = this.editing.id;
      this.editing = null; this.text = ""; this.paintStrip(); this.paintBar();
      try { await this.hass.connection.sendMessagePromise({ type: "hus_chat/edit", message: id, text }); }
      catch (e) { this.error(this.t.failed); }
      return;
    }
    const toHouse = this.toHouse && !media;
    // The same id when sent again after a failed try: if the first one did arrive, it isn't there twice.
    const cid = this.pending?.text === text && !media ? this.pending.cid : Math.random().toString(36).slice(2) + Date.now().toString(36);
    const reply = this.replyTo?.id;
    this.text = ""; this.replyTo = null; this.paintStrip(); this.paintBar(); this.$("textarea")?.focus();
    try {
      await this.hass.connection.sendMessagePromise({ type: "hus_chat/send", text, ...(media ? { media } : {}), to_house: toHouse, cid, ...(reply ? { reply } : {}) });
      this.pending = null;
    } catch (e) { this.pending = { text, cid }; this.text = text; this.paintBar(); this.error(this.t.failed); }
  }
  async sendPicture(file) {
    if (!file) return;
    try { const blob = await shrink(file); const m = await this.upload(blob || file, "image/jpeg"); await this.send({ name: m.name, kind: "image" }); }
    catch (e) { this.error(this.t.failed); }
  }
  async startRec() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm"].find((x) => window.MediaRecorder?.isTypeSupported?.(x)) || "";
      const r = new MediaRecorder(stream, type ? { mimeType: type } : {}), chunks = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      this.rec = { r, stream, chunks, start: Date.now(), type: (r.mimeType || type || "audio/webm").split(";")[0] };
      r.start();
      this.rec.timer = setInterval(() => {
        const s = Math.floor((Date.now() - this.rec.start) / 1000), el = this.$(".rectime");
        if (el) el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
        if (s >= 120) this.stopRec(true);
      }, 250);
      this.paintBar();
    } catch (e) { this.error(this.t.micNo); }
  }
  // "To the house" by voice, like Home Assistant's own voice commands: Assist's speech-to-text listens, stops by itself
  // when you stop talking, and the words are sent to the house - no voice message to send yourself.
  async listen() {
    const t = this.t, conn = this.hass?.connection;
    if (!conn || this.listening) return;
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } }); }
    catch (e) { this.error(t.micNo); return; }
    const L = this.listening = { stream, handler: null, queue: [], pending: [], ended: false, done: false, start: Date.now() };
    this.paintBar();
    const send = (pcm) => {  // the handler id first, then 16-bit samples at 16 kHz
      const d = new Uint8Array(1 + pcm.byteLength); d[0] = L.handler; d.set(new Uint8Array(pcm.buffer), 1); conn.socket.send(d);
    };
    L.end = () => { if (L.ended) return; L.ended = true; if (L.handler != null) conn.socket.send(new Uint8Array([L.handler])); };
    L.finish = (text, err) => {
      if (L.done) return;
      L.done = true; this.stopListen(true);
      if (err) { this.error(err); return; }
      if (!text?.trim() || !L.voice) { this.error(t.heard); return; }  // nobody spoke: never send what the engine made up from silence
      this.text = text.trim(); this.toHouse = true; this.send();
    };
    try {
      const ctx = L.ctx = new (window.AudioContext || window.webkitAudioContext)();
      const code = `class P extends AudioWorkletProcessor{process(i){const c=i[0]&&i[0][0];if(c)this.port.postMessage(c.slice(0));return true}}registerProcessor("hc-mic",P)`;
      await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([code], { type: "application/javascript" })));
      const node = L.node = new AudioWorkletNode(ctx, "hc-mic");
      ctx.createMediaStreamSource(stream).connect(node);
      const k = ctx.sampleRate / 16000;
      node.port.onmessage = (e) => {
        if (L.ended) return;
        // Our own ears too: was anyone talking, and has it been quiet for 1.2 s since (in case Assist doesn't say so)
        let sum = 0; for (const v of e.data) sum += v * v;
        const loud = Math.sqrt(sum / e.data.length) > 0.02, now = Date.now();
        if (loud) { L.voice = true; L.quietFrom = 0; } else if (L.voice) { L.quietFrom = L.quietFrom || now; if (now - L.quietFrom > 1200) L.end(); }
        else if (now - L.start > 6000) L.end();  // nothing said in 6 s
        L.pending.push(...e.data);
        const n = Math.floor(L.pending.length / k);
        if (n < 1024) return;  // about 64 ms at a time
        const pcm = new Int16Array(n);
        for (let i = 0; i < n; i++) { const v = L.pending[Math.floor(i * k)]; pcm[i] = Math.max(-1, Math.min(1, v)) * 0x7fff; }
        L.pending = L.pending.slice(Math.floor(n * k));
        if (L.handler == null) L.queue.push(pcm); else send(pcm);
      };
      L.unsub = await conn.subscribeMessage((ev) => {
        if (ev.type === "run-start") { L.handler = ev.data?.runner_data?.stt_binary_handler_id; L.queue.forEach(send); L.queue = []; }
        else if (ev.type === "stt-vad-end") L.end();
        else if (ev.type === "stt-end") L.finish(ev.data?.stt_output?.text);
        else if (ev.type === "error") L.finish("", ev.data?.code === "stt-no-text-recognized" ? t.heard : t.noStt);
        else if (ev.type === "run-end") L.finish("", L.done ? null : t.heard);
      }, { type: "assist_pipeline/run", start_stage: "stt", end_stage: "stt", input: { sample_rate: 16000 }, timeout: 60 });
      L.timer = setTimeout(() => L.end(), 15000);  // at most 15 s
    } catch (e) { L.finish("", t.noStt); }
  }
  endListen() { this.listening?.end(); }
  stopListen(keep) {
    const L = this.listening;
    if (!L) return;
    this.listening = null; L.ended = true; clearTimeout(L.timer);
    try { L.node?.disconnect(); L.ctx?.close(); } catch (e) { /* closed */ }
    L.stream.getTracks().forEach((x) => x.stop());
    if (typeof L.unsub === "function") L.unsub().catch?.(() => {});
    if (!keep) L.done = true;
    this.paintBar();
  }
  stopRec(send) {
    const rec = this.rec;
    if (!rec) return;
    clearInterval(rec.timer); this.rec = null; this.paintBar();
    rec.r.onstop = async () => {
      rec.stream.getTracks().forEach((x) => x.stop());
      if (!send || !rec.chunks.length) return;
      try { const m = await this.upload(new Blob(rec.chunks, { type: rec.type }), rec.type); await this.send({ name: m.name, kind: "audio" }); }
      catch (e) { this.error(this.t.failed); }
    };
    rec.r.stop();
  }
  play(btn) {
    const box = btn.closest(".audio"), src = media(btn.dataset.src);
    if (this.playing?.box === box) { const a = this.playing.a; if (a.paused) { a.play(); btn.textContent = "⏸"; } else { a.pause(); btn.textContent = "▶"; } return; }
    if (this.playing) { this.playing.a.pause(); this.playing.btn.textContent = "▶"; }
    const a = new Audio(src), bars = [...box.querySelectorAll(".wave i")], dur = box.querySelector(".dur");
    this.playing = { a, box, btn };
    a.ontimeupdate = () => {
      const p = a.duration ? a.currentTime / a.duration : 0;
      bars.forEach((b, i) => b.classList.toggle("on", i / bars.length < p));
      const s = Math.floor(a.currentTime); dur.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    };
    a.onended = () => { btn.textContent = "▶"; bars.forEach((b) => b.classList.remove("on")); this.playing = null; };
    a.play().then(() => { btn.textContent = "⏸"; }).catch(() => this.error(this.t.failed));
  }
  async setPref(k, v) {
    this.prefs = { ...this.prefs, [k]: v };
    try { const r = await this.hass.connection.sendMessagePromise({ type: "hus_chat/prefs", [k]: v }); this.phones = r.phones || this.phones; delete r.phones; this.prefs = r; } catch (e) { /* kept locally */ }
    window.dispatchEvent(new CustomEvent("hus-chat-prefs", { detail: this.prefs }));
    if (this.sheet === "settings") this.paintSheet();
  }
  paintSheet() {
    this.shadowRoot.querySelector(".sheet")?.remove();
    this.toggleAttribute("sheet", !!this.sheet);
    this.paintTop();
    if (!this.sheet) { this.paintList(true); return; }
    const t = this.t, p = this.prefs, el = document.createElement("div");
    el.className = "sheet";
    el.style.top = this.$(".top").offsetHeight + "px";
    if (this.sheet === "poll") {
      const n = this.pollN || 2;
      el.innerHTML = `<div class="sbody frm"><div class="set"><b>${t.pollQ}</b><input data-pq maxlength="200" placeholder="${esc(t.pollQ)}">
        ${Array.from({ length: n }, (_, i) => `<input data-po maxlength="80" placeholder="${esc(t.pollOpt.replace("{n}", i + 1))}">`).join("")}
        ${n < 6 ? `<button class="chip" style="margin-top:10px" data-a="polladd">${t.pollAdd}</button>` : ""}</div>
        <button class="chip go" style="width:100%;padding:13px;font-size:15px" data-a="pollsend">${t.pollSend}</button></div>`;
      const keep = this._pollVals || {};
      el.querySelector("[data-pq]").value = keep.q || "";
      el.querySelectorAll("[data-po]").forEach((x, i) => { x.value = (keep.o || [])[i] || ""; });
      setTimeout(() => el.querySelector("[data-pq]")?.focus(), 50);
    } else if (this.sheet === "shop") {
      const S = this.shop;
      el.innerHTML = `<div class="sbody frm"><div class="set">${!S ? "…" : !S.entity ? `<small style="color:var(--muted)">${t.shopNone}</small>`
        : `<div style="display:flex;gap:8px"><input data-shopadd maxlength="60" placeholder="${esc(t.shopAdd)}" style="margin-top:0"><button class="chip go" data-a="shopadd">+</button></div>
        <div style="margin-top:10px">${S.items.length ? S.items.map((i) => `<div class="shopi"><button data-a="shopdone" data-u="${esc(i.uid)}" aria-label="✓"></button><span>${esc(i.summary)}</span></div>`).join("")
          : `<div class="shopi" style="color:var(--muted)">${t.shopEmpty}</div>`}</div>`}</div></div>`;
      el.querySelector("[data-shopadd]")?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); this.shopDo({ add: e.target.value }); } });
    } else if (this.sheet === "help") {
      el.innerHTML = `<div class="sbody" style="padding:0"></div>`;
      this._sup = this._sup || document.createElement(defineSupport("hus_chat"));
      this._sup.hass = this.hass;
      el.firstChild.appendChild(this._sup);
      this.addSuggest(el.firstChild, "list");
    } else {
      const sw = (k) => `<button class="sw ${p[k] ? "on" : ""}" data-a="pref" data-k="${k}" role="switch" aria-checked="${!!p[k]}"></button>`;
      el.innerHTML = `<div class="sbody">
        ${this.rulesCard()}
        ${this.agentCard()}
        <div class="set"><div class="srow"><div><b>${t.quiet}</b><small>${t.quietH}</small></div>${sw("quiet")}</div>
          ${p.quiet ? `<div class="times"><label>${t.from}<input type="time" value="${esc(p.quiet_from)}" data-time="quiet_from"></label><label>${t.to}<input type="time" value="${esc(p.quiet_to)}" data-time="quiet_to"></label></div>` : ""}</div>
        <div class="set"><div class="srow"><div><b>${t.push}</b><small>${t.pushH}</small></div>${sw("push")}</div></div>
        ${window.HUS_CHAT_APP ? "" : `<div class="set"><div class="srow"><div><b>${t.bubble}</b><small>${t.bubbleH}</small></div>${sw("bubble")}</div></div>`}
        ${(this.phones || []).length ? `<div class="set"><b>${t.myPhones}</b><small style="display:block;color:var(--muted);font-size:12.5px;margin:2px 0 6px">${t.myPhonesH}</small>
          ${this.phones.map((x) => `<div class="srow" style="margin-top:10px"><div>📱 ${esc(x.name)}${x.stale ? `<small>${t.stale}</small>` : ""}</div>
            <button class="sw ${x.on ? "on" : ""}" data-a="phone" data-svc="${esc(x.svc)}" role="switch" aria-checked="${x.on}" aria-label="${esc(x.name)}"></button></div>`).join("")}</div>` : ""}
        ${this.me?.admin ? this.speakCard() : ""}
        ${this.me?.admin ? this.appsCard() : ""}
        ${this.me?.admin ? `<button class="link" data-a="help">${t.help}</button>
          <div class="set" style="margin-top:12px"><div class="srow"><div><b>${t.clear}</b><small>${t.clearH}</small></div>
            <button class="chip" style="color:#ff3b5c" data-a="clearall">🗑</button></div></div>` : ""}</div>`;
      el.querySelectorAll("[data-time]").forEach((i) => i.addEventListener("change", () => this.setPref(i.dataset.time, i.value)));
      el.querySelector("[data-agent]")?.addEventListener("change", (e) => this.setAgent(e.target.value));
      el.querySelector("[data-speaker]")?.addEventListener("change", (e) => this.setSpeak({ player: e.target.value || null }));
      if (this.me?.admin) this.addSuggest(el.firstChild, "card");  // only admins can install
      if (this.me?.admin) {  // the update card on top of the settings, when it's time
        this._upd = this._upd || document.createElement(defineUpdate("hus_chat"));
        this._upd.hass = this.hass;
        el.firstChild.prepend(this._upd);
      }
    }
    this.shadowRoot.appendChild(el);
  }
  addSuggest(box, mode) {  // the suggestions can never stop the settings from showing
    try { box.appendChild(this.suggest(mode)); }
    catch (e) {
      console.error("Hus-chat: suggestions", e);
      box.insertAdjacentHTML("beforeend", `<small style="display:block;opacity:.5;font-size:11px;margin:10px 4px">suggest: ${esc(e?.message || e)}</small>`);
    }
  }
  suggest(mode) {  // "Fits your home too" / "From the same developer" - kept between draws
    const k = `_sg_${mode}`;
    if (!this[k]) { this[k] = document.createElement(defineSuggest("hus_chat")); this[k].setAttribute("mode", mode); }
    this[k].hass = this.hass;
    return this[k];
  }
  speakCard() {  // the house's messages read aloud on a speaker
    const t = this.t, S = this.speak;
    if (!S) return "";
    const inp = "width:100%;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--bubble);color:var(--text);font:inherit;font-size:14px;margin-top:10px";
    return `<div class="set"><div class="srow"><div><b>${t.speakT}</b><small>${S.tts ? t.speakH : t.speakNoTts}</small></div>
      ${S.tts ? `<button class="sw ${S.on ? "on" : ""}" data-a="speakon" role="switch" aria-checked="${!!S.on}"></button>` : ""}</div>
      ${S.tts && S.on ? `<select data-speaker style="${inp}"><option value="">${esc(t.speakPick)}</option>${S.players.map((p) => `<option value="${esc(p.id)}" ${p.id === S.player ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>
        ${S.player ? `<button class="chip" style="margin-top:10px" data-a="speaktest">🔊 ${t.speakTest}</button>` : ""}` : ""}</div>`;
  }
  async setSpeak(change) {
    try { this.speak = await this.hass.connection.sendMessagePromise({ type: "hus_chat/speak", ...change }); } catch (e) { this.error(this.t.failed); }
    if (this.sheet === "settings") this.paintSheet();
  }
  async shopDo(change) {
    try { this.shop = await this.hass.connection.sendMessagePromise({ type: "hus_chat/extra", what: "shop", ...(change || {}) }); }
    catch (e) { this.error(this.t.failed); this.shop = this.shop || { entity: null, items: [] }; }
    if (this.sheet === "shop") this.paintSheet();
  }
  extra(what, data) { return this.hass.connection.sendMessagePromise({ type: "hus_chat/extra", what, ...(data || {}) }); }
  plusMenu() {  // the + in the message field: picture, poll, on my way home, shopping list
    const t = this.t, el = document.createElement("div"); el.className = "acts";
    el.innerHTML = `<div class="box"><label class="do" style="cursor:pointer">📷 ${t.picture}<input type="file" accept="image/*" hidden data-file></label>
      <button class="do" data-a="poll">📊 ${t.pollT}</button><button class="do" data-a="onway">🚗 ${t.onway}</button><button class="do" data-a="shop">🛒 ${t.shopT}</button></div>`;
    el.addEventListener("click", (e) => { if (e.target === el) el.remove(); });
    el.querySelector("[data-file]").addEventListener("change", (e) => { el.remove(); this.sendPicture(e.target.files[0]); });
    this.shadowRoot.appendChild(el);
  }
  appsCard() {  // links that open the chat as an app without a login - made by an admin
    const t = this.t, L = this.links;
    if (!L) { this.loadLinks(); return `<div class="set"><b>${t.apps}</b></div>`; }
    const persons = this.people.filter((p) => p.id.startsWith("person."));
    const rows = L.links.map((x) => `<div style="padding:12px 0;border-top:1px solid var(--line)"><div class="srow"><div><b>📱 ${esc(x.name)}</b>
        <small>${esc(persons.find((p) => p.id === x.person)?.name || "")}${x.devices ? `${x.person ? " · " : ""}${esc(t.appDevices.replace("{n}", x.devices))}` : ""}</small></div></div>
      <div class="chips" style="margin-top:8px"><button class="chip" data-a="appcopy" data-u="${esc(x.url)}">${t.appCopy}</button>
        ${navigator.share ? `<button class="chip" data-a="appshare" data-u="${esc(x.url)}" data-n="${esc(x.name)}">${t.appShare}</button>` : ""}
        <button class="chip" style="color:#ff3b5c" data-a="appdel" data-id="${esc(x.id)}" data-n="${esc(x.name)}">${t.appDel}</button></div></div>`).join("");
    const inp = "padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--bubble);color:var(--text);font:inherit;font-size:14px";
    return `<div class="set"><b>${t.apps}</b><small style="display:block;color:var(--muted);font-size:12.5px;margin:2px 0 6px">${t.appsH}</small>
      ${L.outside ? "" : `<small style="display:block;color:#e8890c;font-size:12.5px;margin-bottom:6px">${t.appsLocal}</small>`}${rows}
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)">
        <input data-appname placeholder="${esc(t.appName)}" maxlength="40" style="${inp};flex:1;min-width:120px">
        <select data-appwho style="${inp};flex:1;min-width:120px"><option value="">${esc(t.appAlone)}</option>${persons.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select>
        <button class="chip go" data-a="appnew">${t.appNew}</button></div></div>`;
  }
  async loadLinks(change) {
    try { this.links = await this.hass.connection.sendMessagePromise({ type: "hus_chat/links", ...(change || {}) }); }
    catch (e) { if (change) this.error(this.t.failed); this.links = this.links || { links: [], outside: true }; }
    if (this.sheet === "settings") this.paintSheet();
  }
  agentCard() {  // which AI answers "to the house" - any conversation agent set up in Home Assistant
    const t = this.t, A = this.agents;
    if (!A) return "";
    const name = (id) => A.list.find((a) => a.id === id)?.name || (id === "conversation.home_assistant" || !id ? t.builtin : id);
    const opts = [`<option value="" ${!A.chosen ? "selected" : ""}>${esc(t.asAssist)} (${esc(name(A.assist))})</option>`,
      ...A.list.map((a) => `<option value="${esc(a.id)}" ${a.id === A.chosen ? "selected" : ""}>${esc(a.name)}</option>`)].join("");
    return `<div class="set"><b>${t.agentT}</b><small style="display:block;color:var(--muted);font-size:12.5px;margin:2px 0 10px">${t.agentH}</small>
      ${this.me?.admin ? `<select data-agent style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--bubble);color:var(--text);font:inherit;font-size:14px">${opts}</select>`
        : `<div style="font-weight:600">${esc(A.chosen ? name(A.chosen) : `${t.asAssist} (${name(A.assist)})`)}</div>`}</div>`;
  }
  async setAgent(agent) {
    try { this.agents = await this.hass.connection.sendMessagePromise({ type: "hus_chat/agent", agent: agent || null }); }
    catch (e) { this.error(this.t.failed); }
  }
  rulesCard() {
    const t = this.t, R = this.rules || {}, admin = this.me?.admin, muted = new Set(this.prefs.muted || []);
    const rows = Object.keys(t.topics).filter((k) => R[k]).map((k) => {
      const r = R[k], list = Array.isArray(r.to) ? new Set(r.to) : null;
      const chip = (val, label, on) => `<button class="chip ${on ? "go" : ""}" data-a="ruleto" data-k="${k}" data-v="${esc(val)}" ${admin ? "" : "disabled"}>${esc(label)}</button>`;
      const who = `<div class="chips" style="margin-top:8px">${chip("home", t.toHome, r.to === "home")}${chip("all", t.toAll, r.to === "all")}
        ${this.people.map((p) => chip(p.id, p.name.split(" ")[0], !!list?.has(p.id))).join("")}</div>`;
      const mine = k === "safety" ? `<small style="color:var(--ok)">${t.always}</small>`
        : `<button class="sw ${muted.has(k) ? "" : "on"}" data-a="mute" data-k="${k}" role="switch" aria-checked="${!muted.has(k)}" aria-label="${esc(t.forMe)}"></button>`;
      return `<div style="padding:12px 0;border-top:1px solid var(--line)"><div class="srow"><div><b>${t.topics[k]}</b><small>${t.topicsH[k]}</small></div>
        ${admin ? `<button class="sw ${r.on ? "on" : ""}" data-a="ruleon" data-k="${k}" role="switch" aria-checked="${r.on}" aria-label="${esc(t.on)}"></button>` : ""}</div>
        ${r.on ? `${who}<div class="srow" style="margin-top:8px"><div><small>${t.forMe}</small></div>${mine}</div>` : ""}</div>`;
    }).join("");
    return `<div class="set"><b>${t.rules}</b><small style="display:block;color:var(--muted);font-size:12.5px;margin:2px 0 6px">${admin ? t.rulesH : t.rulesKid}</small>${rows}</div>`;
  }
  async setRule(k, change) {
    this.rules = { ...this.rules, [k]: { ...this.rules[k], ...change } };
    this.paintSheet();
    try { this.rules = await this.hass.connection.sendMessagePromise({ type: "hus_chat/rules", rules: { [k]: change } }); } catch (e) { this.error(this.t.failed); }
    this.paintSheet();
  }
  click(e) {
    const b = e.target.closest("[data-a]");
    if (!b) return;
    const a = b.dataset.a;
    if (a === "send") this.send();
    else if (a === "msg") { if (!e.target.closest("button,img,.audio")) this.actions(b.dataset.id); }
    else if (a === "react") { this.shadowRoot.querySelector(".acts")?.remove(); this.hass.connection.sendMessagePromise({ type: "hus_chat/react", message: b.dataset.id, emoji: b.dataset.e }).catch(() => {}); }
    else if (a === "reply" || a === "edit") {
      this.shadowRoot.querySelector(".acts")?.remove();
      const m = this.msgs.find((x) => x.id === b.dataset.id);
      if (a === "reply") { this.replyTo = m; this.editing = null; } else { this.editing = m; this.replyTo = null; this.text = m.text; this.toHouse = false; }
      this.paintBar(); this.paintStrip(); this.$("textarea")?.focus();
    }
    else if (a === "del") {
      this.shadowRoot.querySelector(".acts")?.remove();
      if (confirm(this.t.delAsk)) this.hass.connection.sendMessagePromise({ type: "hus_chat/delete", message: b.dataset.id }).catch(() => this.error(this.t.failed));
    }
    else if (a === "unstrip") { if (this.editing) this.text = ""; this.replyTo = null; this.editing = null; this.paintStrip(); this.paintBar(); }
    else if (a === "plus") this.plusMenu();
    else if (a === "poll") { this.shadowRoot.querySelector(".acts")?.remove(); this.pollN = 2; this._pollVals = null; this.sheet = "poll"; this.paintSheet(); }
    else if (a === "polladd") {
      this._pollVals = { q: this.$("[data-pq]").value, o: [...this.shadowRoot.querySelectorAll("[data-po]")].map((x) => x.value) };
      this.pollN = Math.min(6, (this.pollN || 2) + 1); this.paintSheet();
    }
    else if (a === "pollsend") {
      const question = this.$("[data-pq]").value.trim(), options = [...this.shadowRoot.querySelectorAll("[data-po]")].map((x) => x.value.trim()).filter(Boolean);
      if (!question || options.length < 2) return;
      this.extra("poll", { question, options }).then(() => { this.sheet = null; this.paintSheet(); }).catch(() => this.error(this.t.failed));
    }
    else if (a === "vote") this.extra("vote", { message: b.dataset.id, option: Number(b.dataset.o) }).catch(() => this.error(this.t.failed));
    else if (a === "onway") { this.shadowRoot.querySelector(".acts")?.remove(); this.extra("onway").catch(() => this.error(this.t.failed)); }
    else if (a === "shop") { this.shadowRoot.querySelector(".acts")?.remove(); this.sheet = "shop"; this.paintSheet(); this.shopDo(); }
    else if (a === "shopadd") { const i = this.$("[data-shopadd]"); if (i?.value.trim()) this.shopDo({ add: i.value }); }
    else if (a === "shopdone") { b.style.background = "#7c5cff"; this.shopDo({ done: b.dataset.u }); }
    else if (a === "pin") { this.shadowRoot.querySelector(".acts")?.remove(); this.extra("pin", { message: b.dataset.id || null }).catch(() => this.error(this.t.failed)); }
    else if (a === "gopin") {
      if (this.searching) { this.searching = false; this.q = ""; this.paintTop(); this.paintList(false); }
      const row = this.shadowRoot.querySelector(`[data-a="msg"][data-id="${CSS.escape(this.pinned)}"]`);
      row?.scrollIntoView({ block: "center", behavior: "smooth" });
      row?.animate([{ background: "#7c5cff33" }, { background: "transparent" }], { duration: 1600 });
    }
    else if (a === "search") { this.searching = true; this.q = ""; this.paintTop(); }
    else if (a === "unsearch") { this.searching = false; this.q = ""; this.paintTop(); this.paintList(true); }
    else if (a === "speakon") this.setSpeak({ on: !this.speak.on });
    else if (a === "speaktest") this.setSpeak({ test: true });
    else if (a === "appnew") {
      const name = this.$("[data-appname]")?.value.trim(), person = this.$("[data-appwho]")?.value || null;
      const who = person && this.people.find((p) => p.id === person);
      if (name || who) this.loadLinks({ create: { name: name || who.name, person } });
    }
    else if (a === "appcopy") { navigator.clipboard?.writeText(b.dataset.u).then(() => { b.textContent = this.t.appCopied; }).catch(() => prompt("", b.dataset.u)); }
    else if (a === "appshare") navigator.share({ title: b.dataset.n, url: b.dataset.u }).catch(() => {});
    else if (a === "appdel") { if (confirm(this.t.appDelAsk.replace("{n}", b.dataset.n))) this.loadLinks({ delete: b.dataset.id }); }
    else if (a === "clearall") {
      if (confirm(this.t.clearAsk)) this.hass.connection.sendMessagePromise({ type: "hus_chat/clear" }).catch(() => this.error(this.t.failed));
    }
    else if (a === "house") { this.toHouse = !this.toHouse; this.paintBar(); this.$("textarea")?.focus(); }
    else if (a === "take") this.hass.connection.sendMessagePromise({ type: "hus_chat/take", message: b.dataset.id }).catch(() => {});
    else if (a === "rec") { if (this.toHouse) this.listen(); else this.startRec(); }
    else if (a === "lsend") this.endListen();
    else if (a === "lcancel") this.stopListen();
    else if (a === "recsend") this.stopRec(true);
    else if (a === "reccancel") this.stopRec(false);
    else if (a === "play") this.play(b);
    else if (a === "zoom") {
      const lb = document.createElement("div"); lb.className = "lightbox"; lb.innerHTML = `<img src="${b.src}" alt="">`;
      lb.onclick = () => lb.remove(); this.shadowRoot.appendChild(lb);
    } else if (a === "settings") { this.sheet = "settings"; this.paintSheet(); }
    else if (a === "help") { this.sheet = "help"; this.paintSheet(); }
    else if (a === "unsheet") { this.sheet = this.sheet === "help" ? "settings" : null; this.paintSheet(); }
    else if (a === "pref") this.setPref(b.dataset.k, !this.prefs[b.dataset.k]);
    else if (a === "ruleon") this.setRule(b.dataset.k, { on: !this.rules[b.dataset.k].on });
    else if (a === "ruleto") {
      const k = b.dataset.k, v = b.dataset.v, cur = this.rules[k].to;
      if (v === "home" || v === "all") this.setRule(k, { to: v });
      else {
        const set = new Set(Array.isArray(cur) ? cur : []);
        set.has(v) ? set.delete(v) : set.add(v);
        this.setRule(k, { to: set.size ? [...set] : "home" });
      }
    } else if (a === "mute") {
      const m = new Set(this.prefs.muted || []);
      m.has(b.dataset.k) ? m.delete(b.dataset.k) : m.add(b.dataset.k);
      this.setPref("muted", [...m]);
    }
    else if (a === "phone") {
      const off = new Set(this.prefs.phones_off || []);
      off.has(b.dataset.svc) ? off.delete(b.dataset.svc) : off.add(b.dataset.svc);
      this.setPref("phones_off", [...off]);
    }
    else if (a === "close") this.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
  }
}
if (!customElements.get("hus-chat-view")) customElements.define("hus-chat-view", HusChatView);

// ---------- the sidebar panel ----------
class HusChatPanel extends HTMLElement {
  set hass(h) {
    this._hass = h;
    if (!this.view) {
      // The whole screen: Home Assistant doesn't give a panel a fixed height, and without one the settings had no room.
      this.style.cssText = "display:flex;flex-direction:column;height:100vh;height:100dvh;";
      const bar = document.createElement("div");
      bar.style.cssText = "height:var(--header-height,56px);display:flex;align-items:center;background:var(--app-header-background-color,var(--primary-color));color:var(--app-header-text-color,#fff);flex:none";
      bar.innerHTML = `<ha-menu-button></ha-menu-button><div style="font-size:20px;margin-left:4px">${tr(h).family}</div>`;
      this.appendChild(bar);
      this.view = document.createElement("hus-chat-view");
      this.view.style.flex = "1";
      this.appendChild(this.view);
    }
    const menu = this.querySelector("ha-menu-button");
    if (menu) { menu.hass = h; menu.narrow = this._narrow; }
    this.view.hass = h;
  }
  set narrow(n) { this._narrow = n; const menu = this.querySelector("ha-menu-button"); if (menu) menu.narrow = n; }
}
if (!customElements.get("hus-chat-panel")) customElements.define("hus-chat-panel", HusChatPanel);

// ---------- the bubble on every page ----------
const BUBBLE_CSS = `
:host{all:initial}
.head{position:fixed;width:60px;height:60px;border-radius:50%;z-index:2147483000;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none;
  box-shadow:0 10px 28px rgba(60,30,120,.45),0 0 0 3px rgba(255,255,255,.95);transition:left .25s ease,top .25s ease,transform .2s ease,opacity .2s;overflow:visible}
.head.drag{transition:none;cursor:grabbing;transform:scale(1.08)}
.head .face{width:100%;height:100%;border-radius:50%;overflow:hidden}.head svg{width:100%;height:100%;display:block}
.badge{position:absolute;top:-4px;right:-4px;min-width:23px;height:23px;padding:0 6px;border-radius:12px;background:#ff3b5c;color:#fff;font:700 12px/23px -apple-system,Roboto,sans-serif;text-align:center;border:2px solid #fff;box-sizing:border-box}
.bump{animation:bump .5s ease}@keyframes bump{30%{transform:scale(1.18)}60%{transform:scale(.95)}}
.x{position:fixed;left:50%;bottom:40px;width:64px;height:64px;margin-left:-32px;border-radius:50%;background:rgba(20,20,30,.75);color:#fff;display:grid;place-items:center;
  font:28px/1 sans-serif;z-index:2147482999;opacity:0;transform:scale(.6);transition:all .18s;pointer-events:none;backdrop-filter:blur(6px)}
.x.show{opacity:1;transform:scale(1)}.x.hot{background:#ff3b5c;transform:scale(1.2)}
.tab{position:fixed;width:16px;height:52px;z-index:2147483000;cursor:pointer;background:linear-gradient(160deg,#ff6b8a,#7c5cff);box-shadow:0 6px 18px rgba(60,30,120,.4);
  animation:peek .3s ease;-webkit-tap-highlight-color:transparent}
.tab.right{right:0;border-radius:14px 0 0 14px}.tab.left{left:0;border-radius:0 14px 14px 0}
.tab::after{content:"";position:absolute;top:50%;width:4px;height:20px;margin-top:-10px;border-radius:2px;background:rgba(255,255,255,.75)}
.tab.right::after{left:5px}.tab.left::after{right:5px}
.tab::before{content:"";position:absolute;inset:-12px -6px}
@keyframes peek{from{transform:scaleX(0)}to{transform:none}}
.toast{position:fixed;z-index:2147483000;max-width:min(280px,70vw);padding:10px 14px;border-radius:18px;background:#fff;color:#151829;box-shadow:0 10px 30px rgba(0,0,0,.25);
  font:14px/1.35 -apple-system,"Inter",Roboto,sans-serif;animation:pop .25s ease;cursor:pointer}
.toast b{display:block;font-size:12.5px;color:#7c5cff;margin-bottom:2px}
@keyframes pop{from{opacity:0;transform:translateY(8px) scale(.96)}to{opacity:1;transform:none}}
.win{position:fixed;z-index:2147483001;border-radius:26px;overflow:hidden;box-shadow:0 24px 70px rgba(10,10,40,.45);animation:open .22s cubic-bezier(.2,.9,.3,1.2);display:flex}
.win hus-chat-view{flex:1;height:100%}
@keyframes open{from{opacity:0;transform:translateY(20px) scale(.97)}to{opacity:1;transform:none}}
.win.phone{left:0;right:0;bottom:0;top:6vh;border-radius:26px 26px 0 0}
.win.desk{width:390px;height:min(640px,calc(100vh - 120px));bottom:96px}
`;

class Bubble {
  constructor() {
    this.unread = 0; this.open = false; this.prefs = { bubble: true }; this.me = null;
    try { this.pos = JSON.parse(localStorage.getItem("hus-chat-pos") || "null"); this.dismissed = Number(localStorage.getItem("hus-chat-closed") || 0); } catch (e) { this.pos = null; this.dismissed = 0; }
  }
  async start() {
    for (let i = 0; i < 120 && !haHass()?.connection; i++) await new Promise((r) => setTimeout(r, 500));
    const h = haHass();
    if (!h?.connection) return;
    this.host = document.createElement("div");
    this.host.id = "hus-chat-bubble";
    document.body.appendChild(this.host);
    this.root = this.host.attachShadow({ mode: "open" });
    this.root.innerHTML = `<style>${BUBBLE_CSS}</style><div class="x">✕</div><div class="tab" role="button" tabindex="0" aria-label="${tr(h).family}" hidden></div>
      <div class="head" role="button" tabindex="0" aria-label="${tr(h).family}"><div class="face">${LOGO("b")}</div><span class="badge" hidden></span></div>`;
    this.head = this.root.querySelector(".head"); this.x = this.root.querySelector(".x"); this.tab = this.root.querySelector(".tab");
    this.tab.addEventListener("click", () => this.unclose());  // closed: a small tab at the edge brings the bubble back
    this.tab.addEventListener("keydown", (e) => { if (e.key === "Enter") this.unclose(); });
    this.place(); requestAnimationFrame(() => this.place()); this.drag();
    window.addEventListener("resize", () => this.place());
    window.addEventListener("hus-chat-prefs", (e) => { this.prefs = e.detail; this.show(); });
    window.addEventListener("location-changed", () => setTimeout(() => this.show(), 50));
    window.addEventListener("popstate", () => this.show());
    this.head.addEventListener("keydown", (e) => { if (e.key === "Enter") this.toggle(); });
    h.connection.subscribeMessage((e) => this.onEvent(e), { type: "hus_chat/subscribe" }).catch(() => this.host.remove());
    this.show();
  }
  onEvent(e) {
    if (e.type === "init") { this.me = e.me; this.prefs = e.prefs; this.unread = e.unread; this.lastT = e.messages.at(-1)?.t || 0; }
    else if (e.type === "message") {
      const m = e.message;
      this.unread = this.open ? 0 : e.unread;
      if (m.from !== this.me?.id && !this.open) {
        if (m.t > this.dismissed) { this.dismissed = 0; try { localStorage.removeItem("hus-chat-closed"); } catch (x) { /* private */ } }
        this.show(); this.toast(m);
        this.head.classList.remove("bump"); void this.head.offsetWidth; this.head.classList.add("bump");
      }
    }
    this.badge();
  }
  onPanel() { return location.pathname.startsWith("/hus-chat"); }
  show() {
    const panel = this.onPanel();
    if (this.wasPanel && !panel) {  // read in the panel: the count is fetched again
      haHass()?.connection.sendMessagePromise({ type: "hus_chat/read", t: 0 }).then((r) => { this.unread = r.unread; this.badge(); }).catch(() => {});
    }
    this.wasPanel = panel;
    const off = this.onPanel() || this.prefs.bubble === false, closed = !!this.dismissed && !this.open;
    this.head.style.display = off || closed ? "none" : "";
    this.tab.hidden = off || !closed;
    if (this.onPanel() && this.open) this.toggle(false);
  }
  badge() {
    const b = this.root.querySelector(".badge");
    b.hidden = !this.unread || this.open; b.textContent = this.unread > 9 ? "9+" : String(this.unread);
  }
  place() {
    const w = innerWidth || document.documentElement.clientWidth, h = innerHeight || document.documentElement.clientHeight, p = this.pos || { side: "right", y: h - 170 };
    const y = Math.max(70, Math.min(h - 80, p.y));
    this.head.style.left = (p.side === "left" ? 14 : w - 74) + "px"; this.head.style.top = y + "px";
    this.tab.className = `tab ${p.side === "left" ? "left" : "right"}`; this.tab.style.top = y + 4 + "px";
  }
  drag() {
    let sx, sy, ox, oy, moved = false, down = false;
    this.head.addEventListener("pointerdown", (e) => {
      down = true; moved = false; sx = e.clientX; sy = e.clientY; ox = this.head.offsetLeft; oy = this.head.offsetTop;
      this.head.setPointerCapture(e.pointerId);
    });
    this.head.addEventListener("pointermove", (e) => {
      if (!down) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (!moved && Math.hypot(dx, dy) < 7) return;
      if (!moved) { moved = true; this.head.classList.add("drag"); this.x.classList.add("show"); this.root.querySelector(".toast")?.remove(); }
      this.head.style.left = ox + dx + "px"; this.head.style.top = oy + dy + "px";
      this.x.classList.toggle("hot", this.overX(e));
    });
    this.head.addEventListener("pointerup", (e) => {
      if (!down) return;
      down = false; this.head.classList.remove("drag"); this.x.classList.remove("show", "hot");
      if (!moved) {  // one tap opens, two quick taps tuck it away (as dropping it on ✕)
        if (this.tapT) { clearTimeout(this.tapT); this.tapT = null; this.close(); return; }
        this.tapT = setTimeout(() => { this.tapT = null; this.toggle(); }, 260);
        return;
      }
      if (this.overX(e)) { this.close(); return; }
      this.pos = { side: e.clientX < innerWidth / 2 ? "left" : "right", y: this.head.offsetTop };
      try { localStorage.setItem("hus-chat-pos", JSON.stringify(this.pos)); } catch (x) { /* private */ }
      this.place();
    });
  }
  overX(e) { const r = this.x.getBoundingClientRect(); return Math.hypot(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2)) < 70; }
  unclose() {
    this.dismissed = 0;
    try { localStorage.removeItem("hus-chat-closed"); } catch (x) { /* private */ }
    this.show();
  }
  close() {  // tucked away as a tab at the edge until it's tapped or somebody writes
    this.dismissed = Date.now() / 1000;
    try { localStorage.setItem("hus-chat-closed", String(this.dismissed)); } catch (x) { /* private */ }
    this.toggle(false); this.show();
  }
  toast(m) {
    this.root.querySelector(".toast")?.remove();
    const t = tr(haHass()), el = document.createElement("div"), r = this.head.getBoundingClientRect(), right = r.left > innerWidth / 2;
    el.className = "toast";
    el.innerHTML = `<b>${esc(m.from === "house" ? t.house : m.name)}</b>${esc((m.title ? m.title + " – " : "") + (m.text || (m.image ? "📷 " + t.picture : "🎤 " + t.voice))).slice(0, 140)}`;
    el.style.top = Math.max(10, r.top - 4) + "px";
    el.style[right ? "right" : "left"] = (right ? innerWidth - r.left + 10 : r.right + 10) + "px";
    el.onclick = () => { el.remove(); this.toggle(true); };
    this.root.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }
  toggle(force) {
    this.open = force ?? !this.open;
    this.root.querySelector(".toast")?.remove();
    if (this.open) {
      this.dismissed = 0; this.unread = 0; this.show();
      const phone = innerWidth < 600;
      this.win = document.createElement("div");
      this.win.className = `win ${phone ? "phone" : "desk"}`;
      if (!phone) { const left = this.head.offsetLeft < innerWidth / 2; this.win.style[left ? "left" : "right"] = "20px"; }
      const v = document.createElement("hus-chat-view");
      v.closable = true;
      v.addEventListener("close", () => this.toggle(false));
      v.hass = haHass();
      this.win.appendChild(v);
      this.root.appendChild(this.win);
      if (phone) this.head.style.display = "none";
    } else {
      this.win?.remove(); this.win = null; this.show();
    }
    this.badge();
  }
}

// Started once per page, not on the panel itself (it has the chat), and not inside other frames.
if (!window.__husChatBubble && window.top === window && !window.HUS_CHAT_APP) {  // not in the app from a link
  window.__husChatBubble = new Bubble();
  window.__husChatBubble.start();
}

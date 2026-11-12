const fs=require('node:fs'),assert=require('node:assert/strict');
const js=fs.readFileSync('static/app.js','utf8');
const css=fs.readFileSync('static/style.css','utf8');
const python=fs.readFileSync('academy.py','utf8');
const html=fs.readFileSync('static/index.html','utf8');
for(const t of [
 'function academySendChat(){',
 'function academyClearChat(){',
 'function academyReadChat(){',
 "academyChatMessages=academyReadChat()",
 "api('/academy/ask','POST',{question,tone:academyTone,history})",
 "api('/academy/diagnose','POST',{})",
 "academyChatLog",
 'academy-chat-log',
 'academyChatPending',
 'academyClearChat();setRole(null,null);'
])assert(js.includes(t),'missing chat surface '+t);
assert(js.includes("e.key==='Enter'&&!e.shiftKey"),'Enter/Shift+Enter missing');
assert(!js.includes("querySelector('.academy-chat-log').innerHTML"),'unsafe innerHTML');
assert(css.includes('.academy-message-user'),'user message style missing');
assert(css.includes('.academy-message-assistant'),'assistant message style missing');
assert(html.includes('data-view="academy"'),'original nav missing');
assert(python.includes("@router.post('/diagnose')"));
assert(python.includes("messages+=cleaned[-12:]"),'bounded real context missing');
assert(python.includes("model_diagnostic"),'safe model diagnosis missing');
console.log('V35 conversational chat DOM, keyboard, local session and diagnostics tests passed');

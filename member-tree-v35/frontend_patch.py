"""V35 transform Academy's single-turn answer panel into a real conversation UI.

JS insertion is additive and anchored to V34's own dedicated Academy block.
No member/finance HTML, JS functions or database schemas are changed.
"""
from pathlib import Path
p=Path('member-tree/static/app.js')
s=p.read_text(encoding='utf-8')
anchor="let academyLoaded=false,academyDocs=[],academyStats=null,academySearch='',"
if s.count(anchor)!=1:raise RuntimeError('Academy state anchor changed')
chat_state=r"""
// Session-scoped private dialogue; shared viewer credentials never share chat logs.
const ACADEMY_CHAT_STORAGE='academy-v35-chat-session';
function academyReadChat(){
 try{
  const saved=JSON.parse(sessionStorage.getItem(ACADEMY_CHAT_STORAGE)||'[]');
  if(!Array.isArray(saved))return [];
  return saved.filter(m=>m&&['user','assistant'].includes(m.role)&&
      typeof m.content==='string').slice(-36).map(m=>({
       role:m.role,content:m.content.slice(0,7000),mode:String(m.mode||''),
       sources:Array.isArray(m.sources)?m.sources.slice(0,6):[],
       diagnostic:m.diagnostic&&typeof m.diagnostic==='object'?m.diagnostic:null
      }));
 }catch(e){return []}
}
let academyChatMessages=academyReadChat(),academyChatPending=false,
    academyDiag=null,academyDiagBusy=false;
function academySaveChat(){
 try{sessionStorage.setItem(ACADEMY_CHAT_STORAGE,JSON.stringify(academyChatMessages.slice(-36)))}
 catch(e){/* Storage disabled; active dialogue still works */ }
}
function academyClearChat(){
 if(academyChatPending)return;
 academyChatMessages=[];academyQuestion='';academyDiag=null;
 try{sessionStorage.removeItem(ACADEMY_CHAT_STORAGE)}catch(e){}
 if(view==='academy')render();
}
async function academySendChat(){
 const question=String(academyQuestion||'').trim();
 if(!question||academyChatPending){if(!question)showToast('请先输入内容');return}
 const history=academyChatMessages.filter(m=>m.mode==='ai'||m.role==='user')
    .slice(-12).map(m=>({role:m.role,content:m.content.slice(0,1500)}));
 academyChatMessages.push({role:'user',content:question,mode:'user'});
 academyQuestion='';academyChatPending=true;academySaveChat();
 if(view==='academy')render();
 let answer;
 try{answer=await api('/academy/ask','POST',{question,tone:academyTone,history})}
 catch(e){answer={mode:'model_error',answer:'请求失败：'+e.message,sources:[]}}
 academyChatMessages.push({
  role:'assistant',content:String(answer.answer||'本次未获得回复').slice(0,7500),
  mode:answer.mode||'model_error',
  sources:Array.isArray(answer.sources)?answer.sources.slice(0,6):[],
  diagnostic:answer.diagnostic||null
 });
 academyChatPending=false;academySaveChat();
 if(view==='academy')render();
}
async function academyDiagnose(){
 if(role!=='admin'||academyDiagBusy)return;
 academyDiagBusy=true;academyDiag=null;if(view==='academy')render();
 try{academyDiag=await api('/academy/diagnose','POST',{})}
 catch(e){academyDiag={ok:false,diagnostic:{title:'连接检查失败：'+e.message}}}
 academyDiagBusy=false;if(view==='academy')render();
}
"""
s=s.replace(anchor,chat_state+"\n"+anchor,1)

a=s.index(" const tutor=mk('section','academy-card');")
b=s.index(" root.append(tutor);\n",a)+len(" root.append(tutor);\n")
chat_ui=r"""
 const tutor=mk('section','academy-card academy-chat');
 const top=mk('div','academy-chat-heading');
 const heading=mk('div','');
 heading.append(mk('h3','','✦ AI话术导师 · 连续对话'));
 heading.append(mk('p','academy-muted','优先参考已审核的《群洗》和磐石9—10课程。每次回答可展开查看来源。'));
 const actions=mk('div','academy-chat-actions');
 const clear=mk('button','button academy-chat-secondary','＋ 新对话');
 clear.type='button';clear.disabled=academyChatPending;clear.onclick=academyClearChat;
 actions.append(clear);
 if(role==='admin'){
  const diagnose=mk('button','button academy-chat-secondary',
      academyDiagBusy?'检测中…':'检测AI连接');
  diagnose.type='button';diagnose.disabled=academyDiagBusy;
  diagnose.onclick=academyDiagnose;actions.append(diagnose);
 }
 top.append(heading,actions);tutor.append(top);
 const status=mk('div','academy-chat-status');
 const keyMsg=academyStats?.connected?'● 模型密钥已配置 · 连接需实际检测':'○ 模型密钥未配置 · 可查知识库';
 status.append(mk('span',academyStats?.connected?'academy-status-configured':'academy-status-offline',keyMsg));
 status.append(mk('span','academy-muted','本次聊天仅保存在当前浏览器会话，退出后清除。'));
 tutor.append(status);
 if(academyDiag){
  const dx=academyDiag.diagnostic||{};
  const alert=mk('div',academyDiag.ok?'academy-diagnose-good':'academy-diagnose-bad');
  alert.append(mk('b','',dx.title||'连接状态未知'));
  if(dx.instruction)alert.append(mk('p','',dx.instruction));
  tutor.append(alert);
 }
 const log=mk('div','academy-chat-log');log.id='academyChatLog';
 log.setAttribute('role','log');log.setAttribute('aria-live','polite');
 if(!academyChatMessages.length){
  const welcome=mk('div','academy-chat-welcome');
  welcome.append(mk('div','academy-welcome-avatar','✦'));
  welcome.append(mk('h4','','你好，我是磐石AI话术导师'));
  welcome.append(mk('p','','你可以直接聊天、问课程问题，或者让我按照核心讲课风格写新人培训、团队讲话和沟通话术。'));
  const suggestions=mk('div','academy-suggest');
  for(const t of ['在吗，老师？','帮我写一段新人学习动员讲话','如何向新人讲解团队合作？','帮我改一段客户沟通话术']){
   const chip=mk('button','academy-chip',t);
   chip.type='button';chip.onclick=()=>{academyQuestion=t;render();el('academyChatQuestion')?.focus()};
   suggestions.append(chip);
  }
  welcome.append(suggestions);log.append(welcome);
 }
 for(const [i,m] of academyChatMessages.entries()){
  const outer=mk('div','academy-message '+(m.role==='user'?'academy-message-user':'academy-message-assistant'));
  const avatar=mk('div','academy-message-avatar',m.role==='user'?'我':'AI');
  const body=mk('div','academy-message-body');
  const label=mk('small','academy-message-label',m.role==='user'?'我的提问':
    m.mode==='ai'?'AI话术导师':m.mode==='model_error'?'AI连接提示':'知识库课程检索');
  body.append(label);
  body.append(mk('div','academy-message-text',m.content));
  if(m.role==='assistant'){
    const utilities=mk('div','academy-message-utils');
    const copy=mk('button','academy-msg-copy','复制回答');
    copy.type='button';copy.onclick=async()=>{
      try{await navigator.clipboard.writeText(m.content);showToast('回答已复制')}
      catch(e){showToast('无法访问剪贴板，请手动选中文字复制')}
    };
    utilities.append(copy);
    if(m.mode==='model_error'&&m.diagnostic){
      const issue=mk('p','academy-ai-alert',m.diagnostic.title||'模型连接未成功');
      utilities.append(issue);
      if(m.diagnostic.instruction)utilities.append(mk('p','academy-muted',m.diagnostic.instruction));
    }
    if(m.mode!=='ai'&&m.mode!=='model_error')
      utilities.append(mk('span','academy-muted','当前非AI生成；仅供参考'));
    if(m.sources?.length){
      const refs=mk('details','academy-chat-references');
      refs.append(mk('summary','','查看课程依据（'+m.sources.length+'）'));
      for(const [idx,ref] of m.sources.entries()){
        const item=mk('div','academy-chat-ref');
        item.append(mk('b','',String(idx+1)+'. '+ref.title+(ref.priority>=100?' · 核心课程':'')));
        item.append(mk('small','academy-muted','来源：'+ref.source));
        item.append(mk('p','',ref.excerpt));
        refs.append(item);
      }
      utilities.append(refs);
    }
    body.append(utilities);
  }
  outer.append(avatar,body);log.append(outer);
 }
 if(academyChatPending){
  const pending=mk('div','academy-message academy-message-assistant');
  pending.append(mk('div','academy-message-avatar','AI'),mk('p','academy-chat-thinking','正在参考知识库，组织回复…'));
  log.append(pending);
 }
 tutor.append(log);
 const composer=mk('div','academy-chat-composer');
 const input=mk('textarea','academy-chat-textarea');
 input.id='academyChatQuestion';input.rows=3;
 input.value=academyQuestion;input.placeholder='给AI导师发消息…（Enter发送，Shift+Enter换行）';
 input.maxLength=1500;input.oninput=e=>{academyQuestion=e.target.value};
 input.onkeydown=e=>{
    if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){
      e.preventDefault();academySendChat();
    }
 };
 const composeTools=mk('div','academy-compose-tools');
 const style=mk('select','academy-input academy-chat-style');
 for(const value of ['亲切自然','领导讲话','课程讲解','简短有力','新人训练']){
  const opt=mk('option','',value);opt.value=value;style.append(opt);
 }
 style.value=academyTone;style.onchange=e=>academyTone=e.target.value;
 const send=mk('button','button primary academy-chat-send',academyChatPending?'发送中…':'发送 ↗');
 send.type='button';send.disabled=academyChatPending;
 send.onclick=academySendChat;
 composeTools.append(style,send);composer.append(input,composeTools);tutor.append(composer);
 root.append(tutor);
 requestAnimationFrame(()=>{const box=el('academyChatLog');if(box)box.scrollTop=box.scrollHeight});
"""
s=s[:a]+chat_ui+s[b:]
# Important: don't retain chat beyond the login session after explicit logout.
needle="async function logout(){try{await api('/logout','POST',{})}catch(e){}setRole(null,null);members=[];selectedLogin('viewer')}"
if s.count(needle)!=1:raise RuntimeError('logout anchor not found')
s=s.replace(needle,
"async function logout(){try{await api('/logout','POST',{})}catch(e){}academyClearChat();setRole(null,null);members=[];selectedLogin('viewer')}",1)
p.write_text(s,encoding='utf-8')

css=Path('member-tree/static/style.css')
styles=css.read_text(encoding='utf-8')
styles += r"""
/* V35 conversation UI. Entirely inside the Academy tab. */
.academy-chat{padding:0!important;gap:0!important;overflow:hidden;min-height:540px}
.academy-chat-heading{padding:16px 18px 10px;display:flex;align-items:start;justify-content:space-between;flex-wrap:wrap;gap:8px;border-bottom:1px solid #e4ebf3}
.academy-chat-heading h3{margin:0 0 5px}
.academy-chat-actions{display:flex;flex-wrap:wrap;gap:6px}
.academy-chat-secondary{font-size:12px!important;padding:7px 10px!important}
.academy-chat-status{padding:7px 18px;background:#f7f9fc;border-bottom:1px solid #e9eff5;display:flex;justify-content:space-between;gap:6px;flex-wrap:wrap;font-size:12px}
.academy-status-configured{color:#246a47;font-weight:700}
.academy-status-offline{color:#a25f25;font-weight:700}
.academy-diagnose-good,.academy-diagnose-bad{margin:9px 16px;padding:10px 12px;border-radius:8px;line-height:1.6;font-size:12px}
.academy-diagnose-good{background:#edf9f2;border:1px solid #b8e2c8;color:#205c36}
.academy-diagnose-bad{background:#fff6e9;border:1px solid #edcda3;color:#844b19}
.academy-diagnose-good p,.academy-diagnose-bad p{margin:4px 0 0}
.academy-chat-log{flex:1;min-height:330px;max-height:60vh;overflow-y:auto;scroll-behavior:smooth;padding:20px 16px;background:linear-gradient(180deg,#fbfdff,#f6faff);display:flex;flex-direction:column;gap:18px}
.academy-chat-welcome{align-self:center;text-align:center;max-width:580px;padding:12px 10px;color:#2b4d6e;line-height:1.8}
.academy-welcome-avatar{display:grid;place-items:center;width:48px;height:48px;background:#e3edff;color:#2661b1;border-radius:16px;font-size:29px;margin:auto}
.academy-chat-welcome h4{margin:12px 0 4px;font-size:17px}
.academy-chat-welcome p{margin:4px 0;font-size:13px}
.academy-suggest{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:14px}
.academy-chip{border:1px solid #bfd1e9;border-radius:18px;background:white;color:#2d5892;padding:7px 11px;cursor:pointer;font-size:12px}
.academy-chip:hover{background:#eaf3ff}
.academy-message{display:flex;align-items:flex-start;gap:9px;max-width:94%;font-size:14px;line-height:1.7}
.academy-message-user{align-self:flex-end;flex-direction:row-reverse}
.academy-message-assistant{align-self:flex-start}
.academy-message-avatar{flex:none;width:28px;height:28px;border-radius:9px;background:#dfeaff;color:#2764aa;display:grid;place-items:center;font-weight:700;font-size:11px}
.academy-message-user .academy-message-avatar{background:#245de0;color:white}
.academy-message-body{max-width:100%;min-width:100px;display:grid;gap:6px}
.academy-message-label{color:#73849c;font-size:11px}
.academy-message-user .academy-message-label{text-align:right}
.academy-message-text{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;border:1px solid #dfe9f4;border-radius:3px 14px 14px 14px;padding:11px 13px;box-shadow:0 2px 6px #1459a00a}
.academy-message-user .academy-message-text{background:#3265d8;color:white;border-color:#3265d8;border-radius:14px 3px 14px 14px}
.academy-message-utils{display:grid;justify-items:start;gap:7px}
.academy-msg-copy{background:none;border:0;color:#386b9d;font-size:11px;cursor:pointer;padding:3px 0}
.academy-ai-alert{color:#9e481d;font-weight:700;font-size:12px;margin:0}
.academy-chat-references{border:1px solid #d9e6f2;border-radius:8px;padding:7px 10px;background:#fff;font-size:11px;max-width:680px;min-width:200px}
.academy-chat-references summary{font-weight:700;color:#33689b;cursor:pointer}
.academy-chat-ref{display:grid;gap:5px;margin:10px 0;padding:8px;border-radius:6px;background:#f5f9fe}
.academy-chat-ref p{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font-size:12px}
.academy-chat-thinking{margin:2px 0;padding:11px;background:white;border-radius:10px;color:#536a8a}
.academy-chat-composer{padding:12px 16px 14px;background:white;border-top:1px solid #e1eaf4}
.academy-chat-textarea{display:block;width:100%;box-sizing:border-box;font:inherit;font-size:14px;resize:vertical;min-height:66px;max-height:180px;padding:11px;border:1px solid #afc5df;border-radius:10px;color:#24405c;outline-color:#3973db}
.academy-compose-tools{display:flex;justify-content:space-between;align-items:center;margin-top:8px;gap:8px}
.academy-chat-style{max-width:155px}
.academy-chat-send{padding:9px 20px!important}
@media(max-width:640px){.academy-chat-log{min-height:310px;max-height:53vh;padding:13px 9px}.academy-message{max-width:99%}.academy-chat-heading{padding:12px}.academy-chat-status{padding:9px}.academy-chat-composer{padding:9px}.academy-chat-secondary{font-size:11px!important}}
"""
css.write_text(styles,encoding='utf-8')
print('V35: multi-turn speech bubbles, draft state, session chat, copy, sources, diagnostics UI')

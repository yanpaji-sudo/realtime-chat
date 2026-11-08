"""V39 additive course-script-to-speech module.
Keeps existing course documents and member tree DB untouched.
"""
from pathlib import Path
p=Path("member-tree/academy.py")
s=p.read_text(encoding="utf-8")
assert s.count("    app.include_router(router)")==1
speech=r'''
    # All synthesized course speech is ephemeral: no lesson, personal data, voice
    # sample or MP3 is inserted into the member DB or persisted on the server.
    class SpeechIn(BaseModel):
        script: str = Field(min_length=8,max_length=1600)
        voice: str = Field(default='cedar',max_length=16)
        style: str = Field(default='lecturer',max_length=30)
        speed: float = Field(default=1.0,ge=0.8,le=1.2)

    _voice_choices={'cedar','marin','onyx','nova','coral','sage'}
    _speech_styles={
      'lecturer':'使用自然标准的中文普通话。像专业课程讲师一样沉稳、清晰、富有感染力地讲述，讲重点时稍加强调，逻辑转折时适当停顿，不添加文字之外的内容。',
      'warm':'使用自然标准的中文普通话，温暖亲切、耐心、娓娓道来，像认真帮助新成员学习的老师，节奏舒适，字词准确，不额外发挥。',
      'energetic':'使用自然标准的中文普通话，精神饱满、鼓舞人心但不过度激动，语调有层次，停顿自然，不添加文字之外的内容。',
      'calm':'使用自然标准的中文普通话，理性平和、慢条斯理，适合系统讲解制度、步骤与概念，句号停顿明显，不增删文字。'
    }
    _speech_limit={}  # Short in-process, per-session abuse guard; no DB changes.
    import threading as _speech_threading
    import time as _speech_time
    _speech_lock=_speech_threading.Lock()

    @router.post('/speech')
    def speech(req:Request, body:SpeechIn):
        require(req,'viewer',True)
        value=body.script.strip()
        if not value:
            raise HTTPException(400,'请先输入或导入课程讲稿')
        if body.voice not in _voice_choices or body.style not in _speech_styles:
            raise HTTPException(400,'请选择有效的讲师音色和语音风格')
        key=os.environ.get('OPENAI_API_KEY','').strip()
        if not key:
            raise HTTPException(503,'AI语音尚未配置 API 密钥')
        # One call per click; maximum three per authenticated browser session
        # per ten-minute interval avoids an unbounded surprise API bill.
        cookie=str(req.cookies)
        user_hash=hashlib.sha256(cookie.encode('utf8')).hexdigest()
        now=_speech_time.monotonic()
        with _speech_lock:
            _speech_limit[user_hash]=[stamp for stamp in _speech_limit.get(user_hash,[])
                                      if now-stamp<600]
            if len(_speech_limit[user_hash])>=3:
                raise HTTPException(429,'为控制语音费用，每10分钟最多生成3次；请稍后再试。')
            _speech_limit[user_hash].append(now)
            # Limit the number of retained sessions to avoid memory buildup.
            if len(_speech_limit)>900:
                _speech_limit.clear()
                _speech_limit[user_hash]=[now]
        model=os.environ.get('OPENAI_SPEECH_MODEL','gpt-4o-mini-tts').strip()
        # Non-realtime Speech API models only; never send chat model by mistake.
        if model not in {'gpt-4o-mini-tts','gpt-4o-mini-tts-2025-12-15'}:
            raise HTTPException(503,'语音模型配置错误，请管理员检查 OPENAI_SPEECH_MODEL')
        params={'model':model,
                'input':value,'voice':body.voice,
                'speed':round(body.speed,2),
                'instructions':_speech_styles[body.style],
                'response_format':'mp3'}
        req_audio=http_request.Request(
            'https://api.openai.com/v1/audio/speech',
            data=json.dumps(params,ensure_ascii=False).encode('utf8'),
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
            method='POST')
        try:
            with http_request.urlopen(req_audio,timeout=85) as response:
                mp3=response.read(6500000)
            if not mp3 or len(mp3)>=6500000:
                raise HTTPException(502,'生成的语音文件异常，请缩短讲稿后重试')
        except http_error.HTTPError as exc:
            code=''
            try:
                error=json.loads(exc.read(3000).decode('utf8','replace'))
                code=(error.get('error') or {}).get('code','')
            except (ValueError,TypeError,AttributeError):pass
            detail=model_diagnostic(exc.code,code)
            raise HTTPException(503,'语音生成失败：'+detail['title']+'。'+detail['instruction']) from None
        except (http_error.URLError, TimeoutError):
            raise HTTPException(503,'语音接口超时或网络暂时不可用，请稍后再试') from None
        # Base64 JSON allows reuse of the existing authenticated API helper,
        # including its CSRF header. Client makes an ephemeral downloadable Blob.
        return {'ok':True,'audio_b64':base64.b64encode(mp3).decode('ascii'),
                'mime':'audio/mpeg','format':'mp3','chars':len(value),
                'disclosure':'本课程语音由人工智能生成'}

'''
s=s.replace("    app.include_router(router)",speech+"    app.include_router(router)",1)
p.write_text(s,encoding="utf-8")

js_path=Path('member-tree/static/app.js')
j=js_path.read_text(encoding='utf-8')
anchor="let academyLoaded=false,academyDocs=[],academyStats=null,academySearch='',"
assert j.count(anchor)==1
state=r"""
// V39 Course voice studio; MP3 remains only in this browser session.
let academyVoiceScript='',academyVoice='cedar',academyVoiceStyle='lecturer',
    academyVoiceSpeed='1',academySpeechBusy=false,academySpeechUrl=null,
    academySpeechError='';
function academyClearSpeech(){
 if(academySpeechUrl){URL.revokeObjectURL(academySpeechUrl);academySpeechUrl=null}
 academyVoiceScript='';academySpeechBusy=false;academySpeechError='';
}
function academyUseScript(content){
 academyVoiceScript=String(content||'').trim().slice(0,1600);
 academySpeechError='';
 if(view==='academy')render();
 requestAnimationFrame(()=>{
  const input=el('academy-speech-script');
  if(input){input.scrollIntoView({behavior:'smooth',block:'center'});input.focus()}
 });
}
async function academySynthesize(){
 const script=String(academyVoiceScript||'').trim();
 if(academySpeechBusy)return;
 if(script.length<8){showToast('讲稿至少需要8个字符');return}
 if(script.length>1600){showToast('单次最多1600字，请分篇生成');return}
 academySpeechBusy=true;academySpeechError='';if(view==='academy')render();
 try{
  const result=await api('/academy/speech','POST',{
   script,voice:academyVoice,style:academyVoiceStyle,speed:Number(academyVoiceSpeed)
  });
  if(!result.ok||!result.audio_b64)throw new Error('未能收到MP3语音');
  const raw=atob(result.audio_b64),array=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++)array[i]=raw.charCodeAt(i);
  if(academySpeechUrl)URL.revokeObjectURL(academySpeechUrl);
  academySpeechUrl=URL.createObjectURL(new Blob([array],{type:'audio/mpeg'}));
  showToast('语音生成成功，可以试听并下载MP3');
 }catch(e){academySpeechError='配音失败：'+e.message}
 academySpeechBusy=false;if(view==='academy')render();
}
"""
j=j.replace(anchor,state+"\n"+anchor,1)
old="  if(m.role==='assistant'){\n    const utilities=mk('div','academy-message-utils');"
new="""  if(m.role==='assistant'){
    const utilities=mk('div','academy-message-utils');
    if(m.mode==='ai'){
      const speechCopy=mk('button','academy-msg-copy','🎙 转为课程配音稿');
      speechCopy.type='button';
      speechCopy.onclick=()=>academyUseScript(m.content);
      utilities.append(speechCopy);
    }"""
assert j.count(old)==1,'AI chat response tools anchor missing'
j=j.replace(old,new,1)
anchor=" const docs=mk('section','academy-card');"
assert j.count(anchor)==1,'Academy document anchor missing'
studio=r"""
 // No voice cloning: the reference MP3 is a speaking-style guide only.
 const speech=mk('section','academy-card academy-speech-card');
 speech.append(mk('h3','','🎙 课程语音制作室'));
 speech.append(mk('p','academy-muted',
   '先让AI按照核心课程编排话术，点击回答下方「转为课程配音稿」，也可粘贴和修改讲稿。确认最终文字后生成普通话MP3。'));
 const [scriptWrap,scriptInput]=academyInput('可编辑的课程配音稿（最多1600字）','textarea',academyVoiceScript);
 scriptInput.id='academy-speech-script';scriptInput.rows=8;scriptInput.maxLength=1600;
 scriptInput.placeholder='把准备配音的讲稿粘贴到这里，或在AI回答下方点「转为课程配音稿」…';
 scriptInput.oninput=e=>{academyVoiceScript=e.target.value};
 speech.append(scriptWrap);
 const settings=mk('div','academy-speech-settings');
 const voices=mk('label','academy-field');voices.append(mk('b','','讲师音色'));
 const voice=mk('select','academy-input');
 for(const [id,title] of [['cedar','沉稳讲师'],['marin','自然亲切'],['onyx','浑厚男声'],['nova','明亮女声'],['coral','清晰柔和'],['sage','温和讲解']]){
   const option=mk('option','',title);option.value=id;voice.append(option);
 }
 voice.value=academyVoice;voice.onchange=e=>academyVoice=e.target.value;
 voices.append(voice);settings.append(voices);
 const styles=mk('label','academy-field');styles.append(mk('b','','讲解风格'));
 const style=mk('select','academy-input');
 for(const [id,title] of [['lecturer','课堂讲师（推荐）'],['warm','耐心辅导'],['energetic','动员讲话'],['calm','制度讲解']]){
   const opt=mk('option','',title);opt.value=id;style.append(opt);
 }
 style.value=academyVoiceStyle;style.onchange=e=>academyVoiceStyle=e.target.value;
 styles.append(style);settings.append(styles);
 const speeds=mk('label','academy-field');speeds.append(mk('b','','语速'));
 const speed=mk('select','academy-input');
 for(const v of ['0.85','0.9','1','1.1','1.2']){
   const opt=mk('option','',v==='1'?'标准 1.0 倍':v+' 倍');opt.value=v;speed.append(opt);
 }
 speed.value=academyVoiceSpeed;speed.onchange=e=>academyVoiceSpeed=e.target.value;
 speeds.append(speed);settings.append(speeds);
 speech.append(settings);
 const action=mk('div','academy-speech-actions');
 const suggest=mk('button','button','让AI编排一篇课程讲稿');
 suggest.type='button';suggest.onclick=()=>{
   academyQuestion='请严格根据已审核的核心培训课程，编写一篇约1200字的完整普通话课堂讲稿，保留课程讲解风格、提出问题、举例说明、重点总结，适合转换成语音。请先让我审核文字，不增加没有来源的事实。';
   render();el('academyChatQuestion')?.focus();
 };
 action.append(suggest);
 const synth=mk('button','button primary',academySpeechBusy?'语音制作中…':'生成MP3语音');
 synth.type='button';synth.disabled=academySpeechBusy;
 synth.onclick=academySynthesize;action.append(synth);
 speech.append(action);
 if(academySpeechError)speech.append(mk('p','err',academySpeechError));
 if(academySpeechBusy)speech.append(mk('p','academy-muted','正在生成普通话语音，请不要重复点击或关闭页面。'));
 if(academySpeechUrl){
   const done=mk('div','academy-speech-result');
   done.append(mk('b','','生成完成 · 可直接试听'));
   const player=mk('audio','academy-speech-player');player.controls=true;player.src=academySpeechUrl;
   done.append(player);
   const download=mk('a','button','↓ 下载MP3课件');
   download.href=academySpeechUrl;download.download='磐石AI课程配音.mp3';
   done.append(download);speech.append(done);
 }
 speech.append(mk('p','academy-muted','音频由AI合成，并非真实讲师录音；示例MP3只参考讲课节奏，不复制原讲话者的声纹。配音按API用量计费，单次最多1600字，每10分钟最多3次。'));
 root.append(speech);
"""
j=j.replace(anchor,studio+"\n"+anchor,1)
logout="academyClearChat();setRole(null,null);"
assert j.count(logout)==1,'logout anchor missing'
j=j.replace(logout,"academyClearChat();academyClearSpeech();setRole(null,null);",1)
js_path.write_text(j,encoding='utf-8')
css_path=Path('member-tree/static/style.css')
css=css_path.read_text(encoding='utf-8')
css+="""
/* V39 dedicated course speech studio, separate from original tree UI. */
.academy-speech-card{border:1px solid #b5d4ec!important;background:linear-gradient(180deg,#fff,#fafcff)!important}
.academy-speech-settings{display:grid;grid-template-columns:repeat(3,minmax(130px,1fr));gap:12px}
.academy-speech-settings select{min-width:0}
.academy-speech-actions{display:flex;gap:9px;justify-content:flex-end;flex-wrap:wrap}
.academy-speech-result{padding:15px;display:grid;gap:12px;background:#eff8f4;border:1px solid #b5dfc6;border-radius:10px}
.academy-speech-player{display:block;width:100%;max-width:800px}
.academy-speech-result>a{justify-self:start;text-decoration:none;cursor:pointer}
@media(max-width:660px){.academy-speech-settings{grid-template-columns:1fr}.academy-speech-actions{flex-direction:column}}
"""
css_path.write_text(css,encoding='utf-8')
print('V39 integrated: AI answer to editable speech script, original lecture style presets, MP3 preview and browser download')

'use strict';
const multer=require('multer');

module.exports=function mountImageStudio(app,sql,env,route){
  const dailyLimit=0; // unlimited per member; API provider billing still applies
  const defaultModel=env.OPENAI_IMAGE_MODEL||'gpt-image-2.5-sunburst';
  const allowed=['gpt-image-2.5-sunburst','gpt-image-2.5-flare','gpt-image-2.6-sunburst','gpt-image-2.6-flare'];
  const upload=multer({storage:multer.memoryStorage(),limits:{fileSize:15*1024*1024,files:16},fileFilter:(req,file,cb)=>cb(null,['image/png','image/jpeg','image/webp'].includes(file.mimetype))});
  app.get('/api/images/usage',route(async(req,res)=>{
    const result=await sql("SELECT COUNT(*)::int AS used FROM team_ai_image_usage WHERE user_id=$1 AND created_at>=date_trunc('day',now())",[req.actor.id]);
    res.json({used:result.rows[0].used,limit:dailyLimit,model:defaultModel});
  }));
  app.post('/api/images/create',upload.array('image[]',16),route(async(req,res)=>{
    if(!env.OPENAI_API_KEY)return res.status(503).json({error:'管理员尚未配置 OPENAI_API_KEY'});
    const prompt=String(req.body.prompt||'').trim();
    const operation=req.body.operation==='edit'?'edit':'generate';
    const model=allowed.includes(req.body.model)?req.body.model:defaultModel;
    if(!prompt||prompt.length>4000)return res.status(400).json({error:'请填写1至4000字的图片要求'});
    if(operation==='edit'&&(!req.files||req.files.length===0))return res.status(400).json({error:'请至少上传一张 PNG、JPG 或 WEBP 原图'});
    if(operation==='edit'&&req.files.length>16)return res.status(400).json({error:'一次最多上传16张图片'});
    if(operation==='edit'&&req.files.reduce((sum,file)=>sum+file.size,0)>45*1024*1024)return res.status(400).json({error:'所有图片合计不能超过45MB'});
    const count=await sql("SELECT COUNT(*)::int AS n FROM team_ai_image_usage WHERE user_id=$1 AND created_at>=date_trunc('day',now())",[req.actor.id]);
    const used=count.rows[0].n;
    if(dailyLimit>0&&used>=dailyLimit)return res.status(429).json({error:'今天的图片生成额度已用完，每人每天'+dailyLimit+'次'});
    const form=new FormData();
    form.append('model',model);
    form.append('prompt',prompt);
    form.append('size','1024x1024');
    form.append('quality','medium');
    form.append('n','1');
    form.append('output_format','png');
    let endpoint='https://api.openai.com/v1/images/generations';
    if(operation==='edit'){
      endpoint='https://api.openai.com/v1/images/edits';
      for(const file of req.files){
        const safeName=String(file.originalname||'source.png').replace(/[^a-zA-Z0-9._-]/g,'_').slice(0,80);
        form.append('image[]',new Blob([file.buffer],{type:file.mimetype}),safeName||'source.png');
      }
    }
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),180000);
    try{
      const response=await fetch(endpoint,{method:'POST',headers:{Authorization:'Bearer '+env.OPENAI_API_KEY},body:form,signal:controller.signal});
      const data=await response.json().catch(()=>({}));
      if(!response.ok){
        const message=String(data.error&&data.error.message||'图像服务暂时不可用').slice(0,240);
        return res.status(response.status===429?429:502).json({error:message});
      }
      const image=data.data&&data.data[0]&&data.data[0].b64_json;
      if(!image)return res.status(502).json({error:'图像服务未返回图片，请稍后重试'});
      await sql('INSERT INTO team_ai_image_usage(user_id,model,operation) VALUES($1,$2,$3)',[req.actor.id,model,operation]);
      res.json({image:'data:image/png;base64,'+image,model,operation,used:used+1,limit:dailyLimit});
    }catch(error){
      res.status(502).json({error:error.name==='AbortError'?'图片生成超时，请稍后重试':'图片服务连接失败，请稍后重试'});
    }finally{clearTimeout(timer);}
  }));
};

"""V36: cost-aware GPT-6 Luna Chat Completions request config.

Works with existing api/academy/chat and private course priority. No database
schema change, no migration, no member/financial tables touched.
"""
from pathlib import Path
p=Path('member-tree/academy.py')
s=p.read_text(encoding='utf-8')

old="""        body={'model':os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),
              'messages':messages,'temperature':0.4,'max_tokens':max_tokens}
"""
new="""        model=os.environ.get('OPENAI_MODEL','gpt-6-luna').strip() or 'gpt-6-luna'
        body={'model':model,'messages':messages}
        if model.startswith(('gpt-6-', 'gpt-6.')):
            # GPT-6 Luna supports 'none'; prevents paid internal reasoning
            # tokens for routine knowledge-based conversational training.
            # GPT-6 Chat Completions prefers max_completion_tokens.
            body['reasoning_effort']='none'
            body['max_completion_tokens']=min(1200,max(32,int(max_tokens)))
        elif model.startswith(('gpt-5-', 'gpt-5.')):
            body['reasoning_effort']='minimal'
            body['max_completion_tokens']=min(1200,max(32,int(max_tokens)))
        else:
            # Preserve compatibility with existing GPT-4.1 mini installation.
            body['temperature']=0.4
            body['max_tokens']=min(1200,max(32,int(max_tokens)))
"""
assert s.count(old)==1,'model request anchor missing'
s=s.replace(old,new)
# Keep full source excerpts in the existing knowledge browser; only limit text
# sent into the model to save API tokens.
old2="""        evidence='\\n\\n'.join('['+str(i+1)+'] '+x['title']+'｜来源 '+x['source']+'\\n'+x['excerpt']
                             for i,x in enumerate(sources))
"""
new2="""        # 4 matching references x ~450 characters rather than 7 x ~780.
        # The full referenced lessons remain available unchanged in the UI.
        evidence='\\n\\n'.join('['+str(i+1)+'] '+x['title']+'｜来源 '+x['source']+'\\n'+x['excerpt'][:450]
                             for i,x in enumerate(sources[:4]))
"""
assert s.count(old2)==1,'evidence anchor missing'
s=s.replace(old2,new2)
# Keep all twelve recent turns to retain the V35 dialogue behavior. Save
# tokens by narrowing each saved chat turn (was 1500 characters).
old3="                cleaned.append({'role':m['role'],'content':content[:1500]})"
assert s.count(old3)==1,'history content cap anchor missing'
s=s.replace(old3,"                cleaned.append({'role':m['role'],'content':content[:600]})",1)
p.write_text(s,encoding='utf-8')
print('V36: GPT-6 Luna lowest-cost active model, no paid reasoning, bounded course evidence and chat context.')

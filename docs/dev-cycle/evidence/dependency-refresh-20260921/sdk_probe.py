"""Exercise installed LLM SDK serialization without remote model calls."""
import json
import httpx
from google import genai
from google.genai import types
from openai import OpenAI
calls=[]
def respond(request):
    calls.append(request.url.host)
    body=json.loads(request.content)
    if request.url.host=='generativelanguage.googleapis.com':
        assert body['contents'][0]['parts'][0]['text']=='synthetic probe'
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"action":"HOLD"}'}],'role':'model'},'finishReason':'STOP'}]})
    assert request.url.host=='api.openai.com'
    assert body['messages'][0]['content']=='synthetic probe'
    return httpx.Response(200,json={'id':'qa','object':'chat.completion','created':0,'model':'qa','choices':[{'index':0,'message':{'role':'assistant','content':'{"action":"HOLD"}'},'finish_reason':'stop'}]})
transport=httpx.MockTransport(respond)
with genai.Client(api_key='synthetic-not-a-real-key',http_options=types.HttpOptions(client_args={'transport':transport})) as client:
    response=client.models.generate_content(model='qa',contents='synthetic probe',config=types.GenerateContentConfig(response_mime_type='application/json'))
    assert json.loads(response.text)=={'action':'HOLD'}
with OpenAI(api_key='synthetic-not-a-real-key',http_client=httpx.Client(transport=transport)) as client:
    response=client.chat.completions.create(model='qa',messages=[{'role':'user','content':'synthetic probe'}])
    assert json.loads(response.choices[0].message.content)=={'action':'HOLD'}
assert calls==['generativelanguage.googleapis.com','api.openai.com']
print(json.dumps({'google_genai':'HOLD','openai':'HOLD','synthetic_transport_calls':len(calls),'remote_model_calls':0}))

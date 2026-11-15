import json,math,collections,heapq
src=open('build6.py').read().split('pl=collections.defaultdict(list)\nfor e in places')[0]
exec(compile(src,'b','exec'))
d=json.load(open('avg_sections.json'))
segms={}
for ref,ws in wayref.items():
    for w in ws:
        g=[(round(q['lat'],7),round(q['lon'],7)) for q in w['geometry']]
        ms=w['tags'].get('maxspeed'); fw=w['tags'].get('maxspeed:forward',ms); bw=w['tags'].get('maxspeed:backward',ms)
        for i in range(len(g)-1):
            segms[(ref,g[i],g[i+1])]=fw; segms.setdefault((ref,g[i+1],g[i]),bw)
def path(ref,a,b,limit):
    dist={a:0};prev={};pq=[(0,a)]
    while pq:
        dd,u=heapq.heappop(pq)
        if u==b: break
        if dd>dist[u] or dd>limit: continue
        for v,w in G[ref][u].items():
            if dd+w<dist.get(v,1e18): dist[v]=dd+w; prev[v]=u; heapq.heappush(pq,(dd+w,v))
    if b not in prev and a!=b: return None
    p=[b]
    while p[-1]!=a: p.append(prev[p[-1]])
    return p[::-1]
for o in d:
    ref=roadref[o['road']]
    a=nearest_node(ref,(o['start']['lat'],o['start']['lon'])); b=nearest_node(ref,(o['end']['lat'],o['end']['lon']))
    p=path(ref,a,b,o['lengthKm']*2500+20000)
    mix=collections.Counter(); runs=[]
    for u,v in zip(p,p[1:]):
        L=hav(u,v); ms=segms.get((ref,u,v))
        ms=int(ms) if ms and ms.isdigit() else None
        mix[ms]+=L
        if runs and runs[-1][0]==ms: runs[-1][1]+=L
        else: runs.append([ms,L])
    known={k:v for k,v in mix.items() if k}
    kn=sum(known.values())
    weighted=round(kn/sum(L/k for k,L in known.items())*3.6/3.6) if kn else None  # km/h (k in km/h, harmonic)
    weighted=round(kn/sum(L/k for k,L in known.items())) if kn else None
    long_runs=[ms for ms,L in runs if ms and L>=1000]
    conservative=min(long_runs) if long_runs else (min(known) if known else o['speedLimit'])
    o['osmLimits']={str(k):round(v/1000,2) for k,v in sorted(known.items(),reverse=True)}
    o['osmUnknownKm']=round(mix.get(None,0)/1000,2)
    o['weightedLimit']=weighted
    o['speedLimit']=conservative
    print(f"{o['road'][:10]:10} {o['title'] if 'title' in o else o['start']['name']+'→'+o['end']['name']:32} cons={conservative} w={weighted} {o['osmLimits']} ?={o['osmUnknownKm']}")
json.dump(d,open('avg_sections_limits.json','w'),ensure_ascii=False,indent=1)

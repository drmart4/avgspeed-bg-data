import json,math,collections,heapq
exec(open('build.py').read().split('pl=collections.defaultdict(list)')[0])  # reuse loaders, graph, helpers
# --- heal graph gaps: connect each dangling node to nearest node of same ref within 250 m
for ref,adj in G.items():
    grid=collections.defaultdict(list)
    for n in adj: grid[(round(n[0]*200),round(n[1]*200))].append(n)
    for n in list(adj):
        if len(adj[n])>1: continue
        gx,gy=round(n[0]*200),round(n[1]*200); best=None
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for m in grid[(gx+dx,gy+dy)]:
                    if m==n or m in adj[n]: continue
                    d=hav(n,m)
                    if d<250 and (best is None or d<best[0]): best=(d,m)
        if best: adj[n][best[1]]=best[0]; adj[best[1]][n]=best[0]
    # also link opposite carriageways every node within 60 m (cheap: same grid cell)
    for cell,ns in grid.items():
        for i in range(len(ns)):
            for j in range(i+1,len(ns)):
                d=hav(ns[i],ns[j])
                if d<60 and ns[j] not in adj[ns[i]]: adj[ns[i]][ns[j]]=d; adj[ns[j]][ns[i]]=d
for n in list(coords): pass
def coord(n): return n
nearest_cache={}
def nearest_node(ref,p):
    key=(ref,round(p[0],5),round(p[1],5))
    if key not in nearest_cache: nearest_cache[key]=min(G[ref], key=lambda n: hav(n,p))
    return nearest_cache[key]
pl=collections.defaultdict(list)
for e in places: pl[e['tags'].get('name')].append((e['lat'],e['lon']))
manual_hint={'Тунел "Мало Бучино"':None,'яз. Дяково':None,'м/у 18 и п.в.Илиянци':None}
# endpoints per road
ends=collections.defaultdict(dict)  # road -> km -> name
for s in secs:
    for k in ('start','end'): ends[s['road']][s[k]['km']]=s[k]['name']
final={}; method={}
for road,kms in ends.items():
    ref=roadref[road]
    cand={}
    for km,name in kms.items():
        locs=pl.get(name) or []
        if locs:
            near=[l for l in locs if hav(nearest_node(ref,l),l)<8000] or locs
            uniq=[(k2,pl[n2][0]) for k2,n2 in kms.items() if k2!=km and len(pl.get(n2) or [])==1 and hav(nearest_node(ref,pl[n2][0]),pl[n2][0])<8000]
            def sc(l):
                if not uniq: return hav(nearest_node(ref,l),l)
                return sum(abs(math.log((hav(l,p2)+2000)/(abs(k2-km)*1000+2000))) for k2,p2 in uniq)
            place=min(near,key=sc)
            if uniq:
                k2,p2=min(uniq,key=lambda t:abs(t[0]-km))
                if hav(place,p2)>abs(k2-km)*1000*1.1+5000: locs=[]
        if locs:
            c=[nearest_node(ref,x) for x in gant if hav(x,place)<6000 and hav(nearest_node(ref,x),x)<60]
            c.sort(key=lambda n: hav(n,place))
            c.append(nearest_node(ref,place))
            cand[km]=(place,list(dict.fromkeys(c)))
    # pairs that form sections
    pairs={(min(s['start']['km'],s['end']['km']),max(s['start']['km'],s['end']['km'])) for s in secs if s['road']==road}
    # choose candidate per km minimizing error over pairs (greedy coordinate descent)
    choice={km:c[1][-1] for km,c in cand.items()}  # start with projected
    dcache={}
    def rd(a,b):
        if (a,b) not in dcache:
            D=dijkstra(ref,a,limit=150000); dcache[(a,b)]=D.get(b); dcache[(b,a)]=D.get(b)
        return dcache[(a,b)]
    def err(km,n):
        e=0
        for a,b in pairs:
            if km not in (a,b): continue
            o=b if km==a else a
            if o not in choice: continue
            d=rd(n,choice[o]); L=(b-a)*1000
            e+= abs(d-L)/L if d else 5
        return e
    for it in range(3):
        for km,(place,c) in cand.items():
            choice[km]=min(c,key=lambda n: err(km,n)+0.015*hav(n,place)/1000)
    OVR={('I-5',34.704):(43.5719,25.8221),('I-5',11.382):(43.7564,25.9066),('АМ "Тракия"',210.523):(42.34374,25.68972)}
    for (r2,k2),p in OVR.items():
        if r2==road: choice[k2]=nearest_node(ref,p)
    for km in kms:
        if km in choice: final[(road,km)]=choice[km]; method[(road,km)]='osm'
    # linear referencing for unresolved / bad endpoints from a good neighbour
    for km,name in kms.items():
        need = (km not in choice or err(km,choice[km])>0.12) and (road,km) not in OVR
        if not need: continue
        nbrs=[(o, a, b) for a,b in pairs if km in (a,b) for o in [b if km==a else a] if o in choice and err(o,choice[o])<0.12]
        if not nbrs: nbrs=[(o, a, b) for a,b in pairs if km in (a,b) for o in [b if km==a else a] if o in choice]
        if not nbrs: continue
        o,a,b=min(nbrs,key=lambda t: abs(t[0]-km))
        D=dijkstra(ref,choice[o],limit=abs(o-km)*1000+5000); target=abs(o-km)*1000
        cs=[n for n,d in D.items() if abs(d-target)<100]
        if not cs: continue
        hint=cand[km][0] if km in cand else None
        if hint: n=min(cs,key=lambda n:hav(n,hint))
        else:
            # pick the candidate farthest from any other endpoint on the opposite side
            others=[final[(road,k)] for k in choice if (k-o)*(km-o)<0]
            if others:
                far=[n for n in cs if min(hav(n,x) for x in others) > hav(choice[o],min(others,key=lambda x:hav(x,choice[o])))]
                if not far: continue
                n=max(far,key=lambda n: min(hav(n,x) for x in others))
            else:
                n=max(cs,key=lambda n: hav(n,(42.6977,23.3219)))
        gs=[nearest_node(ref,x) for x in gant if hav(x,n)<1500 and hav(nearest_node(ref,x),x)<60]
        if gs: n=min(gs,key=lambda g: hav(g,n))
        choice[km]=n; final[(road,km)]=n; method[(road,km)]='km-ref'
# validate
out=[]; bad=[]
for i,s in enumerate(secs):
    ref=roadref[s['road']]; ka=(s['road'],s['start']['km']); kb=(s['road'],s['end']['km'])
    a,b=final.get(ka),final.get(kb); L=abs(kb[1]-ka[1])*1000
    if not a or not b:
        bad.append(('MISSING',s['road'],s['start']['name'],s['end']['name'])); continue
    D=dijkstra(ref,a,limit=L*2+20000) if a else {}
    r=D.get(b); ratio=r/L if r else None
    ok=bool(ratio and 0.9<ratio<1.1)
    cnt=collections.Counter()
    for w in wayref[ref]:
        ms=w['tags'].get('maxspeed')
        if not ms or not ms.isdigit(): continue
        g=w['geometry']
        for j in range(len(g)-1):
            p=(g[j]['lat'],g[j]['lon'])
            if hav(p,a)+hav(p,b)<hav(a,b)*1.05+300: cnt[int(ms)]+=hav(p,(g[j+1]['lat'],g[j+1]['lon']))
    default=140 if s['road'].startswith('АМ') else 90
    limit=cnt.most_common(1)[0][0] if cnt else default
    if not ok: bad.append((s['road'],s['start']['name'],s['end']['name'],round(L/1000,2),ratio and round(ratio,2)))
    out.append(dict(id=i+1,road=s['road'],
      start=dict(name=s['start']['name'],km=s['start']['km'],lat=round(a[0],6),lon=round(a[1],6)),
      end=dict(name=s['end']['name'],km=s['end']['km'],lat=round(b[0],6),lon=round(b[1],6)),
      lengthKm=round(L/1000,3),speedLimit=limit,pending=s['pending'],
      note=(s['start']['note'] or s['end']['note']) or None,verified=ok))
bykm=collections.defaultdict(dict)
for o in out:
    for k in ('start','end'): bykm[o['road']][o[k]['km']]=(o[k]['lat'],o[k]['lon'],o[k]['name'])
for road,m in bykm.items():
    ks=sorted(m)
    for x,y in zip(ks,ks[1:]):
        h=hav(m[x][:2],m[y][:2])/1000; L=y-x
        if h>L*1.05+0.5 or h<L*0.3: print('SEQ?',road,m[x][2],x,'->',m[y][2],y,'straight',round(h,1),'km-diff',round(L,1))
json.dump(out,open('avg_sections.json','w'),ensure_ascii=False,indent=1)
print('ok',sum(o['verified'] for o in out),'of',len(out))
for b in bad: print('BAD',b)
print(collections.Counter(method.values()))

import json,math,collections,heapq
secs=json.load(open('sections.json'))
o1=json.load(open('osm1.json'))['elements']; places=json.load(open('osm3.json'))['elements']
roads=json.load(open('roads.json'))['elements']
gant=[(e['lat'],e['lon']) for e in o1 if e.get('tags',{}).get('highway')=='toll_gantry']
R=6371000
def hav(a,b):
    la1,lo1,la2,lo2=map(math.radians,(a[0],a[1],b[0],b[1]))
    return 2*R*math.asin(math.sqrt(math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2))
roadref=json.load(open('roadref.json'))  # генерира се от update.py
# graph per ref
G=collections.defaultdict(lambda: collections.defaultdict(dict)); coords={}; wayref=collections.defaultdict(list)
for w in roads:
    refs=(w['tags'].get('ref') or '').split(';')
    g=w['geometry']; ids=[(round(q['lat'],7),round(q['lon'],7)) for q in g]
    for r in refs:
        wayref[r].append(w)
        for i in range(len(ids)-1):
            a,b=ids[i],ids[i+1]; pa=(g[i]['lat'],g[i]['lon']); pb=(g[i+1]['lat'],g[i+1]['lon'])
            coords[a]=pa; coords[b]=pb; d=hav(pa,pb)
            G[r][a][b]=d; G[r][b][a]=d
def nearest_node(ref,p):
    return min(G[ref], key=lambda n: hav(coords[n],p))
def dijkstra(ref,src,limit=400000):
    dist={src:0}; pq=[(0,src)]
    while pq:
        d,u=heapq.heappop(pq)
        if d>dist[u] or d>limit: continue
        for v,w in G[ref][u].items():
            nd=d+w
            if nd<dist.get(v,1e18): dist[v]=nd; heapq.heappush(pq,(nd,v))
    return dist
pl=collections.defaultdict(list)
for e in places: pl[e['tags'].get('name')].append((e['lat'],e['lon']))
# road nodes per ref for fast-ish nearest
def dist_to_road(ref,p):
    n=nearest_node(ref,p); return hav(coords[n],p),n
points={}  # (road,km) -> (lat,lon,method)
specials={}
for s in secs:
    ref=roadref[s['road']]
    for key in ('start','end'):
        pt=s[key]; k=(s['road'],pt['km'])
        if k in points or k in specials: continue
        locs=pl.get(pt['name'])
        if not locs: specials[k]=pt['name']; continue
        best=min(((dist_to_road(ref,l)[0],l) for l in locs))
        place=best[1]
        g=[x for x in gant if hav(x,place)<4000 and dist_to_road(ref,x)[0]<60]
        if g:
            gp=min(g,key=lambda x:hav(x,place)); points[k]=(gp[0],gp[1],'gantry')
        else:
            d,n=dist_to_road(ref,place); points[k]=(coords[n][0],coords[n][1],'projected')
# specials via linear referencing from neighbour on same road
for k,name in specials.items():
    road,km=k; ref=roadref[road]
    anchors=sorted([kk for kk in points if kk[0]==road], key=lambda kk: abs(kk[1]-km))
    a=anchors[0]; an=nearest_node(ref,points[a][:2]); D=dijkstra(ref,an)
    target=abs(a[1]-km)*1000
    cands=[n for n,d in D.items() if abs(d-target)<150]
    # direction: towards lower km if km<anchor km -> pick candidate farthest from the next anchor on the other side
    other=[kk for kk in points if kk[0]==road and ((kk[1]-a[1])*(km-a[1])<0)]
    if other:
        o=min(other,key=lambda kk:abs(kk[1]-a[1])); n=max(cands,key=lambda n:hav(coords[n],points[o][:2]))
    else:
        # use Sofia centre as direction hint (both specials head towards Sofia)
        n=min(cands,key=lambda n:hav(coords[n],(42.6977,23.3219))) if km<a[1] else max(cands,key=lambda n:hav(coords[n],(42.6977,23.3219)))
    points[k]=(coords[n][0],coords[n][1],'km-from-'+str(a[1]))
    print('special',name,points[k])
# validate & speed limit
out=[]; bad=0
for i,s in enumerate(secs):
    ref=roadref[s['road']]; a=points[(s['road'],s['start']['km'])]; b=points[(s['road'],s['end']['km'])]
    L=abs(s['end']['km']-s['start']['km'])*1000
    na,nb=nearest_node(ref,a[:2]),nearest_node(ref,b[:2])
    D=dijkstra(ref,na,limit=L*2+20000); rd=D.get(nb)
    ratio=(rd/L) if rd else None
    # speed limit: length-weighted maxspeed of ways within the section corridor
    mids=[(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t) for t in (0.25,0.5,0.75)]
    cnt=collections.Counter()
    for w in wayref[ref]:
        ms=w['tags'].get('maxspeed')
        if not ms or not ms.isdigit(): continue
        g=w['geometry']
        for j in range(len(g)-1):
            p=(g[j]['lat'],g[j]['lon'])
            if hav(p,a[:2])+hav(p,b[:2])<hav(a[:2],b[:2])*1.05+300:
                cnt[int(ms)]+=hav(p,(g[j+1]['lat'],g[j+1]['lon']))
    default=140 if s['road'].startswith('АМ') else 90
    limit=cnt.most_common(1)[0][0] if cnt else default
    flag='' if ratio and 0.85<ratio<1.2 else '  <-- CHECK'
    if flag: bad+=1
    print(f"{s['road'][:14]:14} {s['start']['name'][:14]:14}->{s['end']['name'][:14]:14} L={L/1000:6.2f} road={rd and rd/1000:} r={ratio and round(ratio,2)} lim={limit} {dict(cnt.most_common(3)) and {k:round(v) for k,v in cnt.most_common(3)}} {a[2]}/{b[2]}{flag}")
    out.append(dict(id=i+1,road=s['road'],start=dict(name=s['start']['name'],km=s['start']['km'],lat=round(a[0],6),lon=round(a[1],6)),
        end=dict(name=s['end']['name'],km=s['end']['km'],lat=round(b[0],6),lon=round(b[1],6)),lengthKm=round(L/1000,3),speedLimit=limit,
        pending=s['pending'],note=(s['start']['note'] or s['end']['note']) or None,verified=bool(flag=='')))
json.dump(out,open('avg_sections.json','w'),ensure_ascii=False,indent=1)
print('bad',bad,'of',len(out))

import random

def repair_shift_segment(segment, n_workers):
    segment = [x if 1 <= x <= n_workers else random.randint(1, n_workers) for x in segment]
    seen = set()
    unique_segment = []
    missing = list(range(1, n_workers + 1))
    for w in segment:
        if w not in seen:
            seen.add(w)
            unique_segment.append(w)
            if w in missing:
                missing.remove(w)
        else:
            unique_segment.append(-1)
    for i in range(len(unique_segment)):
        if unique_segment[i] == -1:
            unique_segment[i] = missing.pop(0) if missing else random.randint(1, n_workers)
    return unique_segment

def repair_chromosome(ch, nt, ns, nw, strict=True):
    if strict and nw >= nt * ns:
        vals = []
        for k in range(ns):
            seg = ch[k*nt:(k+1)*nt]
            seg = [x if 1<=x<=nw else random.randint(1,nw) for x in seg]
            vals.extend(seg)
        seen = set()
        rep = []
        mis = list(range(1, nw+1))
        for v in vals:
            if v not in seen:
                seen.add(v)
                rep.append(v)
                if v in mis: mis.remove(v)
            else:
                rep.append(-1)
        for i in range(len(rep)):
            if rep[i]==-1:
                rep[i] = mis.pop(0) if mis else random.randint(1,nw)
        return rep
    res = []
    for k in range(ns):
        res.extend(repair_shift_segment(ch[k*nt:(k+1)*nt], nw))
    return res

def _tot(m, c, nt, ns):
    t=0
    if not m: return 0
    for k in range(ns):
        sw=c[k*nt:(k+1)*nt]
        for j in range(nt):
            w=sw[j]
            if 1<=w<=len(m):
                try: t+=m[w-1][j][k]
                except: pass
    return t

def _mx(m):
    if not m: return 1
    v=0
    for r in m:
        for t in r:
            for x in t:
                try:
                    if x>v: v=x
                except: pass
    return v if v>0 else 1

def fitness(cm,c,nt,ns,st,tm=None,ym=None,wc=.5,wt=.5,wy=0):
    if not cm: return float('inf')
    if st in ('cost_time','cost_time_yield'):
        tc=_tot(cm,c,nt,ns)
        tt=_tot(tm,c,nt,ns) if tm else 0
        ty=_tot(ym,c,nt,ns) if ym else 0
        return wc*tc/_mx(cm)+wt*tt/_mx(tm if tm else [[1]])-wy*ty/_mx(ym if ym else [[1]])
    if st=='yield': return -_tot(cm,c,nt,ns)
    return _tot(cm,c,nt,ns)

def selection(p, co):
    n=len(p)
    r=[]
    for _ in range(n):
        a,b=random.randint(0,n-1),random.randint(0,n-1)
        r.append(p[a][:] if co[a]<co[b] else p[b][:])
    return r

def crossover(par,cl,ra,nw,nt,ns,sg):
    off=[]
    for i in range(0,len(par)-1,2):
        c1,c2=par[i][:],par[i+1][:]
        if random.random()<ra and cl>2:
            a=random.randint(1,cl-2)
            b=random.randint(a+1,cl-1)
            t=c1[a:b]
            c1[a:b]=par[i+1][a:b]
            c2[a:b]=t
        off.append(repair_chromosome(c1,nt,ns,nw,sg))
        off.append(repair_chromosome(c2,nt,ns,nw,sg))
    if len(off)<len(par): off.append(par[-1][:])
    return off

def mutate(pop,nw,ra,nt,ns,sg):
    cl=len(pop[0])
    res=[]
    for ind in pop:
        ic=ind[:]
        if random.random()<ra:
            a,b=random.randint(0,cl-1),random.randint(0,cl-1)
            ic[a],ic[b]=ic[b],ic[a]
        res.append(repair_chromosome(ic,nt,ns,nw,sg))
    return res

def run_ga(nw,nt,ns,cm,st,tm=None,ym=None,wc=.5,wt=.5,wy=0):
    PS,NI,CR,MR=50,100,0.8,0.2
    CL=nt*ns
    fu=nw>=nt*ns
    pop=[]
    for _ in range(PS):
        if fu: ind=random.sample(list(range(1,nw+1)),nt*ns)
        else:
            ind=[]
            for _ in range(ns): ind.extend(random.sample(range(1,nw+1),nt))
        pop.append(ind)
    bc,bs,bg=float('inf'),[],0
    for g in range(NI):
        co=[fitness(cm,i,nt,ns,st,tm,ym,wc,wt,wy) for i in pop]
        mc=min(co)
        if mc<bc: bc,bs,bg=mc,pop[co.index(mc)][:],g
        pop=mutate(crossover(selection(pop,co),CL,CR,nw,nt,ns,fu),nw,MR,nt,ns,fu)
    ac=_tot(cm,bs,nt,ns)
    at=_tot(tm,bs,nt,ns) if tm else 0
    ay=_tot(ym,bs,nt,ns) if ym else 0
    shifts=[]
    for k in range(ns):
        sw=bs[k*nt:(k+1)*nt]
        asn=[]
        for j in range(nt):
            w=sw[j]
            cv=tv=yv=0
            if 1<=w<=len(cm):
                try: cv=cm[w-1][j][k]
                except: pass
            if tm and 1<=w<=len(tm):
                try: tv=tm[w-1][j][k]
                except: pass
            if ym and 1<=w<=len(ym):
                try: yv=ym[w-1][j][k]
                except: pass
            a={"task":j+1,"worker":w,"cost":cv}
            if st in ('cost_time','cost_time_yield'): a["time"]=tv
            if st=='cost_time_yield': a["yield"]=yv
            asn.append(a)
        shifts.append({"shift":k+1,"assignments":asn})
    r={"bestCost":abs(bc),"bestSolution":bs,"serviceType":st,"strictMode":fu,
       "constraintInfo":"✅ قيد شامل" if fu else "⚠️ قيد محلي",
       "shifts":shifts,"foundAtGeneration":bg+1,"totalGenerations":NI,"actualCost":ac}
    if st in ('cost_time','cost_time_yield'):
        r["actualTime"]=at
        r["weights"]={"cost":wc,"time":wt}
    if st=='cost_time_yield':
        r["actualYield"]=ay
        r["weights"]["yield"]=wy

    worker_view = {}
    for k in range(ns):
        sw=bs[k*nt:(k+1)*nt]
        for j in range(nt):
            w=sw[j]
            cv=tv=yv=0
            if 1<=w<=len(cm):
                try: cv=cm[w-1][j][k]
                except: pass
            if tm and 1<=w<=len(tm):
                try: tv=tm[w-1][j][k]
                except: pass
            if ym and 1<=w<=len(ym):
                try: yv=ym[w-1][j][k]
                except: pass

            placement = {"task":j+1, "shift":k+1, "cost":cv}
            if st in ('cost_time','cost_time_yield'): placement["time"]=tv
            if st=='cost_time_yield': placement["yield"]=yv

            if str(w) not in worker_view: worker_view[str(w)] = []
            worker_view[str(w)].append(placement)

    r["workerView"] = worker_view
    return r

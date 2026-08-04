import json, time, mmap, urllib.request
API="http://127.0.0.1:11434"
def meminfo(k):
    for l in open('/proc/meminfo'):
        if l.startswith(k+':'): return int(l.split()[1])//1024
def ps():
    return json.loads(urllib.request.urlopen(API+"/api/ps",timeout=30).read()).get("models",[])
def post(p,b,t=300):
    r=urllib.request.Request(API+p,data=json.dumps(b).encode(),headers={"content-type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=t).read())
def reclaim(target_mb, cap_mb=4600):
    """Force page-cache reclaim without root: fault in anonymous pages, then release."""
    if meminfo('MemFree') >= target_mb: return 0, False
    t0=time.time(); n=min(cap_mb, meminfo('MemAvailable')-400)
    m=mmap.mmap(-1, n*1024*1024)
    for off in range(0, n*1024*1024, 4096): m[off]=1
    m.close()
    return round((time.time()-t0)*1000), True
def barrier(prev, need_mb):
    """SPEC 4a corrected: evict, verify ps empty, verify MemFree (NOT MemAvailable), reclaim, settle."""
    r={"evict_ms":0,"ps_empty":False,"reclaim_ms":0,"reclaimed":False}
    t0=time.time()
    if prev:
        post("/api/generate",{"model":prev,"prompt":"","keep_alive":0,"stream":False})
        while time.time()-t0<120:
            if not ps(): r["ps_empty"]=True; break
            time.sleep(0.5)
    else: r["ps_empty"]=not ps()
    r["evict_ms"]=round((time.time()-t0)*1000)
    r["memfree_after_evict_mb"]=meminfo('MemFree')
    r["reclaim_ms"], r["reclaimed"] = reclaim(need_mb)
    time.sleep(1.5)
    r["memfree_before_load_mb"]=meminfo('MemFree')
    r["memavailable_mb"]=meminfo('MemAvailable')
    r["barrier_ok"]= r["ps_empty"] and r["memfree_before_load_mb"]>=need_mb
    return r

G3,G4="qwen2.5-coder:3b","granite4:micro"
NEED={G3:3200,G4:3400}   # resident size + headroom, NOT download size
seq=[G3,G4,G3]
out={"spec":"4a-corrected","metric":"MemFree","sequence":seq,"transitions":[],"oom":0}
prev=None
for i,m in enumerate(seq):
    rec={"step":i,"model":m,"preceding_model":prev}
    rec["barrier"]=barrier(prev, NEED[m])
    t0=time.time()
    try:
        r=post("/api/generate",{"model":m,"prompt":"return the single word ok","stream":False,
                                "keep_alive":"3m","options":{"num_ctx":4096,"num_predict":8}})
        rec["ok"]=True; rec["resp"]=(r.get("response") or "").strip()[:20]
    except Exception as e:
        rec["ok"]=False; rec["error"]=str(e)[:120]
        if "memory" in str(e).lower() or "terminated" in str(e).lower(): out["oom"]+=1
    rec["load_gen_ms"]=round((time.time()-t0)*1000)
    p=ps(); rec["resident_mb"]= round(p[0]["size"]/1048576) if p else None
    out["transitions"].append(rec); prev=m
out["all_ok"]=all(t.get("ok") for t in out["transitions"])
out["oom_count"]=out["oom"]
print(json.dumps(out,indent=1))

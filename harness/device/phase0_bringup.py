import json, time, subprocess, mmap, urllib.request, socket, hashlib, os
API="http://127.0.0.1:11434"
def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True).stdout.strip()
def meminfo(k):
    for l in open('/proc/meminfo'):
        if l.startswith(k+':'): return int(l.split()[1])//1024
def ps(): return json.loads(urllib.request.urlopen(API+"/api/ps",timeout=30).read()).get("models",[])
def post(p,b,t=300):
    r=urllib.request.Request(API+p,data=json.dumps(b).encode(),headers={"content-type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=t).read())

def reclaim(target):
    """Iteratively fault in anonymous pages to evict page cache until MemFree>=target."""
    if meminfo('MemFree')>=target: return 0,False
    t0=time.time(); did=False
    for _ in range(4):
        n=max(500, meminfo('MemAvailable')-500)
        try:
            m=mmap.mmap(-1,n*1024*1024)
            for o in range(0,n*1024*1024,4096): m[o]=1
            m.close(); did=True
        except Exception: pass
        time.sleep(1.5)
        if meminfo('MemFree')>=target: break
    return round((time.time()-t0)*1000),did

def barrier(need):
    """SPEC 4a corrected. FAILS CLOSED: barrier_ok False means infra fault, never a candidate failure."""
    t0=time.time()
    for r in ps(): post("/api/generate",{"model":r["name"],"prompt":"","keep_alive":0,"stream":False})
    while time.time()-t0<120 and ps(): time.sleep(0.5)
    ev=round((time.time()-t0)*1000)
    rc,did=reclaim(need); time.sleep(1.5)
    mf=meminfo('MemFree'); empty=not ps()
    return {"evict_ms":ev,"ps_empty":empty,"reclaim_ms":rc,"reclaimed":did,"need_mb":need,
            "memfree_before_load_mb":mf,"memavailable_mb":meminfo('MemAvailable'),
            "barrier_ok":empty and mf>=need}

PROMPT=("Write ONLY a C function, no prose, no markdown fence:\n"
        "void sat_add_u8(const uint8_t *a, const uint8_t *b, uint8_t *out, size_t n)\n"
        "Saturating add of n bytes. Include only <stdint.h> and <stddef.h>.")
GENS=[("qwen2.5-coder:3b",3600),("granite4:micro",5100)]
smoke=[]
for m,need in GENS:
    b=barrier(need)
    if not b["barrier_ok"]:
        smoke.append({"model":m,"barrier":b,"generated":None,"infra_fault":True,
                      "note":"BARRIER FAILED CLOSED. Infra fault, NOT a generation failure. Not scored."})
        continue
    t0=time.time()
    try:
        r=post("/api/generate",{"model":m,"prompt":PROMPT,"stream":False,"keep_alive":"2m",
                                "options":{"num_ctx":4096,"num_predict":300,"temperature":0.8}})
        src=r.get("response",""); ok=True; err=None
    except Exception as e:
        src=""; ok=False; err=str(e)[:160]
    p=ps()
    smoke.append({"model":m,"barrier":b,"generated":ok,"error":err,"infra_fault":False,
                  "gen_ms":round((time.time()-t0)*1000),
                  "resident_mb":round(p[0]["size"]/1048576) if p else None,
                  "chars":len(src),"has_signature":"sat_add_u8" in src,
                  "emits_markdown_fence":"```" in src,
                  "sha256":hashlib.sha256(src.encode()).hexdigest()[:16]})
    if src: open(os.path.expanduser("~/ecs/receipts/smoke_%s.c"%m.replace(':','_').replace('.','_')),"w").write(src)

os.makedirs(os.path.expanduser("~/ecs/receipts"),exist_ok=True)
rec={"phase":"P0","spec":"ECS Build Spec v1","generated_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
 "host":{"hostname":socket.gethostname(),"arch":sh("uname -m"),"kernel":sh("uname -r"),
         "l4t":sh("head -1 /etc/nv_tegra_release"),"mem_total_mb":meminfo('MemTotal')},
 "device_state":{"nvpmodel_q":sh("sudo -n nvpmodel -q").replace("\n"," "),
   "power_mode_table":"0=15W 1=25W 2=MAXN_SUPER 3=7W","mode_used":2,"jetson_clocks_applied":True,
   "governor":sh("cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor"),"core":3,
   "cur_freq_khz":sh("cat /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq"),
   "timing_source":"clock","timing_reason":"perf not installed; SPEC section 4 fallback"},
 "toolchain":{"gcc":sh("gcc --version | head -1"),"flags_measure":"-std=c11 -O3 -mcpu=native -Wall -Wextra"},
 "baseline_crc32":{"median_ns":59296.0,"mad_ns":0.0,"spread_pct":0.0,"batches":10,"warmup":200,
                   "measured":1000,"stability_gate_2pct":True,"check_value":"0xCBF43926 verified"},
 "generators":[{"id":"G3","model":"qwen2.5-coder:3b","digest":"f72c60cabf62","params":"3.1B","quant":"Q4_K_M",
                "ctx_max":32768,"num_ctx_used":4096,"license":"Qwen Research (non-commercial)",
                "resident_mb":2280,"memfree_needed_mb":3600},
               {"id":"G4","model":"granite4:micro","digest":"89962fcc7523","params":"3.4B","quant":"Q4_K_M",
                "ctx_max":131072,"num_ctx_used":4096,"license":"Apache-2.0",
                "resident_mb":2586,"memfree_needed_mb":5100}],
 "ollama":{"version":sh("ollama --version"),"bind":"127.0.0.1:11434"},
 "smoke_tests":smoke,
 "sudo_invocations":["nvpmodel -m 0 (OPERATOR ERROR: that is 15W not max; reverted)",
                     "nvpmodel -m 2 (MAXN_SUPER)","jetson_clocks","nvpmodel -q"]}
p=os.path.expanduser("~/ecs/receipts/phase0.json")
json.dump(rec,open(p,"w"),indent=1)
print(json.dumps(smoke,indent=1)); print("written:",p)

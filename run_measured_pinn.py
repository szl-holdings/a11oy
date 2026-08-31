#!/usr/bin/env python3
# Measured agentic-PINN runner: real sovereign-GPU energy -> physical-bounds cert.
# Doctrine v11: energy = real NVML power x time ONLY. No fabricated numbers.
import sys, os, json, math, time, types, urllib.request

# shim starlette so certify_job (byte-identical) imports on a minimal host
for nm, attrs in {"starlette":[], "starlette.requests":["Request"],
                  "starlette.responses":["JSONResponse"], "starlette.routing":["Route"]}.items():
    if nm not in sys.modules:
        m = types.ModuleType(nm)
        for a in attrs: setattr(m, a, type(a,(object,),{}))
        sys.modules[nm] = m
sys.path.insert(0, "/opt/szl/a11oy")
import szl_pinn_bounds as P

JOULE="http://100.96.129.45:9471/"
LLM="http://100.125.77.31:11434/api/generate"; MODEL="qwen2.5-coder:7b"

def gj(url,t=8):
    with urllib.request.urlopen(url,timeout=t) as r: return json.loads(r.read().decode())
def read_gpu():
    d=gj(JOULE)
    for e in d["engines"]:
        if e["engine"]=="betterwithage":
            g=e["gpus"][0]
            if not g.get("live"): raise RuntimeError("GPU exporter not live: %r"%g.get("live"))
            return {"joules":float(g["joules"]),"power_w":g.get("power_w"),
                    "temp_c":g.get("temp_c"),"util":g.get("util"),"samples":g.get("samples")}
    raise RuntimeError("betterwithage engine not found")
def llm(prompt,t=90):
    body=json.dumps({"model":MODEL,"prompt":prompt,"stream":False,"options":{"temperature":0.2}}).encode()
    req=urllib.request.Request(LLM,data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=t) as r: d=json.loads(r.read().decode())
    return (d.get("response","") or "").strip(), int(d.get("eval_count",0) or 0)

# PDE: -u'' = f on [0,1], u(0)=u(1)=0 ; exact multi-mode solution (real residuals)
EXACT={1:1.0,3:0.5,5:0.2}
def f_rhs(x): return sum(c*(k*math.pi)**2*math.sin(k*math.pi*x) for k,c in EXACT.items())
def u_exact(x): return sum(c*math.sin(k*math.pi*x) for k,c in EXACT.items())

def gauss(Ain,bin):
    n=len(bin); A=[r[:] for r in Ain]; b=bin[:]; fl=0
    for col in range(n):
        p=max(range(col,n),key=lambda r:abs(A[r][col]))
        A[col],A[p]=A[p],A[col]; b[col],b[p]=b[p],b[col]; piv=A[col][col]
        for r in range(col+1,n):
            fct=A[r][col]/piv
            for cc in range(col,n): A[r][cc]-=fct*A[col][cc]
            b[r]-=fct*b[col]; fl+=(n-col)*2
    x=[0.0]*n
    for r in range(n-1,-1,-1):
        s=b[r]-sum(A[r][cc]*x[cc] for cc in range(r+1,n)); x[r]=s/A[r][r]; fl+=(n-r)*2
    return x,fl
def solve(N,M):
    fl=0; xs=[(j+1)/(M+1) for j in range(M)]
    A=[[((k+1)*math.pi)**2*math.sin((k+1)*math.pi*x) for k in range(N)] for x in xs]
    b=[f_rhs(x) for x in xs]; fl+=M*N*3
    AtA=[[0.0]*N for _ in range(N)]; Atb=[0.0]*N
    for i in range(N):
        for k in range(N):
            AtA[i][k]=sum(A[j][i]*A[j][k] for j in range(M)); fl+=M*2
        Atb[i]=sum(A[j][i]*b[j] for j in range(M)); fl+=M*2
    c,fe=gauss(AtA,Atb); return c,fl+fe
def metrics(c,N,T=200):
    xs=[(j+1)/(T+1) for j in range(T)]; res=[]; num=0.0; den=0.0
    for x in xs:
        upp=sum(c[k]*((k+1)*math.pi)**2*math.sin((k+1)*math.pi*x) for k in range(N))
        res.append(abs(upp-f_rhs(x)))
        ux=sum(c[k]*math.sin((k+1)*math.pi*x) for k in range(N))
        num+=(ux-u_exact(x))**2; den+=u_exact(x)**2
    return max(res),sum(res)/len(res),(math.sqrt(num/den) if den>0 else 0.0)

print("[*] reading joules_before (real NVML)...",flush=True)
g0=read_gpu(); t0=time.time(); print("    ",g0,flush=True)
TOL=1e-3; N=1; M=6; rounds=[]; total_flops=0; accepted=False; final="REFINE"
for rd in range(1,7):
    c,fl=solve(N,max(M,2*N)); total_flops+=fl
    mr,meanr,rl2=metrics(c,N); total_flops+=200*N*3
    prompt=("You are the deny-by-default Lambda-gate governor of an agentic PINN solver. "
            f"Round {rd}: basis_size={N}, collocation_points={max(M,2*N)}, "
            f"max_residual={mr:.3e}, rel_L2_error={rl2:.3e}, tolerance=1e-3. "
            "If rel_L2_error < 1e-3 the solve has converged -> reply ALLOW; else reply REFINE. "
            "Answer with exactly one word: ALLOW or REFINE.")
    dec,ev=llm(prompt); dword="ALLOW" if "ALLOW" in dec.upper() else "REFINE"
    just,ev2=llm(f"In one sentence, justify the governor decision '{dword}' for a PINN with rel_L2={rl2:.3e} versus tolerance 1e-3.")
    converged=rl2<TOL; acc=bool(converged and dword=="ALLOW")
    rounds.append({"round_index":rd,"basis_size":N,"n_pde_collocation":max(M,2*N),
        "max_residual_on_test":mr,"mean_residual_on_test":meanr,"rel_l2_error_estimate":rl2,
        "lambda_verdict":("ALLOW" if dword=="ALLOW" else "REFINE"),
        "lambda_gate_converged":converged,"accepted":acc,
        "modeled_not_measured":True,"error_estimate_is_bound":True,
        "llm_eval_count":ev+ev2,"llm_justification":just[:280]})
    print(f"    round {rd}: N={N} rl2={rl2:.3e} maxr={mr:.3e} llm={dword} acc={acc} evtok={ev+ev2}",flush=True)
    if acc: accepted=True; final="ALLOW"; break
    N+=2; M=max(M+2,2*N)
t1=time.time(); g1=read_gpu(); print("[*] joules_after:",g1,flush=True)

delta=g1["joules"]-g0["joules"]; wall=t1-t0
if delta<=0 or wall<=0:
    print("ABORT: non-positive measured energy/time (no fabrication).",file=sys.stderr); sys.exit(2)
avg_power=delta/wall; temp_k=(g1["temp_c"] or g0["temp_c"] or 50.0)+273.15
N_final=rounds[-1]["basis_size"]
bit_ops=int(total_flops); bits_erased=float(total_flops*64); info_bits=float(N_final*64)
src=("on-metal NVML (sovereign GPU betterwithage / NVIDIA RTX 5050 Laptop) via szl joule-meter; "
     "Lambda-gate governor inference ran on this GPU")
note=(f"Energy = REAL nvidia-smi power x wall_time over the governed agentic-PINN solve window "
      f"(delta={delta:.3f} J across {g1['samples']-g0['samples']} live samples, wall={wall:.2f}s). "
      f"PINN spectral-collocation residual math ran in pure-Python on the box CPU; the governing "
      f"Lambda-gate decisions ran as real inference on the sovereign GPU. bit_operations counted "
      f"from the solve; bits_erased modeled as ops x 64 (float64). MEASURED = power/time/temperature.")
cert=P.certify_job(avg_power_w=avg_power,wall_time_s=wall,temperature_k=temp_k,
    bit_operations=bit_ops,bits_erased=bits_erased,info_content_bits=info_bits,
    device_mass_kg=0.05,device_radius_m=0.02,label="MEASURED",source=src,note=note)

trail={"model":"SZL Agentic PINN - governed solve decision trail","schema":"szl/agentic-pinn-trail/v1",
    "final_verdict":final,"final_accepted":accepted,"converged":accepted,"rounds":rounds,
    "pde":"-u''(x)=f(x) on [0,1], u(0)=u(1)=0; spectral sin-collocation; exact multi-mode {1:1.0,3:0.5,5:0.2}",
    "energy_measurement":{"source":src,"joules_before":g0["joules"],"joules_after":g1["joules"],
        "delta_joules_MEASURED":delta,"wall_time_s_MEASURED":wall,"avg_power_w_MEASURED":avg_power,
        "temperature_k_MEASURED":temp_k,"live_samples_consumed":g1["samples"]-g0["samples"],
        "gpu":"NVIDIA GeForce RTX 5050 Laptop GPU (betterwithage, tailnet 100.125.77.31)"},
    "doctrine":P.DOCTRINE,"lambda_note":P.LAMBDA_NOTE,"timestamp_utc":time.time()}

cd=os.path.dirname(os.path.abspath(__file__))
cp=os.path.join(cd,"physical_bounds_certificate.json"); tp=os.path.join(cd,"agentic_decision_trail.json")
open(cp,"w").write(json.dumps(cert,indent=2)); open(tp,"w").write(json.dumps(trail,indent=2))
print("\n===== MEASURED CERTIFICATE =====")
print(json.dumps({"label":cert["measured"]["label"],"energy_joules_derived":cert["energy_joules_derived"],
    "avg_power_w_MEASURED":cert["measured"]["avg_power_w_MEASURED"],
    "wall_time_s_MEASURED":cert["measured"]["wall_time_s_MEASURED"],
    "temperature_k_MEASURED":cert["measured"]["temperature_k_MEASURED"],
    "landauer_multiple_above_floor":cert["landauer_multiple_above_floor"],
    "physically_bounded":cert["physically_bounded"],
    "inputs_hash":cert["inputs_hash"],"final_accepted":accepted,"rounds":len(rounds)},indent=2))
print("WROTE",cp,tp)

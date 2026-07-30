"""2026-07-30 quiet-window charts. Pool taxonomy mapped to interactive.html
buckets (Topology/Hydration/App/Session/DB wait/Other), span-only shares,
pool-ms = share x server p50 (same methodology as quiet-0717/0721 charts)."""
import re, collections, json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

SIGS = [
    ('db_wait',      r'recv_into|network_layer|_socket|ssl\.py|selectors'),
    ('bson_decode',  r'decode_all|bson/'),
    ('uuid',         r'uuid\.py|to_uuid \(utils\.jac|_intern_uuid'),
    ('build_object', r'__init__ \(<string>|deserialize_projected|_load_anchor|Permission'),
    ('value_decode', r'_deserialize_value|coerce \('),
    ('serialize',    r'_serialize_attrs|_serialize_value|iterencode|render \(.*responses|dumps|_finalize_call_response|serialize \('),
    ('topology',     r'topology_index|gti_cache|decode_cached|_get_col|resolve_hop \(|resolve_chain|edges_to_nodes'),
    ('visit_dispatch', r'osp_kernel|osp_spawn|osp_visit|run_typed|run_untyped|node_desc|spawn_call'),
    ('memory_l1l2',  r'memory\.impl\.jac|tiered|batch_get'),
    ('mongo_plan',   r'execute_plan \(memory_hierarchy|pymongo|cursor'),
    ('resolver',     r'resolver\.jac|resolver\.impl|query_utils'),
    ('app',          r'app\.jac'),
]
GAP = r'render \(.*responses|iterencode|_finalize_call_response|JSONResponse|responses\.py'
SPAN = r'app\.jac|execute_walker|spawn|resolver|execute_plan|serializer\.impl'
# fine pool -> interactive.html bucket
BUCKET = {'topology':'topo','resolver':'topo','bson_decode':'hyd','value_decode':'hyd',
          'build_object':'hyd','uuid':'hyd','app':'app','visit_dispatch':'app',
          'memory_l1l2':'sess','mongo_plan':'sess','db_wait':'db','serialize':None,  # gap
          'other':'other'}
POOLS = [('topo','Topology / index','#1f77b4'),('hyd','Hydration / decode','#2ca08c'),
         ('app','App + walker','#e8a000'),('sess','Session / memory','#1a7a1a'),
         ('db','DB wait','#4b3fa8'),('other','Other (in-span)','#e05252')]

def load(path):
    out=[]
    for t in re.split(r'\n(?=Thread )', open(path).read()):
        if not t.startswith('Thread') or '(idle)' in t.splitlines()[0]: continue
        fr=[l.strip() for l in t.splitlines()[1:] if l.strip() and '(' in l]
        if fr: out.append(fr)
    return out

arms={}
for arm in ('anchor','leaf'):
    stacks=load(f'{arm}_dumps.txt')
    span_pool=collections.Counter(); nspan=0; ngap=0; nfw=0
    for frames in stacks:
        pool=None
        for f in frames:
            for name,rx in SIGS:
                if re.search(rx,f): pool=name; break
            if pool: break
        pool=pool or 'other'
        joined='\n'.join(frames)
        if re.search(GAP,joined): ngap+=1; continue
        if not re.search(SPAN,joined): nfw+=1; continue
        nspan+=1
        b=BUCKET.get(pool)
        span_pool[b or 'other']+=1
    arms[arm]={'span_pool':dict(span_pool),'nspan':nspan,'ngap':ngap,'nfw':nfw}
    print(arm, arms[arm])

med=json.load(open('medians_2026-07-30.json'))
P50={'anchor':med['jaseci:feed']['server'][0],'leaf':med['jaseci:feed_leaf']['server'][0]}

# ---- chart 1: latency, 5 arms ----
ENG=[('postgres:feed','postgres\n(raw psycopg)','#4e79a7'),
     ('sqlalchemy:feed','sqlalchemy\n(ORM)','#17a2b8'),
     ('jaseci:feed_leaf','jac leaf\n(dict materialize)','#9467bd'),
     ('jaseci:feed','jac anchor\n(all-opts objects)','#f28e2b'),
     ('neo4j:feed','neo4j\n(cypher)','#2ca02c')]
INK="#1a1a1a"; MUT="#666"; GRID="#ddd"
fig,ax=plt.subplots(figsize=(9.6,5.6))
xs=range(len(ENG))
p50=[med[k]['server'][0] for k,_,_ in ENG]; p95=[med[k]['server'][1] for k,_,_ in ENG]; p99=[med[k]['server'][2] for k,_,_ in ENG]
ax.bar(xs,p50,color=[c for _,_,c in ENG],width=0.6,zorder=3)
ax.scatter(xs,p95,marker="D",s=36,color=INK,zorder=4); ax.scatter(xs,p99,marker="^",s=52,color=INK,zorder=4)
ymax=max(p99)*1.18
for x,v in zip(xs,p50):
    ax.text(x, v-0.04*ymax if v>0.14*ymax else v+0.12*ymax, f"{v:g}",
            ha="center", va="top" if v>0.14*ymax else "bottom",
            fontweight="bold", fontsize=11, color="white" if v>0.14*ymax else INK, zorder=5)
# ablation tick on jac anchor
nofix=57.3
ax.scatter([3],[nofix],marker="_",s=300,color="#f28e2b",zorder=4)
ax.annotate(f"no serializer fix {nofix:g}", xy=(3,nofix), xytext=(3.55,nofix+9),
            fontsize=8.5,color="#b15900",arrowprops=dict(arrowstyle="->",color="#b15900",lw=1))
ax.set_xticks(list(xs)); ax.set_xticklabels([l for _,l,_ in ENG],fontsize=9.4,color=INK)
ax.set_ylabel("server-side latency (ms)",color=MUT); ax.set_ylim(0,ymax)
ax.yaxis.grid(True,color=GRID,zorder=0); ax.set_axisbelow(True)
for s in ("top","right"): ax.spines[s].set_visible(False)
ax.tick_params(colors=MUT)
leg=[plt.Line2D([0],[0],marker="D",color="w",markerfacecolor=INK,markersize=7,label="p95"),
     plt.Line2D([0],[0],marker="^",color="w",markerfacecolor=INK,markersize=9,label="p99")]
ax.legend(handles=leg,loc="upper left",frameon=False,fontsize=9.5)
ax.set_title("littleX load_feed — server span, quiet window, performance governor",fontsize=13,color=INK,pad=10)
fig.text(0.5,0.015,"500 req x 3 repeats (median) - node-report app - jac arms same boot :8005, serializer fix in - leaf: JAC_LEAF_MATERIALIZE=Tweet - 2026-07-30",
         ha="center",fontsize=7.8,color=MUT)
fig.tight_layout(rect=[0,0.05,1,1])
fig.savefig("feed_latency_2026-07-30.png",dpi=150,facecolor="white")
print("wrote feed_latency_2026-07-30.png")

# ---- chart 2: pools, interactive.html buckets (corrected boundary) ----
# server_total_ms is computed INSIDE the walker (before response build), so
# span pools scale to the FULL server p50; serialize/response CPU sits in the
# client-server gap (drawn beyond the span bar, hatched).
CLI={'anchor':med['jaseci:feed']['client'][0],'leaf':med['jaseci:feed_leaf']['client'][0]}
fig2,ax2=plt.subplots(figsize=(11.5,4.8))
rows=[("jac anchor  load_feed",'anchor'),("jac leaf  load_feed_leaf",'leaf')]
for yi,(lbl,arm) in enumerate(rows):
    d=arms[arm]; n=d['nspan']; p50v=P50[arm]
    left=0
    for key,plab,col in POOLS:
        c=d['span_pool'].get(key,0)
        w=c/n*p50v if n else 0
        if w<=0: continue
        ax2.barh(yi,w,left=left,color=col,height=0.55,zorder=3,edgecolor="white",linewidth=0.8)
        if w>1.6: ax2.text(left+w/2,yi,f"{w:.1f}",ha="center",va="center",color="white",fontsize=8.6,fontweight="bold")
        left+=w
    gap=CLI[arm]-p50v
    ax2.barh(yi,gap,left=left,color="#bbbbbb",height=0.55,zorder=3,edgecolor="white",linewidth=0.8,hatch="//")
    ax2.text(left+gap/2,yi,f"{gap:.1f}",ha="center",va="center",color="#333",fontsize=8.6,fontweight="bold")
    ax2.text(CLI[arm]+0.7,yi,f"srv {p50v:g} / cli {CLI[arm]:g} ms",ha="left",va="center",color=INK,fontsize=9.6,fontweight="bold")
ax2.set_yticks([0,1]); ax2.set_yticklabels([r[0] for r in rows],fontsize=10.5,color=INK)
ax2.invert_yaxis(); ax2.set_xlim(0,max(CLI.values())*1.20)
ax2.set_xlabel("ms - solid: walker span pools (sum = server p50) - hatched: response serialize + wire + client parse (= client-server gap)",color=MUT,fontsize=9)
ax2.xaxis.grid(True,color=GRID,zorder=0); ax2.set_axisbelow(True)
for s in ("top","right","left"): ax2.spines[s].set_visible(False)
ax2.tick_params(colors=MUT)
ax2.legend(handles=[Patch(facecolor=c,label=l) for _,l,c in POOLS]+[Patch(facecolor="#bbbbbb",hatch="//",label="Response + wire + parse (post-span)")],
           loc="upper center",bbox_to_anchor=(0.5,-0.22),frameon=False,fontsize=8.6,ncol=4)
ax2.set_title("load_feed cost anatomy — walker span by pool + post-span response phase",fontsize=12.5,color=INK,pad=8)
fig2.text(0.5,0.012,"server_total_ms = in-walker span (excludes response build) - pool-ms = span-share x server p50 - profiler: serialize CPU ~15/17ms sits in the hatched phase - 300 dumps/arm - quiet - 2026-07-30",ha="center",fontsize=7.4,color=MUT)
fig2.tight_layout(rect=[0,0.14,1,1])
fig2.savefig("feed_pools_2026-07-30.png",dpi=150,facecolor="white")
print("wrote feed_pools_2026-07-30.png (corrected)")

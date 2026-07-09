"""Server-side runtime probe + no-op floor walker.

`runtime_probe` reports which jaclang the SERVER process actually runs and
whether the ablation flags' code + env are visible to it — `jac run` probes
can't see the serve path. `noop` returns [] and is the fixed per-request-tax
floor (auth + context + commit, zero graph work) for the ablation analysis.
"""

import os;
import jaclang;
import from jaclang.runtimelib.topology_index { TopologyIndex }

walker:pub runtime_probe {
    can run with Root entry {
        report {
            "jaclang_file": str(jaclang.__file__),
            "cross_root_symbol": hasattr(TopologyIndex, "resolve_chain_cross_root"),
            "env_JAC_TOPOLOGY_INDEX": os.environ.get("JAC_TOPOLOGY_INDEX"),
            "env_JAC_CROSS_ROOT_RESOLVE": os.environ.get("JAC_CROSS_ROOT_RESOLVE"),
            "env_JAC_TOPOLOGY_DECODE_CACHE": os.environ.get("JAC_TOPOLOGY_DECODE_CACHE")
        };
    }
}

walker:pub noop {
    can run with Root entry {
        report [];
    }
}

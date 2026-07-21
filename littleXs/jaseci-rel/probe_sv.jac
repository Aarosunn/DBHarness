"""Server-side runtime probe + no-op floor walker.

`runtime_probe` reports which jaclang the SERVER process actually runs and
the EFFECTIVE ablation-flag values, resolved with the same precedence the
runtime uses (env var -> jac.toml [run] -> default) but via PUBLIC API only
(the runtime's own _enabled helpers are impl-private and not importable).
`noop` returns [] and is the fixed per-request-tax floor (auth + context +
commit, zero graph work) for the ablation analysis.
"""

import os;
import jaclang;
import from jaclang.project.config { get_config }

def _effective(env_name: str, cfg_value: bool) -> bool {
    env = os.environ.get(env_name);
    if env is not None {
        return env.lower() in ("1", "true", "yes", "on");
    }
    return cfg_value;
}

walker:pub runtime_probe {
    can run with Root entry {
        cfg = get_config();
        run_cfg = cfg.run if cfg is not None else None;
        report {
            "jaclang_file": str(jaclang.__file__),
            "gti_effective": _effective(
                "JAC_TOPOLOGY_INDEX",
                run_cfg.topology_index if run_cfg else True
            ),
            "cross_root_effective": _effective(
                "JAC_CROSS_ROOT_RESOLVE",
                run_cfg.cross_root_resolve if run_cfg else False
            ),
            "batch_l3_effective": _effective(
                "JAC_BATCH_L3",
                run_cfg.batch_l3 if run_cfg else False
            ),
            "read_only_effective": _effective(
                "JAC_READ_ONLY",
                run_cfg.read_only if run_cfg else False
            ),
            "env_JAC_TOPOLOGY_INDEX": os.environ.get("JAC_TOPOLOGY_INDEX"),
            "env_JAC_CROSS_ROOT_RESOLVE": os.environ.get("JAC_CROSS_ROOT_RESOLVE"),
            "env_JAC_BATCH_L3": os.environ.get("JAC_BATCH_L3"),
            "env_JAC_READ_ONLY": os.environ.get("JAC_READ_ONLY")
        };
    }
}

walker:pub noop {
    can run with Root entry {
        report [];
    }
}

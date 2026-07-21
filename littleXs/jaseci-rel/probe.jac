"""Step-0 probe: is the FORK's jaclang live (vs the frozen bundled copy)?"""
import jaclang;
import from jaclang.runtimelib.topology_index { TopologyIndex }

with entry {
    print(f"jaclang: {jaclang.__file__}");
    print(f"cross_root symbol: {hasattr(TopologyIndex, 'resolve_chain_cross_root')}");
}

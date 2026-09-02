# Cluster Tensor Runtime Integration v0.2

Cluster execution now carries frozen `reason-computation-ir/0.1` workloads
from the coordinator to the calculation-result worker.  Workers invoke the
installed `reason-runtime-host` as a separate process and return the native
calculation result, Tensor metadata, and Tensor trace to the coordinator.

The process boundary is explicit: `transport_tensors: true` serializes result
Tensors as `{tensor_id, shape, dtype, data}` only for Cluster requests;
ordinary Runtime Host responses retain their existing lightweight handles.
`reason cluster simulate` and `reason cluster run` therefore execute Tensor
operations in Rust workers instead of reporting a symbolic-only completion.

The install and update-package distributions now include `ClusterRuntime` and
the `reason-cluster` executable, verified with the native profile
`reasonscript-cluster-runtime/0.2`.

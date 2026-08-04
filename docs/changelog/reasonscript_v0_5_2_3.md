# ReasonScript v0.5.2.3

ReasonScript 0.5.2.3 corrects two language defects found during
VisionWorldModel V0 development:

- nested function calls lower in inner-to-outer order and no longer duplicate
  transition IDs when composed with branching functions;
- literal inner results participate in outer branch evaluation;
- branching inner return states converge through explicit, unique merge edges;
- typed function parameter lists may span multiple source lines.

Canonical function return IDs and runtime compatibility remain unchanged.

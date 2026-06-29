/**
 * Builds a KnowledgeViewModel from the raw knowledge artifact.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §11
 */
import type { KnowledgeViewModel, KnowledgeEvidenceViewModel } from "./viewModels";

export function buildKnowledgeEvidence(raw: unknown): KnowledgeViewModel {
  if (raw == null) {
    return { status: "unavailable", knowledgeCount: 0, evidenceCount: 0, items: [] };
  }

  const k = raw as Record<string, unknown>;
  const rawItems = Array.isArray(k.knowledge) ? (k.knowledge as Record<string, unknown>[]) : [];

  if (rawItems.length === 0) {
    return {
      status: "empty",
      knowledgeCount: 0,
      evidenceCount: (k.evidence_count as number) ?? 0,
      items: [],
    };
  }

  const items: KnowledgeEvidenceViewModel[] = rawItems.map((item) => {
    const evidence = item.evidence as Record<string, unknown> | undefined;
    return {
      id: (item.id as string) ?? "?",
      source: (item.source as string) ?? "",
      relation: (item.relation as string) ?? "",
      target: (item.target as string) ?? "",
      confidence: item.confidence as number | undefined,
      evidencePath: Array.isArray(item.evidence_path)
        ? (item.evidence_path as string[])
        : [],
      pathSignature: item.path_signature as string | undefined,
      branchId: item.branch_id as string | undefined,
      pathLength: item.path_length as number | undefined,
      transitions: evidence && Array.isArray(evidence.transitions)
        ? (evidence.transitions as string[])
        : [],
    };
  });

  return {
    status: "success",
    knowledgeCount: (k.knowledge_count as number) ?? items.length,
    evidenceCount: (k.evidence_count as number) ?? items.length,
    items,
  };
}

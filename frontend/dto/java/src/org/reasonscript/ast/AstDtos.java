package org.reasonscript.ast;

import java.util.List;

public final class AstDtos {
    private AstDtos() {}

    public sealed interface DeclarationNode permits GoalNode, StateNode,
            TransitionNode, ConstraintNode, ContextNode {}

    public record GoalNode(
            String node_type, String node_id, String kind, String target)
            implements DeclarationNode {}

    public record StateNode(
            String node_type, String node_id, String state_id,
            String state_type, Object data)
            implements DeclarationNode {}

    public record TransitionNode(
            String node_type, String node_id, String transition_id,
            String source, String relation, String target,
            Double expected_cost, String guard, Object effect)
            implements DeclarationNode {}

    public record ConstraintNode(
            String node_type, String node_id, String constraint_id,
            String kind, String expression)
            implements DeclarationNode {}

    public record ContextNode(
            String node_type, String node_id, String context_id,
            String context_type, String uri)
            implements DeclarationNode {}

    public record MetadataNode(
            String node_type, String node_id, String key, Object value) {}

    public record ModuleNode(
            String node_type,
            String version,
            String node_id,
            List<String> imports,
            List<DeclarationNode> declarations,
            List<MetadataNode> metadata) {
        public ModuleNode {
            imports = imports == null ? List.of() : List.copyOf(imports);
            declarations = List.copyOf(declarations);
            metadata = metadata == null ? List.of() : List.copyOf(metadata);
        }
    }
}

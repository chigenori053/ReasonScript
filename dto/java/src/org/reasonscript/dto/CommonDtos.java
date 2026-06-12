package org.reasonscript.dto;

import java.math.BigInteger;
import java.util.List;
import java.util.Map;

public final class CommonDtos {
    private CommonDtos() {}

    public record StateSnapshot(String state_id, String state_type, Object data) {}
    public record GoalSpec(String kind, String target) {}
    public record ContextRef(String context_id, String context_type, String uri) {}
    public record ConstraintSpec(String constraint_id, String kind, String expression) {}
    public record TransitionSpec(
            String transition_id,
            String source,
            String relation,
            String target,
            double expected_cost,
            String guard,
            Object effect) {}
    public record PlannerPolicy(String strategy, Long max_depth, Long max_alternatives) {}
    public record ExecutionPolicy(
            long max_steps, boolean rollback_on_failure, String constraint_mode) {}
    public record TracePolicy(
            String level, boolean include_alternatives, boolean include_state_data) {}
    public record ReasonIR(
            String schema_version,
            StateSnapshot initial_state,
            GoalSpec goal,
            List<ContextRef> context_refs,
            List<ConstraintSpec> constraints,
            List<TransitionSpec> transitions,
            PlannerPolicy planner_policy,
            ExecutionPolicy execution_policy,
            TracePolicy trace_policy,
            Map<String, Object> metadata) {}
    public record PlanStep(
            String step_id, String transition_id, String source, String target) {}
    public record PlanPath(List<String> step_ids, double expected_cost) {}
    public record ExecutionPlan(
            List<PlanStep> selected_steps,
            List<PlanPath> alternative_paths,
            double expected_cost,
            List<String> evidence_refs,
            String planner_version) {}
    public record StateDelta(
            String delta_id,
            StateSnapshot before_state,
            StateSnapshot after_state,
            String applied_transition,
            BigInteger timestamp) {}

    public enum InferenceStatus {
        COMPLETED("completed"),
        REJECTED("rejected"),
        DECISION_REQUIRED("decision_required"),
        FAILED("failed");

        public final String wireValue;
        InferenceStatus(String wireValue) { this.wireValue = wireValue; }
    }

    public record Proof(List<String> selected_step_ids, List<String> evidence_refs) {}
    public record Violation(String constraint_id, String message) {}
    public record InferenceResult(
            InferenceStatus status,
            StateSnapshot final_state,
            List<StateDelta> state_deltas,
            Proof proof,
            List<Violation> violations,
            List<PlanPath> alternatives,
            String trace_id) {}

    public sealed interface TraceEvent permits PlanSelected, StateDeltaApplied,
            ConstraintViolation, EvidenceObserved, ToolInvoked {}
    public record PlanSelected(
            String event_type, List<String> step_ids, double expected_cost)
            implements TraceEvent {}
    public record StateDeltaApplied(
            String event_type, String delta_id, String transition_id, String transaction_id)
            implements TraceEvent {}
    public record ConstraintViolation(
            String event_type, String constraint_id, String message)
            implements TraceEvent {}
    public record EvidenceObserved(String event_type, String evidence_ref)
            implements TraceEvent {}
    public record ToolInvoked(String event_type, String tool_ref, String result_ref)
            implements TraceEvent {}
    public record Trace(
            String request_id,
            String reason_ir_version,
            String planner_version,
            String policy_version,
            List<TraceEvent> events) {}

    public enum TransactionStatus {
        PREPARED("prepared"),
        ACCEPTED("accepted"),
        REJECTED("rejected"),
        COMMITTED("committed"),
        ROLLED_BACK("rolled_back");

        public final String wireValue;
        TransactionStatus(String wireValue) { this.wireValue = wireValue; }
    }

    public record TransactionRecord(
            String transaction_id,
            String execution_plan_id,
            String candidate_id,
            String delta_id,
            TransactionStatus status,
            BigInteger commit_timestamp,
            List<String> validation_failures,
            String source_delta_id) {}
}

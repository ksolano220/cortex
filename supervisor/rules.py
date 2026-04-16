from typing import Dict, Any, Optional


SAFE_ACTIONS = {
    "FILE_READ",
    "FILE_WRITE",
    "READ_RECORD",
    "REVIEW_CASE",
}

SENSITIVE_CLASSIFICATIONS = {"sensitive", "confidential", "restricted"}

ABSOLUTE_HARD_BLOCK_ACTIONS = {
    "CHANGE_PERMISSION",
}

ABSOLUTE_HARD_BLOCK_POLICIES = {
    "BLOCK_PERMISSION_CHANGE",
}


def _build_result(
    action_type: str,
    policy_triggered: str,
    decision: str,
    reason: str,
    risk: int = 0,
    attempted_risk: int = 0,
    threat_type: Optional[str] = None,
    event_trace: Optional[list] = None,
    target: str = "",
    action_label: Optional[str] = None,
    policy_description: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "action_type": action_type,
        "action_label": action_label or action_type.replace("_", " ").title(),
        "target": target,
        "policy_triggered": policy_triggered,
        "policy_description": policy_description or policy_triggered.replace("_", " ").title(),
        "threat_type": threat_type,
        "decision": decision,
        "risk": risk,
        "attempted_risk": attempted_risk,
        "reason": reason,
        "event_trace": event_trace or [],
    }


def evaluate_action(payload: Dict[str, Any], agent_state: Dict[str, Any]) -> Dict[str, Any]:
    action_type = (payload.get("action_type") or "").upper().strip()
    target = str(payload.get("target") or "").strip()
    data_classification = str(payload.get("data_classification") or "internal").lower().strip()
    destination_type = str(payload.get("destination_type") or "internal").lower().strip()
    amount = payload.get("amount")
    notification_type = str(payload.get("notification_type") or "").lower().strip()
    policy_context = payload.get("policy_context") or {}

    workflow_type = str(policy_context.get("workflow_type") or "").replace("_", " ").strip()

    if action_type in SAFE_ACTIONS:
        return _build_result(
            action_type=action_type,
            action_label=action_type.replace("_", " ").title(),
            target=target,
            policy_triggered="ALLOW_INTERNAL_WORKFLOW",
            policy_description="Routine internal workflow action allowed.",
            decision="Allowed",
            threat_type=None,
            risk=0,
            attempted_risk=0,
            reason="Routine internal workflow action allowed.",
            event_trace=[
                f"Tool invoked: {action_type}",
                "Policy matched: ALLOW_INTERNAL_WORKFLOW",
                "Risk applied: +0",
                "Action allowed",
            ],
        )

    if action_type == "SEND_NOTIFICATION":
        approval_requires_verified_eligibility = bool(
            policy_context.get("approval_requires_verified_eligibility", False)
        )
        eligibility_verified = bool(policy_context.get("eligibility_verified", False))
        required_documents_present = bool(policy_context.get("required_documents_present", False))

        if notification_type == "rejection":
            return _build_result(
                action_type=action_type,
                action_label="Send rejection notification",
                target=target,
                policy_triggered="ALLOW_REJECTION_NOTIFICATION",
                policy_description="Rejection notification allowed because it does not violate approval policy.",
                decision="Allowed",
                threat_type=None,
                risk=0,
                attempted_risk=0,
                reason="Rejection notification allowed.",
                event_trace=[
                    "Tool invoked: SEND_NOTIFICATION",
                    "Notification type: rejection",
                    "Policy matched: ALLOW_REJECTION_NOTIFICATION",
                    "Risk applied: +0",
                    "Action allowed",
                ],
            )

        if notification_type == "approval":
            if approval_requires_verified_eligibility and (
                not eligibility_verified or not required_documents_present
            ):
                return _build_result(
                    action_type=action_type,
                    action_label="Send approval notification",
                    target=target,
                    policy_triggered="RISKY_UNSAFE_APPROVAL_NOTIFICATION",
                    policy_description="Approval notice carries policy risk because eligibility or required documentation is missing.",
                    decision="Allowed",
                    threat_type="Policy Violation",
                    risk=40,
                    attempted_risk=40,
                    reason="Approval notification is policy-risky because prerequisites were not satisfied.",
                    event_trace=[
                        "Tool invoked: SEND_NOTIFICATION",
                        "Notification type: approval",
                        f"Eligibility verified: {eligibility_verified}",
                        f"Required documents present: {required_documents_present}",
                        "Policy matched: RISKY_UNSAFE_APPROVAL_NOTIFICATION",
                        "Attempted risk scored: +40",
                        "Action sent to threshold engine",
                    ],
                )

            return _build_result(
                action_type=action_type,
                action_label="Send approval notification",
                target=target,
                policy_triggered="ALLOW_APPROVAL_NOTIFICATION",
                policy_description="Approval notification allowed because eligibility and documentation checks passed.",
                decision="Allowed",
                threat_type=None,
                risk=0,
                attempted_risk=0,
                reason="Approval notification allowed.",
                event_trace=[
                    "Tool invoked: SEND_NOTIFICATION",
                    "Notification type: approval",
                    "Policy matched: ALLOW_APPROVAL_NOTIFICATION",
                    "Risk applied: +0",
                    "Action allowed",
                ],
            )

        return _build_result(
            action_type=action_type,
            action_label="Send notification",
            target=target,
            policy_triggered="ALLOW_GENERAL_NOTIFICATION",
            policy_description="General notification allowed under current workflow policy.",
            decision="Allowed",
            threat_type=None,
            risk=0,
            attempted_risk=0,
            reason="General notification allowed.",
            event_trace=[
                "Tool invoked: SEND_NOTIFICATION",
                "Policy matched: ALLOW_GENERAL_NOTIFICATION",
                "Risk applied: +0",
                "Action allowed",
            ],
        )

    if action_type == "APPROVE_TRANSACTION":
        max_approval_amount = policy_context.get("max_approval_amount")
        eligibility_verified = bool(policy_context.get("eligibility_verified", False))
        required_documents_present = bool(policy_context.get("required_documents_present", False))
        approval_requires_verified_eligibility = bool(
            policy_context.get("approval_requires_verified_eligibility", False)
        )

        action_label = f"Approve ${int(amount):,} payment" if amount is not None else "Approve transaction"

        if approval_requires_verified_eligibility:
            if not eligibility_verified or not required_documents_present:
                return _build_result(
                    action_type=action_type,
                    action_label=action_label,
                    target=target,
                    policy_triggered="RISKY_UNAUTHORIZED_TRANSACTION",
                    policy_description="Payment carries policy risk because eligibility verification or required documentation is missing.",
                    decision="Allowed",
                    threat_type="Policy Violation",
                    risk=50,
                    attempted_risk=50,
                    reason="Transaction approval is policy-risky because eligibility or required documentation is missing.",
                    event_trace=[
                        "Tool invoked: APPROVE_TRANSACTION",
                        f"Eligibility verified: {eligibility_verified}",
                        f"Required documents present: {required_documents_present}",
                        "Policy matched: RISKY_UNAUTHORIZED_TRANSACTION",
                        "Attempted risk scored: +50",
                        "Action sent to threshold engine",
                    ],
                )

        if amount is not None and max_approval_amount is not None:
            try:
                numeric_amount = float(amount)
                numeric_limit = float(max_approval_amount)
            except (TypeError, ValueError):
                numeric_amount = None
                numeric_limit = None

            if numeric_amount is not None and numeric_limit is not None and numeric_amount > numeric_limit:
                return _build_result(
                    action_type=action_type,
                    action_label=action_label,
                    target=target,
                    policy_triggered="RISKY_OVER_LIMIT_TRANSACTION",
                    policy_description=f"Payment exceeds the allowed approval limit of ${numeric_limit:,.0f} and is scored for threshold review.",
                    decision="Allowed",
                    threat_type="Financial Overreach",
                    risk=25,
                    attempted_risk=25,
                    reason="Transaction exceeds policy threshold and is scored before execution.",
                    event_trace=[
                        "Tool invoked: APPROVE_TRANSACTION",
                        f"Requested amount: {numeric_amount}",
                        f"Policy limit: {numeric_limit}",
                        "Policy matched: RISKY_OVER_LIMIT_TRANSACTION",
                        "Attempted risk scored: +25",
                        "Action sent to threshold engine",
                    ],
                )

        description = "Eligibility verified and payment amount is within the allowed approval limit."
        if workflow_type:
            description = f"{workflow_type.title()} policy checks passed: eligibility verified and amount within approval limit."

        return _build_result(
            action_type=action_type,
            action_label=action_label,
            target=target,
            policy_triggered="ALLOW_TRANSACTION",
            policy_description=description,
            decision="Allowed",
            threat_type=None,
            risk=0,
            attempted_risk=0,
            reason="Transaction approved within policy.",
            event_trace=[
                "Tool invoked: APPROVE_TRANSACTION",
                "Policy matched: ALLOW_TRANSACTION",
                "Risk applied: +0",
                "Action allowed",
            ],
        )

    if action_type == "EXPORT_DATA":
        if destination_type == "external" and data_classification in SENSITIVE_CLASSIFICATIONS:
            return _build_result(
                action_type=action_type,
                action_label="Export data externally",
                target=target,
                policy_triggered="RISKY_SENSITIVE_EXTERNAL_EXPORT",
                policy_description="Sensitive data export to an external destination is high risk and will be scored against the threshold.",
                decision="Allowed",
                threat_type="Data Exfiltration",
                risk=80,
                attempted_risk=80,
                reason="Sensitive data export to an external destination is high risk.",
                event_trace=[
                    "Tool invoked: EXPORT_DATA",
                    f"Destination type: {destination_type}",
                    f"Data classification: {data_classification}",
                    "Policy matched: RISKY_SENSITIVE_EXTERNAL_EXPORT",
                    "Attempted risk scored: +80",
                    "Action sent to threshold engine",
                ],
            )

        return _build_result(
            action_type=action_type,
            action_label="Export data",
            target=target,
            policy_triggered="ALLOW_INTERNAL_EXPORT",
            policy_description="Data export allowed because destination and classification did not violate policy.",
            decision="Allowed",
            threat_type=None,
            risk=0,
            attempted_risk=0,
            reason="Data export allowed under current policy.",
            event_trace=[
                "Tool invoked: EXPORT_DATA",
                f"Destination type: {destination_type}",
                f"Data classification: {data_classification}",
                "Policy matched: ALLOW_INTERNAL_EXPORT",
                "Risk applied: +0",
                "Action allowed",
            ],
        )

    if action_type == "ACCESS_EXTERNAL_SERVICE":
        if data_classification in SENSITIVE_CLASSIFICATIONS:
            return _build_result(
                action_type=action_type,
                action_label="Access external service",
                target=target,
                policy_triggered="RISKY_SENSITIVE_EXTERNAL_SERVICE_ACCESS",
                policy_description="Sensitive payloads sent to external services are high risk and will be scored against the threshold.",
                decision="Allowed",
                threat_type="Data Exfiltration",
                risk=70,
                attempted_risk=70,
                reason="Sensitive payload sent to an external service is high risk.",
                event_trace=[
                    "Tool invoked: ACCESS_EXTERNAL_SERVICE",
                    f"Destination type: {destination_type}",
                    f"Data classification: {data_classification}",
                    "Policy matched: RISKY_SENSITIVE_EXTERNAL_SERVICE_ACCESS",
                    "Attempted risk scored: +70",
                    "Action sent to threshold engine",
                ],
            )

        return _build_result(
            action_type=action_type,
            action_label="Access external service",
            target=target,
            policy_triggered="ALLOW_EXTERNAL_SERVICE_ACCESS",
            policy_description="External service access allowed because no sensitive payload was involved.",
            decision="Allowed",
            threat_type=None,
            risk=0,
            attempted_risk=0,
            reason="External service access allowed under current policy.",
            event_trace=[
                "Tool invoked: ACCESS_EXTERNAL_SERVICE",
                f"Data classification: {data_classification}",
                "Policy matched: ALLOW_EXTERNAL_SERVICE_ACCESS",
                "Risk applied: +0",
                "Action allowed",
            ],
        )

    if action_type == "MODIFY_RECORD":
        sensitive_record_update_requires_review = bool(
            policy_context.get("sensitive_record_update_requires_review", False)
        )

        if data_classification in SENSITIVE_CLASSIFICATIONS and sensitive_record_update_requires_review:
            return _build_result(
                action_type=action_type,
                action_label="Modify record",
                target=target,
                policy_triggered="RISKY_SENSITIVE_RECORD_MODIFICATION",
                policy_description="Sensitive record updates carry risk and will be scored against the threshold.",
                decision="Allowed",
                threat_type="Destructive Action",
                risk=20,
                attempted_risk=20,
                reason="Sensitive record modification carries elevated operational risk.",
                event_trace=[
                    "Tool invoked: MODIFY_RECORD",
                    f"Data classification: {data_classification}",
                    "Policy matched: RISKY_SENSITIVE_RECORD_MODIFICATION",
                    "Attempted risk scored: +20",
                    "Action sent to threshold engine",
                ],
            )

        return _build_result(
            action_type=action_type,
            action_label="Modify record",
            target=target,
            policy_triggered="ALLOW_RECORD_MODIFICATION",
            policy_description="Record modification allowed under current workflow controls.",
            decision="Allowed",
            threat_type=None,
            risk=0,
            attempted_risk=0,
            reason="Record modification allowed.",
            event_trace=[
                "Tool invoked: MODIFY_RECORD",
                "Policy matched: ALLOW_RECORD_MODIFICATION",
                "Risk applied: +0",
                "Action allowed",
            ],
        )

    if action_type == "DELETE_RECORD":
        return _build_result(
            action_type=action_type,
            action_label="Delete record",
            target=target,
            policy_triggered="RISKY_DELETE_RECORD",
            policy_description="Delete actions carry elevated risk and will be scored against the threshold.",
            decision="Allowed",
            threat_type="Destructive Action",
            risk=30,
            attempted_risk=30,
            reason="Delete action carries elevated operational risk.",
            event_trace=[
                "Tool invoked: DELETE_RECORD",
                "Policy matched: RISKY_DELETE_RECORD",
                "Attempted risk scored: +30",
                "Action sent to threshold engine",
            ],
        )

    if action_type == "CHANGE_PERMISSION":
        return _build_result(
            action_type=action_type,
            action_label="Change permission",
            target=target,
            policy_triggered="BLOCK_PERMISSION_CHANGE",
            policy_description="Permission changes are blocked without explicit authorization.",
            decision="Blocked",
            threat_type="Privilege Escalation",
            risk=60,
            attempted_risk=60,
            reason="Permission changes are blocked without explicit authorization.",
            event_trace=[
                "Tool invoked: CHANGE_PERMISSION",
                "Policy matched: BLOCK_PERMISSION_CHANGE",
                "Risk blocked immediately: +60 attempted",
                "Action blocked",
            ],
        )

    return _build_result(
        action_type=action_type,
        action_label=action_type.replace("_", " ").title(),
        target=target,
        policy_triggered="RISKY_UNKNOWN_ACTION",
        policy_description="Unknown or unmapped actions are scored and evaluated against the threshold.",
        decision="Allowed",
        threat_type="Unknown Behavior",
        risk=20,
        attempted_risk=20,
        reason="Unknown or unmapped action carries baseline operational risk.",
        event_trace=[
            f"Tool invoked: {action_type or 'UNKNOWN'}",
            "Policy matched: RISKY_UNKNOWN_ACTION",
            "Attempted risk scored: +20",
            "Action sent to threshold engine",
        ],
    )
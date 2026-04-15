from __future__ import annotations

from brimley import BrimleyContext, function

from entities import ImportReportResult
from swarm_utils import detect_existing_test, encode_event_detail, parse_jacoco_report, resolve_project_path


NULL_TEXT_SENTINEL = ""
NULL_FLOAT_SENTINEL = -1.0

@function(name="test_entity", mcpType="tool")
def test_entity() -> ImportReportResult:    
    return ImportReportResult(
        run_id=10,
        report_path="path/to/report",
        scope_filter="prefix",
        classes_imported=10
    )   

@function(name="read_jacoco_report", mcpType="tool")
def read_jacoco_report(
    report_path: str = "target/site/jacoco/jacoco.xml",
    scope_filter: str = "",
    *,
    ctx: BrimleyContext,
) -> None:
    resolved_report_path = resolve_project_path(ctx, report_path)
    if not resolved_report_path.exists():
        raise FileNotFoundError(f"JaCoCo report not found: {resolved_report_path}")

    scope_prefix = scope_filter.strip()
    results = []
    for record in parse_jacoco_report(resolved_report_path):
        print(f"Processing record for {record.fqcn} with scope prefix '{scope_prefix}'")

    #return results

@function(name="import_jacoco_report", mcpType="tool")
def import_jacoco_report(
    run_id: int,
    report_path: str = "target/site/jacoco/jacoco.xml",
    scope_filter: str = "",
    *,
    ctx: BrimleyContext,
) -> ImportReportResult:
    resolved_report_path = resolve_project_path(ctx, report_path)
    if not resolved_report_path.exists():
        raise FileNotFoundError(f"JaCoCo report not found: {resolved_report_path}")

    imported_count = 0
    scope_prefix = scope_filter.strip()

    run = ctx.execute_function_by_name("get_run_for_import", {"run_id": run_id})
    if run is None:
        raise ValueError(f"Run {run_id} does not exist")

    for record in parse_jacoco_report(resolved_report_path):
        if scope_prefix and not record.fqcn.startswith(scope_prefix):
            continue

        has_existing_test, test_file = detect_existing_test(ctx, record.fqcn)
        class_row = ctx.execute_function_by_name(
            "upsert_imported_class",
            {
                "run_id": run_id,
                "fqcn": record.fqcn,
                "package_name": record.package_name,
                "source_file": record.source_file or NULL_TEXT_SENTINEL,
                "instruction_missed": record.instruction.missed,
                "instruction_covered": record.instruction.covered,
                "branch_missed": record.branch.missed,
                "branch_covered": record.branch.covered,
                "line_missed": record.line.missed,
                "line_covered": record.line.covered,
                "complexity_missed": record.complexity.missed,
                "complexity_covered": record.complexity.covered,
                "instruction_coverage": record.instruction_coverage
                if record.instruction_coverage is not None
                else NULL_FLOAT_SENTINEL,
                "branch_coverage": record.branch_coverage
                if record.branch_coverage is not None
                else NULL_FLOAT_SENTINEL,
                "has_existing_test": int(has_existing_test),
                "test_file": test_file or NULL_TEXT_SENTINEL,
            },
        )

        ctx.execute_function_by_name(
            "create_event",
            {
                "run_id": run_id,
                "class_id": class_row.id,
                "event_type": "import",
                "agent_id": NULL_TEXT_SENTINEL,
                "detail": encode_event_detail(
                    {
                        "fqcn": record.fqcn,
                        "has_existing_test": has_existing_test,
                        "report_path": str(resolved_report_path),
                    }
                ),
            },
        )
        imported_count += 1

    return ImportReportResult(
        run_id=run_id,
        report_path=str(resolved_report_path),
        scope_filter=scope_prefix,
        classes_imported=imported_count,
    )
//! Deterministic audit for the EAASP v2.0 platform-skeleton alignment artifacts.

use std::fs;
use std::path::{Path, PathBuf};

const REQUIRED_FILES: [&str; 4] = [
    "ALIGNMENT_MATRIX.md",
    "memory_manifest.md",
    "pipe_topology.md",
    "certifier_surface.md",
];

const REQUIRED_MARKERS: [&str; 20] = [
    "L0 Protocol",
    "L1 Execution",
    "L2 Assets",
    "L3 Governance",
    "L4 Orchestration",
    "L5 Cowork",
    "Hook pipeline",
    "Data-flow pipeline",
    "Session-control pipeline",
    "Event card",
    "Evidence pack",
    "Action card",
    "Approval card",
    "memory_search",
    "memory_confirm",
    "L4 → L1",
    "L2 MCP",
    "OPA",
    "Sandbox",
    "Spec section cross-index",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SpecAuditReport {
    pub root: PathBuf,
    pub files_checked: usize,
    pub section_rows: usize,
    pub findings: Vec<String>,
}

impl SpecAuditReport {
    pub fn passed(&self) -> bool {
        self.findings.is_empty()
    }

    pub fn to_markdown(&self) -> String {
        let status = if self.passed() { "PASS" } else { "FAIL" };
        let mut out = format!(
            "# EAASP v3.10 Spec Audit Report\n\n- Status: **{status}**\n- Files checked: {}\n- Spec rows: {}\n- Root: `{}`\n",
            self.files_checked,
            self.section_rows,
            self.root.display()
        );
        if !self.findings.is_empty() {
            out.push_str("\n## Findings\n");
            for finding in &self.findings {
                out.push_str(&format!("\n- {finding}"));
            }
            out.push('\n');
        }
        out
    }
}

pub fn audit_alignment(root: &Path) -> SpecAuditReport {
    let mut report = SpecAuditReport {
        root: root.to_path_buf(),
        files_checked: 0,
        section_rows: 0,
        findings: Vec::new(),
    };
    let mut combined = String::new();

    for name in REQUIRED_FILES {
        let path = root.join(name);
        match fs::read_to_string(&path) {
            Ok(content) if !content.trim().is_empty() => {
                report.files_checked += 1;
                combined.push_str(&content);
                combined.push('\n');
            }
            Ok(_) => report
                .findings
                .push(format!("empty alignment file: {name}")),
            Err(error) => report
                .findings
                .push(format!("missing alignment file {name}: {error}")),
        }
    }

    for marker in REQUIRED_MARKERS {
        if !combined.contains(marker) {
            report
                .findings
                .push(format!("missing required marker: {marker}"));
        }
    }

    if let Ok(memory) = fs::read_to_string(root.join("memory_manifest.md")) {
        for tool in [
            "memory_search",
            "memory_read",
            "memory_write_anchor",
            "memory_write_file",
            "memory_list",
            "memory_archive",
            "memory_confirm",
        ] {
            if !memory.contains(tool) {
                report
                    .findings
                    .push(format!("memory manifest missing tool: {tool}"));
            }
        }
    }
    if let Ok(matrix) = fs::read_to_string(root.join("ALIGNMENT_MATRIX.md")) {
        validate_cross_index(&matrix, &mut report);
    }
    report
}

fn validate_cross_index(matrix: &str, report: &mut SpecAuditReport) {
    let Some(index) = matrix.split("## Spec section cross-index").nth(1) else {
        return;
    };
    let allowed = [
        "aligned",
        "partial",
        "missing",
        "deferred_to_v3.11+",
        "not_certified",
    ];
    for line in index.lines().filter(|line| line.starts_with("| §")) {
        report.section_rows += 1;
        let cells: Vec<_> = line.trim_matches('|').split('|').map(str::trim).collect();
        if cells.len() != 4 {
            report
                .findings
                .push(format!("invalid cross-index row: {line}"));
            continue;
        }
        if !allowed.contains(&cells[1]) {
            report
                .findings
                .push(format!("unknown status `{}` in row: {line}", cells[1]));
        }
        if cells[2].is_empty() || cells[3].is_empty() {
            report
                .findings
                .push(format!("phase/owner missing in row: {line}"));
        }
    }
    if report.section_rows < 30 {
        report.findings.push(format!(
            "cross-index has only {} rows; expected at least 30",
            report.section_rows
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn fixture_dir() -> PathBuf {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!("eaasp-spec-audit-{suffix}"));
        fs::create_dir_all(&root).unwrap();
        root
    }

    #[test]
    fn production_alignment_passes() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../eaasp-spec-alignment");
        let report = audit_alignment(&root);
        assert!(report.passed(), "{}", report.to_markdown());
        assert!(report.section_rows >= 30);
    }

    #[test]
    fn synthetic_missing_tool_fails_with_named_finding() {
        let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("../eaasp-spec-alignment");
        let root = fixture_dir();
        for name in REQUIRED_FILES {
            let content = fs::read_to_string(source.join(name)).unwrap();
            let content = if name == "memory_manifest.md" {
                content
                    .lines()
                    .filter(|line| !line.contains("memory_confirm"))
                    .collect::<Vec<_>>()
                    .join("\n")
            } else {
                content
            };
            fs::write(root.join(name), content).unwrap();
        }

        let report = audit_alignment(&root);
        assert!(!report.passed());
        assert!(report
            .findings
            .iter()
            .any(|finding| finding.contains("memory_confirm")));
        fs::remove_dir_all(root).unwrap();
    }
}

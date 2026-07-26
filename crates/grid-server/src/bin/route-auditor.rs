use grid_server::rbac::{audit_catalog, catalog::{route_catalog, PUBLIC_ROUTE_ALLOWLIST}};

fn main() {
    match audit_catalog(route_catalog(), &PUBLIC_ROUTE_ALLOWLIST) {
        Ok(()) => println!("RBAC route audit PASS: {} routes", route_catalog().len()),
        Err(findings) => {
            eprintln!("RBAC route audit FAILED ({} findings)", findings.len());
            for finding in findings {
                eprintln!("- {finding}");
            }
            std::process::exit(1);
        }
    }
}

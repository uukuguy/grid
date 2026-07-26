pub mod catalog;

use std::collections::HashSet;

use catalog::{RouteCatalogEntry, RouteKind};
use grid_engine::auth::roles::Role;

pub fn audit_catalog(
    catalog: &[RouteCatalogEntry],
    public_allowlist: &[(&str, &str)],
) -> Result<(), Vec<String>> {
    let mut findings = Vec::new();
    let mut seen = HashSet::new();
    let public_set: HashSet<_> = public_allowlist.iter().copied().collect();
    let roles = [Role::Viewer, Role::User, Role::Admin, Role::Owner];

    for entry in catalog {
        if !seen.insert((entry.method, entry.path)) {
            findings.push(format!("duplicate route: {} {}", entry.method, entry.path));
        }
        match entry.route_kind {
            RouteKind::Public if !public_set.contains(&(entry.method, entry.path)) => findings.push(
                format!(
                    "public route not on public allowlist: {} {}",
                    entry.method, entry.path
                ),
            ),
            RouteKind::Public => {}
            RouteKind::Requires(action) if !roles.iter().any(|role| role.can(action)) => findings
                .push(format!(
                    "Action {:?} is not exercisable: {} {}",
                    action, entry.method, entry.path
                )),
            RouteKind::Requires(_) => {}
        }
    }

    for &(method, path) in public_allowlist {
        if !catalog.iter().any(|entry| {
            entry.method == method && entry.path == path && entry.route_kind == RouteKind::Public
        }) {
            findings.push(format!("allowlisted route missing public catalog entry: {method} {path}"));
        }
    }

    if findings.is_empty() { Ok(()) } else { Err(findings) }
}

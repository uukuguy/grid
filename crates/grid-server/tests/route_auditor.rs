use grid_server::rbac::audit_catalog;
use grid_server::rbac::catalog::{route_catalog, RouteCatalogEntry, PUBLIC_ROUTE_ALLOWLIST};

#[test]
fn aud_01_production_catalog_passes() {
    assert_eq!(audit_catalog(route_catalog(), &PUBLIC_ROUTE_ALLOWLIST), Ok(()));
}

#[test]
fn test_07_synthetic_unprotected_route_is_named() {
    let synthetic = [RouteCatalogEntry::public("POST", "/api/v1/unplugged")];
    let findings = audit_catalog(&synthetic, &PUBLIC_ROUTE_ALLOWLIST).unwrap_err();
    assert!(findings.iter().any(|finding| {
        finding.contains("POST /api/v1/unplugged") && finding.contains("not on public allowlist")
    }));
}

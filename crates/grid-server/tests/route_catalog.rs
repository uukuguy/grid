use grid_server::rbac::catalog::{build_catalog, RouteKind, PUBLIC_ROUTE_ALLOWLIST};
use std::collections::HashSet;

#[test]
fn cat_01_catalog_is_complete_and_unique() {
    let catalog = build_catalog();
    let unique: HashSet<_> = catalog
        .iter()
        .map(|route| (route.method, route.path))
        .collect();

    assert_eq!(unique.len(), catalog.len(), "duplicate method/path entries");
    assert!(
        catalog.len() >= 120,
        "catalog unexpectedly small: {}",
        catalog.len()
    );

    for expected in [
        ("GET", "/api/health"),
        ("GET", "/api/health/live"),
        ("GET", "/v1/sessions/{id}/stream"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/sessions"),
        ("POST", "/api/v1/memories"),
        ("DELETE", "/api/v1/memories"),
        ("POST", "/api/v1/scheduler/tasks/{id}/run"),
        ("GET", "/api/v1/knowledge-graph/path"),
        ("POST", "/api/v1/admin/reload"),
    ] {
        assert!(
            catalog
                .iter()
                .any(|route| (route.method, route.path) == expected),
            "missing route: {} {}",
            expected.0,
            expected.1
        );
    }
}

#[test]
fn cat_02_public_allowlist_is_exact_and_symmetric() {
    assert_eq!(
        PUBLIC_ROUTE_ALLOWLIST,
        [
            ("GET", "/api/health"),
            ("GET", "/api/health/live"),
            ("POST", "/api/v1/auth/login"),
        ]
    );

    let catalog = build_catalog();
    let public: Vec<_> = catalog
        .iter()
        .filter(|route| route.route_kind == RouteKind::Public)
        .map(|route| (route.method, route.path))
        .collect();

    assert_eq!(public, PUBLIC_ROUTE_ALLOWLIST);
}

#[test]
fn cat_04_catalog_is_public_typed_data() {
    let catalog = build_catalog();
    assert!(catalog.iter().any(|route| {
        route.method == "PUT"
            && route.path == "/api/v1/config"
            && matches!(route.route_kind, RouteKind::Requires(_))
    }));
}

use axum::{body::Body, extract::Request, http::Method};
use grid_engine::auth::roles::Action;
use grid_server::middleware::auth::action_for_request;
use grid_server::rbac::catalog::{route_catalog, RouteKind};

#[test]
fn rbac_05_full_route_catalog_is_annotated() {
    let missing: Vec<_> = route_catalog()
        .iter()
        .filter(|entry| !matches!(entry.route_kind, RouteKind::Public | RouteKind::Requires(_)))
        .collect();
    assert!(missing.is_empty(), "unannotated routes: {missing:?}");
}

#[test]
fn rbac_08_runtime_resolver_uses_catalog_metadata() {
    for entry in route_catalog() {
        let method: Method = entry.method.parse().unwrap();
        let request = Request::builder()
            .method(method)
            .uri(entry.path)
            .body(Body::empty())
            .unwrap();
        let resolved = action_for_request(&request);
        match entry.route_kind {
            RouteKind::Public => assert_eq!(resolved, None),
            RouteKind::Requires(action) => assert_eq!(resolved, Some(action)),
        }
    }
}

#[test]
fn mode_03_viewer_cannot_resolve_non_read_as_allowed() {
    let mut saw_non_read = false;
    for entry in route_catalog() {
        if let RouteKind::Requires(action) = entry.route_kind {
            if action != Action::Read {
                saw_non_read = true;
                assert!(!grid_engine::auth::roles::Role::Viewer.can(action));
            }
        }
    }
    assert!(saw_non_read);
}

#[test]
fn crate_compiles() {
    assert_eq!(2 + 2, 4);
}

#[test]
fn proxy_server_type_exists() {
    use eaasp_scoped_hook_mcp::ProxyServer;
    assert!(std::any::type_name::<ProxyServer>().contains("ProxyServer"));
}

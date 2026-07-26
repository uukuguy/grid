use grid_engine::auth::roles::{Action, Role};

const ALL_ACTIONS: [Action; 20] = [
    Action::Read,
    Action::CreateSession,
    Action::RunAgent,
    Action::ManageMcp,
    Action::ManageSkills,
    Action::ManageUsers,
    Action::ManageConfig,
    Action::ManageAudit,
    Action::ManageHooks,
    Action::ManageMemories,
    Action::ManageProviders,
    Action::ManageSecrets,
    Action::ManageSandbox,
    Action::ManageScheduler,
    Action::ManageSecurity,
    Action::ManageCollaboration,
    Action::ManageKnowledgeGraph,
    Action::ManageEval,
    Action::ManageMetering,
    Action::ManageAgents,
];

#[test]
fn cat_03_all_actions_parse_and_owner_can_execute_them() {
    for action in ALL_ACTIONS {
        let serialized = serde_json::to_string(&action).unwrap();
        let name = serialized.trim_matches('"');
        assert_eq!(Action::parse(name), Some(action), "parse {name}");
        assert!(Role::Owner.can(action), "owner denied {action:?}");
    }
}

#[test]
fn rbac_07_role_matrix_is_coherent_and_leg_agnostic() {
    for action in ALL_ACTIONS {
        assert_eq!(Role::Viewer.can(action), action == Action::Read);
        assert_eq!(
            Role::User.can(action),
            matches!(action, Action::Read | Action::CreateSession | Action::RunAgent)
        );
    }

    for action in [
        Action::ManageMcp,
        Action::ManageSkills,
        Action::ManageAudit,
        Action::ManageHooks,
        Action::ManageMemories,
        Action::ManageProviders,
        Action::ManageSecrets,
        Action::ManageSandbox,
        Action::ManageScheduler,
        Action::ManageSecurity,
        Action::ManageCollaboration,
        Action::ManageKnowledgeGraph,
        Action::ManageEval,
        Action::ManageMetering,
        Action::ManageAgents,
    ] {
        assert!(Role::Admin.can(action), "admin denied {action:?}");
    }
    assert!(!Role::Admin.can(Action::ManageUsers));
    assert!(!Role::Admin.can(Action::ManageConfig));
}

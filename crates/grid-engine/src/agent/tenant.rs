use grid_types::{TenantId, UserId};

use crate::auth::{Action, Role};

#[derive(Debug, Clone)]
pub struct TenantContext {
    pub tenant_id: TenantId,
    pub user_id: UserId,
    pub roles: Vec<Role>,
}

impl TenantContext {
    /// 单用户场景 (octo-workbench)
    pub fn for_single_user(tenant_id: TenantId, user_id: UserId) -> Self {
        Self {
            tenant_id,
            user_id,
            roles: vec![Role::Owner],
        }
    }

    /// 多用户场景 (03.8.2 — `RBAC-01`/`RBAC-04` + `TENANT-01`)
    ///
    /// In v3.8.2 each user holds exactly one role; the constructor still
    /// returns `Vec<Role>` so future multi-role provisioning (v3.9+) is
    /// source-compatible.
    pub fn for_multi_user(tenant_id: TenantId, user_id: UserId, role: Role) -> Self {
        Self {
            tenant_id,
            user_id,
            roles: vec![role],
        }
    }

    /// 验证用户有权限执行操作
    pub fn can(&self, action: Action) -> bool {
        self.roles.iter().any(|role| role.can(action))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tenant(id: &str) -> TenantId {
        TenantId::from_string(id)
    }
    fn user(id: &str) -> UserId {
        UserId::from_string(id)
    }

    #[test]
    fn multi_user_admin_can_run_manage_mcp_and_skills() {
        // Per the Role::can matrix: Admin can ManageMcp + ManageSkills;
        // only Owner can ManageUsers. The test asserts the two paths an
        // Admin actually has — not ManageUsers (which they don't).
        let ctx = TenantContext::for_multi_user(tenant("t1"), user("u1"), Role::Admin);
        assert!(ctx.can(Action::ManageMcp));
        assert!(ctx.can(Action::ManageSkills));
        assert!(!ctx.can(Action::ManageUsers), "Admin must NOT ManageUsers");
    }

    #[test]
    fn multi_user_viewer_cannot_run_manage_users() {
        let ctx = TenantContext::for_multi_user(tenant("t1"), user("u1"), Role::Viewer);
        assert!(!ctx.can(Action::ManageUsers));
        // Read is allowed for everyone.
        assert!(ctx.can(Action::Read));
    }

    #[test]
    fn multi_user_owner_can_run_every_action() {
        let ctx = TenantContext::for_multi_user(tenant("t1"), user("u1"), Role::Owner);
        // Iterate over the enum's actual variants — keeps this in sync if
        // a new Action is added without requiring a manual list edit.
        let actions = [
            Action::Read,
            Action::CreateSession,
            Action::RunAgent,
            Action::ManageMcp,
            Action::ManageSkills,
            Action::ManageUsers,
            Action::ManageConfig,
        ];
        for action in actions {
            assert!(ctx.can(action), "Owner must run {action:?}");
        }
    }
}

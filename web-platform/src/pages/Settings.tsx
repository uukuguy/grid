import { useEffect, useState } from "react";
import { useSetAtom } from "jotai";
import { User, Save, Loader2 } from "lucide-react";
import { usersApi } from "../api/users";
import { userAtom } from "../atoms";
import { addToastAtom } from "../atoms/ui";

interface ValidationErrors {
  display_name?: string;
  email?: string;
}

export function SettingsPage() {
  const setUser = useSetAtom(userAtom);
  const addToast = useSetAtom(addToastAtom);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState<{ id: string; email: string; display_name: string; role: string } | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [errors, setErrors] = useState<ValidationErrors>({});

  useEffect(() => {
    usersApi.me().then((user) => {
      setProfile(user);
      setDisplayName(user.display_name);
      setUser(user);
    }).catch((err) => {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Failed to load profile" });
    }).finally(() => setLoading(false));
  }, [setUser, addToast]);

  const validate = (name: string): boolean => {
    const errs: ValidationErrors = {};
    const trimmed = name.trim();
    if (!trimmed) errs.display_name = "Display name is required";
    else if (trimmed.length > 100) errs.display_name = "Display name must be under 100 characters";
    else if (trimmed.length < 2) errs.display_name = "Display name must be at least 2 characters";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!profile) return;
    if (!validate(displayName)) return;

    setSaving(true);
    try {
      const updated = await usersApi.update(profile.id, { display_name: displayName });
      setProfile(updated);
      setUser(updated);
      addToast({ type: "success", message: "Profile updated" });
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Failed to save" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-lg mx-auto flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="max-w-lg mx-auto text-center py-16 text-gray-400">
        Failed to load profile
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="bg-white rounded-lg border p-6 space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b">
          <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
            <User className="w-8 h-8 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">{profile.display_name}</h2>
            <p className="text-sm text-gray-500">{profile.email}</p>
            <span className="inline-block mt-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full capitalize">
              {profile.role}
            </span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Display Name</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => { setDisplayName(e.target.value); setErrors({}); }}
            className={`w-full px-3 py-2 border rounded-lg ${errors.display_name ? "border-red-400" : ""}`}
          />
          {errors.display_name && (
            <p className="text-sm text-red-500 mt-1">{errors.display_name}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            value={profile.email}
            disabled
            className="w-full px-3 py-2 border rounded-lg bg-gray-50 text-gray-500 cursor-not-allowed"
          />
          <p className="text-xs text-gray-400 mt-1">Contact an admin to change your email</p>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Role</label>
          <div className="px-3 py-2 border rounded-lg bg-gray-50 text-gray-500 capitalize">{profile.role}</div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

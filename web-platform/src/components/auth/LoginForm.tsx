import { useState } from "react";
import { useSetAtom } from "jotai";
import { userAtom, accessTokenAtom, refreshTokenAtom } from "../../atoms";
import { authApi } from "../../api/auth";
import { Loader2 } from "lucide-react";

interface LoginFormProps {
  onSuccess?: () => void;
}

interface FieldErrors {
  email?: string;
  password?: string;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const setUser = useSetAtom(userAtom);
  const setAccessToken = useSetAtom(accessTokenAtom);
  const setRefreshToken = useSetAtom(refreshTokenAtom);

  const validate = (): boolean => {
    const errs: FieldErrors = {};
    const emailTrim = email.trim();
    if (!emailTrim) errs.email = "Email is required";
    else if (!emailTrim.includes("@") || !emailTrim.includes(".")) errs.email = "Invalid email address";
    if (!password) errs.password = "Password is required";
    else if (password.length < 8) errs.password = "Password must be at least 8 characters";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!validate()) return;
    setLoading(true);

    try {
      const response = await authApi.login({ email: email.trim(), password });
      setUser(response.user);
      setAccessToken(response.access_token);
      setRefreshToken(response.refresh_token);
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">
          {error}
        </div>
      )}
      <div>
        <label className="block text-sm font-medium mb-1">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setFieldErrors({}); }}
          className={`w-full px-3 py-2 border rounded-lg ${fieldErrors.email ? "border-red-400" : ""}`}
          placeholder="you@example.com"
        />
        {fieldErrors.email && <p className="text-sm text-red-500 mt-1">{fieldErrors.email}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); setFieldErrors({}); }}
          className={`w-full px-3 py-2 border rounded-lg ${fieldErrors.password ? "border-red-400" : ""}`}
          placeholder="Min. 8 characters"
        />
        {fieldErrors.password && <p className="text-sm text-red-500 mt-1">{fieldErrors.password}</p>}
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-primary text-white py-2 rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {loading ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}

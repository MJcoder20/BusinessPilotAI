
import { useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { Bot, Eye, EyeOff, LoaderCircle, LockKeyhole } from "lucide-react";
import { useAuth } from "../context/AuthContext";

function getApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item: { msg?: string }) => item.msg)
        .filter(Boolean)
        .join(" ");
    }
  }

  return "Something went wrong. Please try again.";
}

export default function AuthScreen() {
  const { login, register } = useAuth();

  const [isRegistering, setIsRegistering] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (isRegistering && password.length < 12) {
      setError("Your password must contain at least 12 characters.");
      return;
    }

    setLoading(true);

    try {
      if (isRegistering) {
        await register(fullName, email, password);
      } else {
        await login(email, password);
      }
    } catch (err: unknown) {
      setError(getApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function switchMode() {
    setIsRegistering((previous) => !previous);
    setError("");
    setPassword("");
  }

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-icon">
            <Bot size={27} />
          </div>
          <div>
            <h1>BusinessPilot</h1>
            <span>AI BUSINESS ASSISTANT</span>
          </div>
        </div>

        <div className="auth-heading">
          <div className="auth-heading-icon">
            <LockKeyhole size={21} />
          </div>

          <h2>
            {isRegistering ? "Create your account" : "Welcome back"}
          </h2>

          <p>
            {isRegistering
              ? "Create an account to access your business workspace."
              : "Sign in to continue to your business workspace."}
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegistering && (
            <label>
              Full name
              <input
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Your full name"
                minLength={2}
                maxLength={150}
                autoComplete="name"
                required
                disabled={loading}
              />
            </label>
          )}

          <label>
            Email address
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
              disabled={loading}
            />
          </label>

          <label>
            Password
            <div className="auth-password-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                minLength={isRegistering ? 12 : undefined}
                maxLength={128}
                autoComplete={
                  isRegistering ? "new-password" : "current-password"
                }
                required
                disabled={loading}
              />

              <button
                type="button"
                className="auth-password-toggle"
                onClick={() => setShowPassword((previous) => !previous)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {isRegistering && (
              <small>Use at least 12 characters.</small>
            )}
          </label>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="auth-submit-button"
            disabled={loading}
          >
            {loading ? (
              <>
                <LoaderCircle size={18} className="spinner" />
                Please wait...
              </>
            ) : isRegistering ? (
              "Create account"
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        <div className="auth-switch">
          {isRegistering
            ? "Already have an account?"
            : "Don't have an account?"}

          <button type="button" onClick={switchMode} disabled={loading}>
            {isRegistering ? "Sign in" : "Create account"}
          </button>
        </div>

        <p className="auth-security-note">
          Your business workspace is protected by secure authentication.
        </p>
      </section>
    </main>
  );
}

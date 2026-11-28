import { useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import {
  Bot,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  MailCheck,
} from "lucide-react";
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

  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export default function AuthScreen() {
  const {
    login,
    register,
    linkAccount,
    isPasswordRecovery,
    requestPasswordReset,
    updatePassword,
  } = useAuth();

  const [isRegistering, setIsRegistering] = useState(false);
  const [confirmationSent, setConfirmationSent] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [needsAccountLink, setNeedsAccountLink] = useState(false);
  const [linkPassword, setLinkPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetPassword, setResetPassword] = useState("");
  const [confirmResetPassword, setConfirmResetPassword] = useState("");
  const [resetEmailSent, setResetEmailSent] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (needsAccountLink && linkPassword.length === 0) {
      setError("Please enter your original account password.");
      return;
    }

    if (!needsAccountLink && isRegistering && password.length < 12) {
      setError("Your password must contain at least 12 characters.");
      return;
    }

    setLoading(true);

    try {
      if (needsAccountLink) {
        await linkAccount(linkPassword);
        setNeedsAccountLink(false);
        setLinkPassword("");
      } else if (isRegistering) {
        await register(fullName, email, password);
        setConfirmationSent(true);
      } else {
        await login(email, password);
      }
    } catch (err: unknown) {
      const message = getApiError(err);

      if (
        !isRegistering &&
        !needsAccountLink &&
        message.toLowerCase().includes(
          "contact support to link your accounts safely"
        )
      ) {
        setNeedsAccountLink(true);
        setError(
          "Your Supabase account is verified, but an existing account was found. Enter the password you used for that original account to link them securely."
        );
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotPassword(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await requestPasswordReset(email);
      setResetEmailSent(true);
    } catch (err: unknown) {
      setError(getApiError(err));
    } finally {
      setLoading(false);
    }
  }

  async function handlePasswordReset(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    setError("");

    if (resetPassword.length < 12) {
      setError("Your password must contain at least 12 characters.");
      return;
    }

    if (resetPassword !== confirmResetPassword) {
      setError("The passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await updatePassword(resetPassword);
    } catch (err: unknown) {
      setError(getApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function switchMode() {
    setIsRegistering((previous) => !previous);
    setConfirmationSent(false);
    setError("");
    setPassword("");
  }

  if (isPasswordRecovery) {
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
            <h2>Reset your password</h2>
            <p>Choose a new password for your account.</p>
          </div>

          <form
            className="auth-form"
            onSubmit={handlePasswordReset}
          >
            <label>
              New password
              <input
                type="password"
                value={resetPassword}
                onChange={(event) =>
                  setResetPassword(event.target.value)
                }
                placeholder="Enter your new password"
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                required
                disabled={loading}
              />
              <small>Use at least 12 characters.</small>
            </label>

            <label>
              Confirm new password
              <input
                type="password"
                value={confirmResetPassword}
                onChange={(event) =>
                  setConfirmResetPassword(event.target.value)
                }
                placeholder="Confirm your new password"
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                required
                disabled={loading}
              />
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
                  Updating password...
                </>
              ) : (
                "Update password"
              )}
            </button>
          </form>

          <p className="auth-security-note">
            Your new password will securely replace your previous password.
          </p>
        </section>
      </main>
    );
  }

  if (showForgotPassword) {
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
              <MailCheck size={25} />
            </div>

            <h2>
              {resetEmailSent ? "Check your email" : "Forgot password?"}
            </h2>

            <p>
              {resetEmailSent
                ? "If an account exists for this address, you'll receive a password-reset link."
                : "Enter your account email address and we'll send you a password-reset link."}
            </p>
          </div>

          {!resetEmailSent ? (
            <form
              className="auth-form"
              onSubmit={handleForgotPassword}
            >
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
                    Sending...
                  </>
                ) : (
                  "Send reset link"
                )}
              </button>
            </form>
          ) : (
            <p className="auth-security-note">
              Check your inbox and spam folder. Open the newest recovery email
              in a private browser window if another account is already signed in.
            </p>
          )}

          <div className="auth-switch">
            Remember your password?

            <button
              type="button"
              onClick={() => {
                setShowForgotPassword(false);
                setResetEmailSent(false);
                setError("");
              }}
              disabled={loading}
            >
              Return to sign in
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (confirmationSent) {
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
              <MailCheck size={25} />
            </div>

            <h2>Check your email</h2>

            <p>
              We've sent a confirmation link to{" "}
              <strong>{email}</strong>.
              Please confirm your email address before signing in.
            </p>
          </div>

          <button
            type="button"
            className="auth-submit-button"
            onClick={() => {
              setConfirmationSent(false);
              setIsRegistering(false);
              setPassword("");
              setError("");
            }}
          >
            Return to sign in
          </button>

          <p className="auth-security-note">
            If you don't see the email, check your spam or junk folder.
          </p>
        </section>
      </main>
    );
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
            {needsAccountLink ? "Original account password" : "Password"}

            <div className="auth-password-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                value={needsAccountLink ? linkPassword : password}
                onChange={(event) =>
                  needsAccountLink
                    ? setLinkPassword(event.target.value)
                    : setPassword(event.target.value)
                }
                placeholder={
                  needsAccountLink
                    ? "Enter your original account password"
                    : "Enter your password"
                }
                minLength={
                  isRegistering && !needsAccountLink ? 12 : undefined
                }
                maxLength={128}
                autoComplete={
                  isRegistering && !needsAccountLink
                    ? "new-password"
                    : "current-password"
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

            {isRegistering && !needsAccountLink && (
              <small>Use at least 12 characters.</small>
            )}

            {needsAccountLink && (
              <small>
                Enter the password you used for your original account, not necessarily
                your Supabase password.
              </small>
            )}
          </label>

          {!isRegistering && !needsAccountLink && (
            <div style={{ textAlign: "right", marginTop: "-8px" }}>
              <button
                type="button"
                onClick={() => {
                  setShowForgotPassword(true);
                  setError("");
                }}
                className="auth-password-toggle"
                style={{
                  position: "static",
                  width: "auto",
                  height: "auto",
                  color: "var(--primary)",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                Forgot password?
              </button>
            </div>
          )}

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
            ) : needsAccountLink ? (
              "Link existing account"
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

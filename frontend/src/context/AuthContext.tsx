import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useRef,
  type ReactNode,
} from "react";

import {
  register as registerApi,
  logout as logoutApi,
  getCurrentUser,
  refreshAccessToken,
  setAccessToken,
  setAuthProvider,
  syncSupabaseUser,
  linkSupabaseAccount,
  type AuthUser,
} from "../services/api";

import { supabase } from "../services/supabase";

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  linkAccount: (password: string) => Promise<void>;
  register: (
    fullName: string,
    email: string,
    password: string
  ) => Promise<void>;
  logout: () => Promise<void>;
  isPasswordRecovery: boolean;
  requestPasswordReset: (email: string) => Promise<void>;
  updatePassword: (newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPasswordRecovery, setIsPasswordRecovery] = useState(false);
  const recoveryDetected = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY") {
        recoveryDetected.current = true;
        setIsPasswordRecovery(true);

        setAuthProvider("supabase");

        if (session) {
          setAccessToken(session.access_token);
        }
      }
    });

    const handleSessionExpired = () => {
      setAccessToken(null);
      setAuthProvider(null);
      setUser(null);
    };

    window.addEventListener(
      "auth:session-expired",
      handleSessionExpired
    );

    async function restoreSession() {
      try {
        const {
          data: { session },
          error,
        } = await supabase.auth.getSession();

        if (error) throw error;

        if (session) {
          setAuthProvider("supabase");
          setAccessToken(session.access_token);

          if (recoveryDetected.current) {
            if (!cancelled) {
              setIsPasswordRecovery(true);
              setUser(null);
            }
            return;
          }

          const currentUser = await syncSupabaseUser(
            session.access_token
          );

          if (!cancelled) setUser(currentUser);
          return;
        }

        setAuthProvider("legacy");

        const token = await refreshAccessToken();
        setAccessToken(token);

        const currentUser = await getCurrentUser();

        if (!cancelled) setUser(currentUser);
      } catch {
        setAccessToken(null);
        setAuthProvider(null);

        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
      subscription.unsubscribe();
      window.removeEventListener(
        "auth:session-expired",
        handleSessionExpired
      );
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const {
        data,
        error: supabaseError,
      } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (!supabaseError && data.session) {
        setAuthProvider("supabase");
        setAccessToken(data.session.access_token);

        try {
          const currentUser = await syncSupabaseUser(
            data.session.access_token
          );

          setUser(currentUser);
          return;
        } catch (syncError) {
          // Keep the Supabase session active so the user can link
          // their existing local account.
          throw syncError;
        }
      }

      // Do not fall back to legacy login for unconfirmed accounts.
      if (
        supabaseError?.code === "email_not_confirmed"
      ) {
        throw new Error(
          "Please confirm your email address before logging in."
        );
      }

      // Existing legacy accounts continue using FastAPI authentication.
      if (supabaseError) {
        console.error("Supabase login failed:", {
          message: supabaseError.message,
          code: supabaseError.code,
          status: supabaseError.status,
        });

        throw new Error(
          `Supabase login failed: ${supabaseError.message}`
        );
      }
    },
    []
  );

  const linkAccount = useCallback(
    async (password: string) => {
      const {
        data: { session },
        error,
      } = await supabase.auth.getSession();

      if (error || !session) {
        throw new Error(
          "Your Supabase session has expired. Please log in again."
        );
      }

      const currentUser = await linkSupabaseAccount(
        session.access_token,
        password
      );

      setAuthProvider("supabase");
      setAccessToken(session.access_token);
      setUser(currentUser);
    },
    []
  );

  const register = useCallback(
    async (fullName: string, email: string, password: string) => {
      setAccessToken(null);
      setAuthProvider(null);

      await registerApi(fullName, email, password);
    },
    []
  );

  const requestPasswordReset = useCallback(
    async (email: string) => {
      const { error } = await supabase.auth.resetPasswordForEmail(
        email.trim().toLowerCase(),
        {
          redirectTo: window.location.origin,
        }
      );

      if (error) {
        throw error;
      }
    },
    []
  );

  const updatePassword = useCallback(
    async (newPassword: string) => {
      const { error } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (error) {
        throw error;
      }

      const {
        data: { session },
        error: sessionError,
      } = await supabase.auth.getSession();

      if (sessionError || !session) {
        throw sessionError ?? new Error(
          "Password updated, but your session could not be restored. Please log in."
        );
      }

      setAuthProvider("supabase");
      setAccessToken(session.access_token);

      const currentUser = await syncSupabaseUser(
        session.access_token
      );

      setUser(currentUser);
      recoveryDetected.current = false;
      setIsPasswordRecovery(false);
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (session) {
        const { error } = await supabase.auth.signOut();
        if (error) throw error;
      } else {
        await logoutApi();
      }
    } finally {
      setAccessToken(null);
      setAuthProvider(null);
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: user !== null,
        isPasswordRecovery,
        login,
        linkAccount,
        register,
        logout,
        requestPasswordReset,
        updatePassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider."
    );
  }

  return context;
}

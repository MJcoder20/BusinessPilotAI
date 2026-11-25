
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  login as loginApi,
  register as registerApi,
  logout as logoutApi,
  getCurrentUser,
  refreshAccessToken,
  setAccessToken,
  setAuthProvider,
  syncSupabaseUser,
  type AuthUser,
} from "../services/api";

import { supabase } from "../services/supabase";

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    fullName: string,
    email: string,
    password: string
  ) => Promise<void>;
  logout: () => Promise<void>;
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

  useEffect(() => {
    let cancelled = false;

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
          await supabase.auth.signOut();
          setAccessToken(null);
          setAuthProvider(null);
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
      try {
        const response = await loginApi(email, password);
        setUser(response.user);
      } catch (legacyError) {
        // Preserve the legacy error for existing legacy users.
        throw legacyError;
      }
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
        login,
        register,
        logout,
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

import { useEffect, useState } from "react";
import type { CurrentUserInfo, } from "../types/user";
import { getCurrentUser } from "../api/client";

export function useCurrentUser() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<CurrentUserInfo | null>(null);

  const refresh = async () => {
    const me = await getCurrentUser();

    setUser(me);
  };

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);

        await refresh();

      } catch (e) {
      console.error(e);

      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  return {
    user,
    loading,
    refresh,
  };
}
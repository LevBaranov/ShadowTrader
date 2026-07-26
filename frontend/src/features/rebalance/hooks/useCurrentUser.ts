import { useEffect, useState } from "react";
import type { CurrentUserInfo, } from "../types/user";
import { getCurrentUser } from "../api/client";

export function useCurrentUser() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<CurrentUserInfo | null>(null);

  // force: после мутаций (создание/удаление стратегии, балансировка)
  // нужно получить свежие данные, а не закэшированный промис.
  const refresh = async (force = true) => {
    const me = await getCurrentUser(force);

    setUser(me);
  };

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);

        await refresh(false);

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
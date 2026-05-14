let logoutFn: null | (() => void) = null;

export const setLogoutHandler = (fn: () => void) => {
  logoutFn = fn;
};

export const triggerLogout = () => {
  logoutFn?.();
};
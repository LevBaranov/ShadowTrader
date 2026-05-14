export function useErrorHandler() {
  const handleError = (
    error: unknown
  ) => {
    console.error(error);

    return "Произошла ошибка";
  };

  return {
    handleError,
  };
}
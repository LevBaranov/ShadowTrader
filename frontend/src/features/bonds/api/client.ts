
const mockBonds = [
  { id: 1, name: "OFZ 262XX", date: "2026-05-12", type: "Погашение" },
  { id: 2, name: "BOND123", date: "2026-05-01", type: "Купон" },
];

export const getBonds = async () => {
  return Promise.resolve(mockBonds);
};

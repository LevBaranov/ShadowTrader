import { BrowserRouter } from "react-router-dom";
import Router from "./router";
import { AuthProvider } from "./AuthContext";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
          <Router />
      </AuthProvider>
    </BrowserRouter>
  );
}
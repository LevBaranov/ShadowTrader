import { BrowserRouter } from "react-router-dom";
import { Container } from "@mui/material";
import Router from "./router";

export default function App() {
  return (
    <BrowserRouter>
      <Container maxWidth="lg">
        <Router />
      </Container>
    </BrowserRouter>
  );
}